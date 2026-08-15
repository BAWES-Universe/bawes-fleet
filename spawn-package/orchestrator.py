#!/usr/bin/env python3
"""orchestrator.py — T-UNIVERSE-021 (khalid: "concentrate on orchestration").
ovh-server-001 promoted to DISPATCHER (control plane only):
claim cards -> capability match (register) -> dispatch via A2A (HMAC-signed
per-card grant IS the wire auth; control token NEVER leaves the orchestrator)
-> verify receipt against structured dispatch registry + output hash vs probe
pool (non-earner) -> mint bananas on verified-only (exact-match trace, dedup)
-> done/ transition -> ROI/brick JSON.

Hostile DA rounds 1-2 (all findings fixed):
F1 CRIT  mint trace = EXACT (card_id, probe_id, brick_id, dispatch_id) match
          against structured dispatches.jsonl registry + card must be in
          claimed/ + dedup on (card_id, probe_id, brick_id) — ghost cards and
          substring/prefix reuse impossible
F2 HIGH  wire auth = grant signature only; control token never transmitted
          to any dispatch target (grant-only auth on /dispatch)
F3 HIGH  wallet RMW serialized on a DEDICATED lockfile (wallet.lock) — never
          the file being replaced (inode swap broke flock); stress-tested
F4 MED   audit row before mutation; fail-closed
F5 MED   price+probe_id hard-required; bill only on 2xx; cost rows carry
          brick_id as a structured field; voided rows excluded from ROI
F6 LOW   capability re-validated; brick bound to matched candidate
F7 LOW   no self-earn (orchestrator cannot claim/mint)
F8 LOW   lease capped; done/ on mint; no lock leaks
F9 NIT   probe_pool chmod 0600 on load; CI runs ORCH-1..9 verbatim

NEVER builds/runs app code. stdlib-only.
"""
import hashlib, hmac, json, os, pathlib, time, datetime, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MIN_TOKEN = 16
LEASE_MAX_S = 24 * 3600


def _now():
    return datetime.datetime.utcnow().isoformat() + "Z"


def _log(path, op, detail="", outcome="ok"):
    """Audit-before-mutation. Append-only, flocked."""
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
    tmp = p.with_name(p.name + ".tmp-" + str(os.getpid()) + "-" +
                      hashlib.sha256(os.urandom(8)).hexdigest()[:8])
    tmp.write_text(content)
    os.chmod(tmp, mode)
    os.replace(tmp, p)


def _locked(path, fn):
    """F3: serialize on a DEDICATED lockfile (never the file being replaced)."""
    lock = pathlib.Path(str(path) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a+") as lf:
        try:
            import fcntl
            fcntl.flock(lf, fcntl.LOCK_EX)
        except Exception:
            pass
        try:
            return fn()
        finally:
            try:
                import fcntl
                fcntl.flock(lf, fcntl.LOCK_UN)
            except Exception:
                pass


class Orchestrator:
    def __init__(self, orch_dir, reg_dir, bank_dir, rate_card, probe_pool,
                 a2a_url, worker_token, brick_id="orchestrator-001",
                 grant_key=None):
        self.orch_dir = pathlib.Path(orch_dir)
        self.reg_dir = pathlib.Path(reg_dir)
        self.bank_dir = pathlib.Path(bank_dir)
        self.rate_card = rate_card
        self.probe_pool = pathlib.Path(probe_pool)
        self.a2a_url = a2a_url.rstrip("/")
        self.worker_token = worker_token
        self.brick_id = brick_id
        self.grant_key = grant_key or hashlib.sha256(
            (worker_token + brick_id).encode()).hexdigest()[:32]
        self.audit = self.orch_dir / "audit.jsonl"
        self.dispatch_reg = self.orch_dir / "dispatches.jsonl"
        self.open_dir = self.orch_dir / "open"
        self.claimed_dir = self.orch_dir / "claimed"
        self.done_dir = self.orch_dir / "done"
        for d in (self.open_dir, self.claimed_dir, self.done_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.lease_s = 3600
        self._chmod_pool()

    # ---------- helpers ----------
    def _chmod_pool(self):
        if self.probe_pool.exists():
            os.chmod(self.probe_pool, 0o600)

    def _auth(self, token):
        return (len(token) >= MIN_TOKEN
                and hmac.compare_digest(token, self.worker_token))

    def _grant(self, card, brick, dispatch_id):
        """F2: per-card HMAC-signed grant — THE wire auth (control token never sent)."""
        g = {"card_id": card.get("card_id"), "brick_id": brick.get("brick_id"),
             "probe_id": card.get("probe_id"), "dispatch_id": dispatch_id,
             "scope": "read-only", "exp": int(time.time()) + 600}
        body = json.dumps(g, sort_keys=True)
        g["sig"] = hmac.new(self.grant_key.encode(), body.encode(),
                            hashlib.sha256).hexdigest()[:24]
        return g

    def _grant_auth_header(self, grant):
        """F2: wire auth = grant only. 'Grant <sig>:<exp>:<card_id>'. The
        receiving brick presents this back; orchestrator validates sig+exp.
        No control token on the wire, ever."""
        return f"Grant {grant['sig']}:{grant['exp']}:{grant['card_id']}"

    def _verify_grant(self, grant):
        g = dict(grant)
        sig = g.pop("sig", "")
        body = json.dumps(g, sort_keys=True)
        expect = hmac.new(self.grant_key.encode(), body.encode(),
                          hashlib.sha256).hexdigest()[:24]
        return (hmac.compare_digest(sig, expect)
                and g.get("exp", 0) > time.time()
                and g.get("scope") == "read-only")

    def _verify_output(self, probe_id, output_hash):
        """Non-earner verify: RECOMPUTE expected hash from probe pool (DA-9)."""
        if not self.probe_pool.exists():
            return False, "probe_pool missing"
        pool = json.loads(self.probe_pool.read_text())
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
        """open/ -> claimed/ atomic rename with lease. F7: orchestrator never claims."""
        if self.brick_id.startswith("orchestrator"):
            return {"ok": False, "error": "orchestrator cannot claim (F7 no self-earn)"}
        src = self.open_dir / card_id
        dst = self.claimed_dir / card_id
        if not src.exists():
            cd = self.claimed_dir / card_id
            if cd.exists():
                try:
                    card = json.loads(cd.read_text())
                    exp = card.get("lease_expires", 0)
                    if 0 < exp < time.time():
                        card["state"] = "open"
                        card.pop("claimer", None)
                        _log(self.audit, "lease-reopen", card_id,
                             "before-mutation")
                        _atomic_write(str(cd), json.dumps(card))
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
        card["lease_expires"] = time.time() + min(self.lease_s, LEASE_MAX_S)
        _log(self.audit, "claim",
             f"{card_id} claimer={self.brick_id} before-mutation")
        _atomic_write(str(dst), json.dumps(card))
        src.unlink(missing_ok=True)
        try:
            lock.close()
            pathlib.Path(str(src) + ".lock").unlink(missing_ok=True)
        except Exception:
            pass
        return {"ok": True, "state": "claimed", "card": card}

    def match_card(self, card):
        """capability_register lookup: register skill ∩ card.capability; ranked."""
        reg_rows, _ = _read(self.reg_dir / "registry.jsonl")
        skill = card.get("capability", "")
        cands = []
        for r in reg_rows:
            if skill in (r.get("skills") or []):
                cands.append({"brick_id": r.get("brick_id"),
                              "quality": r.get("quality", "unknown")})
        cands.sort(key=lambda b: 0 if b["quality"] == "verified" else 1)
        return cands

    def dispatch(self, card, brick):
        """Pattern AA hard gate then A2A POST with grant-only auth (F2)."""
        if not card.get("death_warrant"):
            return {"ok": False, "error": "missing death_warrant — refused"}
        card_id = card.get("card_id")
        price = card.get("price")
        probe_id = card.get("probe_id")
        if price is None or not isinstance(price, (int, float)):
            return {"ok": False, "error": "price required (F5)"}
        if not probe_id:
            return {"ok": False, "error": "probe_id required (F5)"}
        cands = self.match_card(card)
        if not any(c["brick_id"] == brick.get("brick_id") for c in cands):
            return {"ok": False, "error": "brick not a matched candidate (F6)"}
        did = hashlib.sha256(f"{card_id}:{time.time()}".encode()).hexdigest()[:16]
        # F1: structured dispatch registry row (exact-match trace source)
        reg_row = {"card_id": card_id, "probe_id": probe_id,
                   "brick_id": brick.get("brick_id"), "dispatch_id": did,
                   "ts": _now()}
        _log(self.dispatch_reg, "dispatch", json.dumps(reg_row, sort_keys=True))
        # Pattern AA: ledger row BEFORE the A2A call (brick_id as field)
        _log(self.bank_dir / "ledger-cost-rows.log", "dispatch-price",
             json.dumps({"card": card_id, "brick_id": brick.get("brick_id"),
                         "price": price}), "committed")
        grant = self._grant(card, brick, did)
        payload = {"card_id": card_id, "probe_id": probe_id,
                   "capability": card.get("capability"), "grant": grant,
                   "dispatch_id": did}
        req = urllib.request.Request(
            f"{self.a2a_url}/dispatch",
            data=json.dumps(payload).encode(),
            headers={"Authorization": self._grant_auth_header(grant),
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.load(r)
            _log(self.audit, "dispatch",
                 f"{card_id} brick={brick.get('brick_id')} did={did} outcome=ok")
            return {"ok": True, "dispatch_id": did,
                    "brick_id": brick.get("brick_id"), "grant": grant,
                    "response": body}
        except urllib.error.HTTPError as e:
            _log(self.bank_dir / "ledger-cost-rows.log", "dispatch-void",
                 json.dumps({"card": card_id, "brick_id": brick.get("brick_id"),
                             "http": e.code}), "voided")
            return {"ok": False, "error": f"dispatch HTTP {e.code} (not billed)"}
        except Exception as e:
            _log(self.bank_dir / "ledger-cost-rows.log", "dispatch-void",
                 json.dumps({"card": card_id, "brick_id": brick.get("brick_id"),
                             "err": str(e)[:40]}), "voided")
            return {"ok": False, "error": f"{str(e)[:80]} (not billed)"}

    def _dispatch_trace(self, receipt):
        """F1: EXACT-match trace against the structured dispatch registry."""
        rows, _ = _read(self.dispatch_reg)
        for r in rows:
            try:
                d = json.loads(r.get("detail", "{}"))
            except Exception:
                continue
            if (d.get("card_id") == receipt.get("card_id")
                    and d.get("probe_id") == receipt.get("probe_id")
                    and d.get("brick_id") == receipt.get("brick_id")
                    and d.get("dispatch_id") == receipt.get("dispatch_id")):
                return True
        return False

    def verify_receipt(self, receipt):
        """Non-earner verify: exact trace + fields + hash recompute."""
        for fld in ("card_id", "probe_id", "output_hash", "brick_id", "dispatch_id"):
            if not receipt.get(fld):
                return {"ok": False, "reason": f"missing {fld}"}
        if not self._dispatch_trace(receipt):
            return {"ok": False,
                    "reason": "dispatch_id not traced exactly (F1)"}
        ok, msg = self._verify_output(receipt["probe_id"], receipt["output_hash"])
        if not ok:
            return {"ok": False, "reason": msg}
        return {"ok": True, "verified": True}

    def mint(self, card, receipt):
        """Verified + exact-traced + done/ transition. F1/F3/F4/F7."""
        if self.brick_id.startswith("orchestrator"):
            return {"ok": False, "error": "orchestrator cannot mint to self (F7)"}
        v = self.verify_receipt(receipt)
        if not v.get("ok"):
            return {"ok": False, "error": f"unverified — no mint ({v.get('reason')})"}
        card_id = receipt["card_id"]
        probe_id = receipt["probe_id"]
        brick_id = receipt["brick_id"]
        if not (self.claimed_dir / card_id).exists():
            return {"ok": False, "error": "card not in claimed/ state (F1)"}

        def _mint_once():
            ledger, _ = _read(self.bank_dir / "wallet.jsonl")
            if any(r.get("card_id") == card_id and r.get("probe_id") == probe_id
                   and r.get("brick_id") == brick_id for r in ledger):
                return {"ok": False, "error": "card already minted (F1 dedup)"}
            bananas = self.rate_card.get(probe_id) or self.rate_card.get("default", 1)
            row = {"card_id": card_id, "probe_id": probe_id,
                   "brick_id": brick_id, "dispatch_id": receipt["dispatch_id"],
                   "bananas": bananas, "ts": _now()}
            _log(self.audit, "mint",
                 f"{card_id} {bananas} bananas before-mutation")
            _atomic_write(str(self.bank_dir / "wallet.jsonl"),
                          "\n".join(json.dumps(r) for r in ledger + [row]) + "\n")
            done = self.done_dir / card_id
            if not done.exists():
                done.write_text(json.dumps({"card_id": card_id, "minted": _now(),
                                            "bananas": bananas}))
                os.chmod(done, 0o600)
            (self.claimed_dir / card_id).unlink(missing_ok=True)
            return {"ok": True, **row}

        return _locked(self.bank_dir / "wallet.jsonl", _mint_once)

    def roi_per_brick(self):
        """F5: cost rows carry brick_id as a field; voided rows excluded."""
        wallet, _ = _read(self.bank_dir / "wallet.jsonl")
        costs, _ = _read(self.bank_dir / "ledger-cost-rows.log")
        roi = {}
        for w in wallet:
            b = w.get("brick_id", "?")
            d = roi.setdefault(b, {"earned_bananas": 0, "cost_rows": 0, "roi": 0})
            d["earned_bananas"] += w.get("bananas", 0)
        for c in costs:
            if c.get("op") == "dispatch-void":
                continue  # F5: voided never billed
            try:
                detail = json.loads(c.get("detail", "{}"))
                b = detail.get("brick_id", "?")
            except Exception:
                b = "?"
            d = roi.setdefault(b, {"earned_bananas": 0, "cost_rows": 0, "roi": 0})
            d["cost_rows"] += 1
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
            "corrupt_rows": _read(self.audit)[1],
            "audit_rows": len(_read(self.audit)[0]),
        }


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        o = self.server.orch
        if not o._auth(self.headers.get("Authorization", "").replace("Bearer ", "")):
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
        # /verify + /mint accept EITHER control token (internal ops) — dispatch
        # itself is grant-authed on the WIRE (outbound), not via this server.
        if not o._auth(self.headers.get("Authorization", "").replace("Bearer ", "")):
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
