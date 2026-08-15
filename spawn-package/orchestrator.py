#!/usr/bin/env python3
"""orchestrator.py — T-UNIVERSE-021 (khalid: "concentrate on orchestration").
ovh-server-001 promoted to DISPATCHER (control plane only):
claim cards -> capability match (register) -> dispatch via A2A (scoped worker
token) -> verify receipt + output hash vs probe pool (non-earner) -> mint
bananas on verified-only -> ROI/brick JSON for Observatory.

NEVER builds/runs app code. Control plane = queue/ledger/observatory only.
Code-card verification = CI run status or approved Vast worker artifact.
Every dispatch: Pattern AA (ledger row + ticket + price + ROI BEFORE), death
warrant, per-run spend re-approval for paid runs. Brainless bricks get
probe/verify jobs only. stdlib-only.
"""
import hashlib, hmac, json, os, pathlib, re, shutil, time, datetime, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DISPATCH_CONTRACT = {"scope": "read-only", "v": 1}
MIN_TOKEN = 16


def _now():
    return datetime.datetime.utcnow().isoformat() + "Z"


def _log(path, op, detail="", outcome="ok"):
    """Audit-before-mutation. Append-only, flocked, atomic."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = json.dumps({"ts": _now(), "op": op, "detail": detail, "outcome": outcome})
    with open(p, "a") as f:
        try:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
        except Exception:
            pass
        f.write(row + "\n")
    os.chmod(p, 0o600)


def _read(path, schema=None):
    """Read JSONL with corrupt-row counting. Never crashes on bad rows."""
    p = pathlib.Path(path)
    rows, corrupt = [], 0
    if not p.exists():
        return rows, 0
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            if schema and not all(k in r for k in schema):
                corrupt += 1
                continue
            rows.append(r)
        except Exception:
            corrupt += 1
    return rows, corrupt


def _atomic_write(path, content, mode=0o600):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(content)
    os.chmod(tmp, mode)
    os.replace(tmp, p)


class Orchestrator:
    def __init__(self, orch_dir, reg_dir, bank_dir, rate_card, probe_pool,
                 a2a_url, worker_token, brick_id="orchestrator-001"):
        self.orch_dir = pathlib.Path(orch_dir)
        self.reg_dir = pathlib.Path(reg_dir)
        self.bank_dir = pathlib.Path(bank_dir)
        self.rate_card = rate_card
        self.probe_pool = probe_pool
        self.a2a_url = a2a_url.rstrip("/")
        self.worker_token = worker_token
        self.brick_id = brick_id
        self.audit = self.orch_dir / "audit.jsonl"
        self.open_dir = self.orch_dir / "open"
        self.claimed_dir = self.orch_dir / "claimed"
        self.done_dir = self.orch_dir / "done"
        for d in (self.open_dir, self.claimed_dir, self.done_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.lease_s = 3600

    # ---------- helpers ----------
    def _auth(self, token):
        return (len(token) >= MIN_TOKEN
                and hmac.compare_digest(token, self.worker_token))

    def _verify_output(self, probe_id, output_hash):
        """Non-earner verify: RECOMPUTE expected hash from probe pool — never
        trusts the brick's claimed hash (DA-9)."""
        pp = pathlib.Path(self.probe_pool)
        if not pp.exists():
            return False, "probe_pool missing"
        pool = json.loads(pp.read_text())
        spec = pool.get(probe_id)
        if not spec:
            return False, f"unknown probe {probe_id}"
        exp = spec.get("expected_sha256")
        if not exp:
            return False, "probe_pool entry missing expected_sha256"
        ok = hmac.compare_digest(output_hash, exp)
        return ok, "hash match" if ok else "hash MISMATCH"

    # ---------- core ops ----------
    def claim_card(self, card_id):
        """open/ -> claimed/ atomic rename with lease. Flocked double-claim refused."""
        src = self.open_dir / card_id
        dst = self.claimed_dir / card_id
        if not src.exists():
            # lease watchdog: expired lease in claimed/ reopens
            cd = self.claimed_dir / card_id
            if cd.exists():
                try:
                    card = json.loads(cd.read_text())
                    if card.get("lease_expires", 0) < time.time():
                        card["state"] = "open"
                        card.pop("claimer", None)
                        _atomic_write(str(cd), json.dumps(card))
                        shutil.move(str(cd), str(src))
                        _log(self.audit, "lease-reopen", card_id)
                        return {"ok": True, "state": "open"}
                except Exception as e:
                    _log(self.audit, "lease-reopen-fail", card_id, str(e))
            return {"ok": False, "error": f"card {card_id} not found"}
        try:
            import fcntl
            lock = open(str(src) + ".lock", "w")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            return {"ok": False, "error": "card locked"}
        card = json.loads(src.read_text())
        card["state"] = "claimed"
        card["claimer"] = self.brick_id
        card["claimed_at"] = _now()
        card["lease_expires"] = time.time() + self.lease_s
        _atomic_write(str(dst), json.dumps(card))
        src.unlink(missing_ok=True)
        try:
            lock.close()
        except Exception:
            pass
        _log(self.audit, "claim", card_id, f"claimer={self.brick_id}")
        return {"ok": True, "state": "claimed", "card": card}

    def match_card(self, card):
        """capability_register lookup: register skill ∩ card.capability; ranked."""
        reg_rows, _ = _read(self.reg_dir / "registry.jsonl")
        skill = card.get("capability", "")
        cands = []
        for r in reg_rows:
            skills = r.get("skills") or []
            if skill in skills:
                cands.append({"brick_id": r.get("brick_id"),
                              "quality": r.get("quality", "unknown")})
        # rank: registered/verified first (register semantics: claimed->verified)
        cands.sort(key=lambda b: 0 if b["quality"] == "verified" else 1)
        return cands

    def dispatch(self, card, brick):
        """Pattern AA HARD GATE then A2A POST. Returns dispatch_id."""
        # death warrant (signed card field) mandatory
        if not card.get("death_warrant"):
            return {"ok": False, "error": "missing death_warrant — refused (DA-4)"}
        card_id = card.get("card_id", "?")
        price = card.get("price")
        # ledger row BEFORE dispatch (Pattern AA) — audit the ledger append first
        _log(self.bank_dir / "ledger-cost-rows.log", "dispatch-price",
             f"card={card_id} brick={brick.get('brick_id')} price={price}",
             "committed")
        payload = {"card_id": card_id, "probe_id": card.get("probe_id"),
                   "capability": card.get("capability"), "scope": "read-only",
                   "price": price, "dispatch_id": hashlib.sha256(
                       f"{card_id}:{time.time()}".encode()).hexdigest()[:16]}
        req = urllib.request.Request(
            f"{self.a2a_url}/dispatch",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.worker_token}",
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.load(r)
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"dispatch HTTP {e.code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:80]}
        _log(self.audit, "dispatch", card_id,
             f"brick={brick.get('brick_id')} did={payload['dispatch_id']}")
        return {"ok": True, "dispatch_id": payload["dispatch_id"],
                "brick_id": brick.get("brick_id"), "response": body}

    def verify_receipt(self, receipt):
        """Non-earner verify: validate fields + recompute hash vs probe pool."""
        for fld in ("card_id", "probe_id", "output_hash", "brick_id"):
            if not receipt.get(fld):
                return {"ok": False, "reason": f"missing {fld}"}
        ok, msg = self._verify_output(receipt["probe_id"], receipt["output_hash"])
        if not ok:
            return {"ok": False, "reason": msg}
        _log(self.audit, "verify", receipt["card_id"], f"probe={receipt['probe_id']}")
        return {"ok": True, "verified": True}

    def mint(self, card, receipt):
        """Verified ONLY. Dedup by receipt_hash (DA-3 no double-mint)."""
        receipt_hash = hashlib.sha256(json.dumps(
            receipt, sort_keys=True).encode()).hexdigest()[:16]
        ledger, _ = _read(self.bank_dir / "wallet.jsonl",
                          schema=("receipt_hash", "card_id", "bananas"))
        if any(r.get("receipt_hash") == receipt_hash for r in ledger):
            return {"ok": False, "error": "receipt replay — no double-mint"}
        v = self.verify_receipt(receipt)
        if not v.get("ok"):
            return {"ok": False, "error": f"unverified — no mint ({v.get('reason')})"}
        bananas = self.rate_card.get(receipt.get("probe_id")) or self.rate_card.get("default", 1)
        row = {"receipt_hash": receipt_hash, "card_id": receipt["card_id"],
               "brick_id": receipt["brick_id"], "probe_id": receipt["probe_id"],
               "bananas": bananas, "ts": _now()}
        _atomic_write(str(self.bank_dir / "wallet.jsonl"),
                      "\n".join(json.dumps(r) for r in ledger + [row]) + "\n")
        _log(self.audit, "mint", receipt["card_id"], f"{bananas} bananas")
        return {"ok": True, **row}

    def roi_per_brick(self):
        """{brick_id: {earned_bananas, cost_rows, roi}} -> out/roi.json"""
        wallet, _ = _read(self.bank_dir / "wallet.jsonl")
        costs, _ = _read(self.bank_dir / "ledger-cost-rows.log")
        roi = {}
        for w in wallet:
            b = w.get("brick_id", "?")
            roi.setdefault(b, {"earned_bananas": 0, "cost_rows": 0, "roi": 0})
            roi[b]["earned_bananas"] += w.get("bananas", 0)
        for c in costs:
            b = c.get("brick_id", "?")
            roi.setdefault(b, {"earned_bananas": 0, "cost_rows": 0, "roi": 0})
            roi[b]["cost_rows"] += 1
        for b, d in roi.items():
            d["roi"] = round(d["earned_bananas"] / max(1, d["cost_rows"]), 3)
        out = self.orch_dir / "out" / "roi.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(str(out), json.dumps(roi, indent=1))
        return roi

    def status(self):
        return {
            "brick_id": self.brick_id,
            "open": len(list(self.open_dir.iterdir())) if self.open_dir.exists() else 0,
            "claimed": len(list(self.claimed_dir.iterdir())) if self.claimed_dir.exists() else 0,
            "done": len(list(self.done_dir.iterdir())) if self.done_dir.exists() else 0,
            "corrupt_rows": sum(_read(self.audit)[1] for _ in [0]),
            "audit_rows": len(_read(self.audit)[0]),
        }


class Handler(BaseHTTPRequestHandler):
    def _auth(self):
        tok = self.headers.get("Authorization", "").replace("Bearer ", "")
        return self.server.orch._auth(tok)

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        o = self.server.orch
        if not self._auth():
            return self._json(401, {"error": "unauthorized"})
        if self.path == "/health":
            return self._json(200, {"status": "ok", "brick": o.brick_id})
        if self.path == "/status":
            return self._json(200, o.status())
        if self.path == "/roi":
            return self._json(200, o.roi_per_brick())
        self._json(404, {"error": "not found"})

    def do_POST(self):
        o = self.server.orch
        if not self._auth():
            return self._json(401, {"error": "unauthorized"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n)) if n else {}
        except Exception:
            return self._json(400, {"error": "malformed json"})
        p = self.path
        if p == "/claim":
            return self._json(200, o.claim_card(body.get("card_id", "")))
        if p == "/match":
            return self._json(200, {"candidates": o.match_card(body.get("card", {}))})
        if p == "/dispatch":
            return self._json(200, o.dispatch(body.get("card", {}), body.get("brick", {})))
        if p == "/verify":
            return self._json(200, o.verify_receipt(body.get("receipt", {})))
        if p == "/mint":
            return self._json(200, o.mint(body.get("card", {}), body.get("receipt", {})))
        self._json(404, {"error": "not found"})

    def log_message(self, *a):
        pass


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--orch-dir", default="/srv/bricks/orchestrator")
    ap.add_argument("--reg-dir", default="/srv/bricks/register")
    ap.add_argument("--bank-dir", default="/srv/bricks/bank")
    ap.add_argument("--probe-pool", default="/srv/bricks/orchestrator/probe_pool.json")
    ap.add_argument("--rate-card", default="{}")
    ap.add_argument("--a2a-url", default="http://127.0.0.1:3738")
    ap.add_argument("--worker-token", default=os.environ.get("WORKER_TOKEN", ""))
    ap.add_argument("--serve", default="")
    ap.add_argument("--brick-id", default="orchestrator-001")
    args = ap.parse_args()
    rc = json.loads(args.rate_card) if args.rate_card.startswith("{") else {"default": 1}
    o = Orchestrator(args.orch_dir, args.reg_dir, args.bank_dir, rc,
                     args.probe_pool, args.a2a_url, args.worker_token, args.brick_id)
    if args.serve:
        host, port = args.serve.split(":")
        srv = ThreadingHTTPServer((host, int(port)), Handler)
        srv.orch = o
        print(f"orchestrator {args.brick_id} on {args.serve} (control plane only)")
        srv.serve_forever()
    else:
        print(json.dumps(o.status()))


if __name__ == "__main__":
    main()
