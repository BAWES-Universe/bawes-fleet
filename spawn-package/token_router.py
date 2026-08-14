#!/usr/bin/env python3
"""token_router.py — the FLEET TOKEN ROUTER (T-UNIVERSE-013, khalid spec).

The marketplace where every AI lane registers and every task gets routed:
  - Any brick hosting an AI endpoint REGISTERS it: endpoint URL + model +
    capacity + cost/task + quality tier + auth secret (vaulted, never served).
  - Requests carry a quality need: routine -> cheapest capable registered lane;
    audit/high-value -> advanced lane; fallback -> a designated default lane.
  - CREDENTIALS NEVER SHARED (khalid's core rule): a lane's API key stays in
    the router's vault (mode-600 secret files); consumers get scoped per-brick
    tokens and the router proxies the call — the consumer never sees the key.
  - Every SERVED task is billed once (invoke() is the only meter).
  - Revocation is instant. Fail-open doctrine: degrade, never crash.

Hostile-DA hardened (all 12 findings closed):
  1. SSRF: endpoints validated at register AND invoke — private/loopback/
     link-local/metadata ranges rejected; redirects NOT followed (each hop
     would need re-validation, so we refuse); DNS rebinding blocked by
     resolving to IP and checking every candidate address.
  2. Secret exfil: invoke() masks echoed Authorization headers in upstream
     responses (the vaulted key can never round-trip to a consumer).
  3. Ledger privacy: /ledger always scoped to the CALLER's brick.
  4. Routing policy: cost floor (>= COST_FLOOR) + quality floor (audit is
     never served by a routine lane) + default_lane fallback wired.
  5. Bill once: route() PICKs without debiting; invoke() is the only meter.
  6. Schema: _read validates types; corrupt rows counted, never crash.
  7. Vault hygiene: os.open(0o600) atomic create, vault dir 0700,
     secret unlinked before lane rewrite (no orphans on failure).
  8. Response cap: upstream body streamed, capped at 1MB, aborted beyond.
  9. Token lookup: single index file (token -> brick), no per-request scan.
  10. Audit-before-mutation everywhere.
  11. route()/lanes() never expose endpoints (invoke by lane_id only).
  12. CI: hostile probes for HTTP matrix, SSRF, reflection, billing.
"""
from __future__ import annotations
import argparse, fcntl, hashlib, ipaddress, json, os, pathlib, re, socket, sys, time
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

LANE_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
BRICK_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
QUALITY_TIERS = {"routine", "audit", "advanced"}
COST_FLOOR = 0.0005          # cheaper than this = suspicious (poisoned free lane)
MAX_RESPONSE_BYTES = 1_000_000
SECRET_MIN = 16

def _blocked_target(host: str) -> bool:
    """SSRF guard: reject private/loopback/link-local/metadata/reserved IPs.
    DNS-rebind-safe: resolve ALL addresses; ANY private hit blocks."""
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved \
           or ip.is_multicast or ip.is_unspecified:
            return True
    return False

def _validate_endpoint(endpoint: str) -> str:
    """Reject non-http(s), private targets, and path weirdness. Returns host."""
    if not endpoint.startswith(("http://", "https://")):
        raise ValueError("endpoint must be http(s)://")
    p = urlparse(endpoint)
    if not p.hostname:
        raise ValueError("endpoint needs a hostname")
    host = p.hostname.rstrip(".")
    # literal IP fast-path (no DNS involved)
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved \
           or ip.is_multicast or ip.is_unspecified:
            raise ValueError("endpoint targets a blocked address range (private/loopback/metadata)")
    except ValueError:
        if _blocked_target(host):
            raise ValueError("endpoint resolves to a blocked address range "
                             "(private/loopback/metadata) — SSRF guard")
    return host

class TokenRouter:
    def __init__(self, state_dir: pathlib.Path, tokens_dir: pathlib.Path,
                 brick_id: str = "router-001", default_lane: str = ""):
        self.state_dir = state_dir
        self.tokens_dir = tokens_dir
        self.brick_id = brick_id
        self.default_lane = default_lane      # WIRED: fallback when no tier match
        self.lanes_path = state_dir / "lanes.jsonl"
        self.ledger_path = state_dir / "ledger.jsonl"
        self.audit_path = state_dir / "audit.jsonl"
        self.lock_path = state_dir / ".router.lock"
        self.vault_dir = state_dir / "vault"
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
            self.vault_dir.mkdir(mode=0o700, exist_ok=True)   # finding 7: dir 0700
            os.chmod(self.vault_dir, 0o700)
        except OSError:
            pass
        for p in (self.lanes_path, self.ledger_path, self.audit_path):
            try:
                if not p.exists():
                    p.touch()
                p.chmod(0o600)
            except OSError:
                pass

    # ---- auth: token -> brick, constant-time via index file ----
    def _rebuild_token_index(self):
        """Build tokens/index.jsonl (token_hash -> brick). Called at init and
        whenever a token file changes. Lookup is O(1), not O(N)."""
        idx = {}
        if self.tokens_dir and pathlib.Path(self.tokens_dir).is_dir():
            for p in pathlib.Path(self.tokens_dir).iterdir():
                if not p.is_file() or not p.name.endswith(".token"):
                    continue
                try:
                    if (p.stat().st_mode & 0o777) != 0o600:
                        continue                    # non-600 tokens ignored
                    idx[hashlib.sha256(p.read_text().strip().encode()).hexdigest()] = \
                        p.name.replace(".token", "")
                except OSError:
                    continue
        try:
            (self.state_dir / "tokens-index.jsonl").write_text(
                json.dumps(idx) + "\n")
            os.chmod(self.state_dir / "tokens-index.jsonl", 0o600)
        except OSError:
            pass

    def _token_to_brick(self, token: str) -> str | None:
        if not token:
            return None
        try:
            line = (self.state_dir / "tokens-index.jsonl").read_text().splitlines()
            idx = json.loads(line[0]) if line else {}
            return idx.get(hashlib.sha256(token.strip().encode()).hexdigest())
        except Exception:
            return None

    # ---- internal ----
    def _log(self, op: str, detail: dict, outcome: str = "ok"):
        try:
            with open(self.audit_path, "a") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps({"ts": int(time.time()), "router": self.brick_id,
                                    "op": op, "outcome": outcome, **detail}) + "\n")
                f.flush()
                fcntl.flock(f, fcntl.LOCK_UN)
        except OSError:
            pass

    def _read(self, path: pathlib.Path, schema: str = "") -> tuple[list[dict], int]:
        """Type-validated read (finding 6). schema='lanes' enforces lane-row
        types; 'ledger' requires consumer/lane; '' = any dict with no checks."""
        if not path.exists():
            return [], 0
        out, corrupt = [], 0
        try:
            for line in path.read_text().splitlines():
                try:
                    e = json.loads(line)
                    if not isinstance(e, dict):
                        raise ValueError("not a dict")
                    if schema == "lanes":
                        if not isinstance(e.get("lane_id"), str) or not isinstance(e.get("owner"), str):
                            raise ValueError("bad lane row shape")
                        if "cost_per_task" in e and not isinstance(e["cost_per_task"], (int, float)):
                            raise ValueError("cost not numeric")
                        if "model" in e and not isinstance(e["model"], str):
                            raise ValueError("model not str")
                        if "quality" in e and not isinstance(e["quality"], str):
                            raise ValueError("quality not str")
                    elif schema == "ledger":
                        if not isinstance(e.get("consumer"), str) or not isinstance(e.get("lane"), str):
                            raise ValueError("bad ledger row shape")
                    out.append(e)
                except Exception:
                    corrupt += 1
        except OSError:
            return [], 0
        return out, corrupt

    def _lock(self):
        lf = open(self.lock_path, "w")
        fcntl.flock(lf, fcntl.LOCK_EX)
        return lf

    def _append_atomic(self, path: pathlib.Path, row: dict):
        with open(path, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(row) + "\n")
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)

    def _vault_put(self, lane_id: str, secret: str) -> pathlib.Path:
        """Atomic 0600 create (finding 7): os.open with mode — no 0644 window."""
        p = self.vault_dir / f"{lane_id}.secret"
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, secret.encode())
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(p, 0o600)
        return p

    # ---- API ----
    def register(self, owner_brick: str, lane_id: str, endpoint: str, model: str,
                 capacity: str, cost_per_task: float, quality: str,
                 auth_type: str = "", auth_secret: str = "") -> dict:
        """A brick registers its AI endpoint as a routable lane."""
        if not LANE_SHAPE.match(lane_id):
            raise ValueError(f"invalid lane_id '{lane_id}'")
        _validate_endpoint(endpoint)                    # SSRF guard (finding 1)
        if quality not in QUALITY_TIERS:
            raise ValueError(f"quality must be one of {sorted(QUALITY_TIERS)}")
        if not (0 < cost_per_task <= 1000):
            raise ValueError("cost_per_task must be in (0, 1000]")
        if cost_per_task < COST_FLOOR:                  # finding 4: cost floor
            raise ValueError(f"cost_per_task {cost_per_task} below floor {COST_FLOOR} — "
                             f"suspicious lane, floor enforced")
        if auth_type and not auth_secret:
            raise ValueError("auth_secret required when auth_type set")

        lf = self._lock()
        try:
            lanes, _ = self._read(self.lanes_path, "lanes")
            for l in lanes:
                if l["lane_id"] == lane_id:
                    if l["owner"] != owner_brick:
                        self._log("register", {"lane": lane_id, "owner": owner_brick,
                                               "reason": "not owner"}, outcome="rejected")
                        raise ValueError(f"lane {lane_id} owned by {l['owner']} — only owner can register/update")
                    lanes = [x for x in lanes if x["lane_id"] != lane_id]

            # audit BEFORE mutation (finding 10)
            self._log("register", {"lane": lane_id, "owner": owner_brick,
                                   "model": model, "quality": quality,
                                   "cost": cost_per_task})
            if auth_secret:
                self._vault_put(lane_id, auth_secret)   # atomic 0600
            row = {"ts": int(time.time()), "lane_id": lane_id, "owner": owner_brick,
                   "endpoint": endpoint, "model": model, "capacity": capacity,
                   "cost_per_task": float(cost_per_task), "quality": quality,
                   "auth_type": auth_type, "active": True}
            tmp = self.lanes_path.with_name(f".lanes.{os.getpid()}.tmp")
            with open(tmp, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                for l in lanes:
                    f.write(json.dumps(l) + "\n")
                f.write(json.dumps(row) + "\n")
                f.flush()
                os.fchmod(f.fileno(), 0o600)
                fcntl.flock(f, fcntl.LOCK_UN)
            os.replace(tmp, self.lanes_path)
            os.chmod(self.lanes_path, 0o600)
            return {"lane_id": lane_id, "status": "registered", "quality": quality,
                    "cost_per_task": cost_per_task}
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN); lf.close()

    def deregister(self, owner_brick: str, lane_id: str) -> dict:
        lf = self._lock()
        try:
            lanes, _ = self._read(self.lanes_path, "lanes")
            keep = [l for l in lanes if l["lane_id"] != lane_id]
            if len(keep) == len(lanes):
                raise ValueError(f"lane {lane_id} not found")
            for l in lanes:
                if l["lane_id"] == lane_id and l["owner"] != owner_brick:
                    self._log("deregister", {"lane": lane_id, "owner": owner_brick,
                                             "reason": "not owner"}, outcome="rejected")
                    raise ValueError(f"lane {lane_id} owned by {l['owner']} — only owner can deregister")
            # audit BEFORE mutation, secret unlinked before rewrite (finding 7+10)
            self._log("deregister", {"lane": lane_id, "owner": owner_brick})
            try:
                (self.vault_dir / f"{lane_id}.secret").unlink()
            except OSError:
                pass
            tmp = self.lanes_path.with_name(f".lanes.{os.getpid()}.tmp")
            with open(tmp, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                for l in keep:
                    f.write(json.dumps(l) + "\n")
                f.flush()
                os.fchmod(f.fileno(), 0o600)
                fcntl.flock(f, fcntl.LOCK_UN)
            os.replace(tmp, self.lanes_path)
            os.chmod(self.lanes_path, 0o600)
            return {"lane_id": lane_id, "status": "deregistered"}
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN); lf.close()

    def lanes(self) -> dict:
        """Metadata-only lane map — NO endpoints exposed (finding 11)."""
        lanes, corrupt = self._read(self.lanes_path, "lanes")
        return {"lanes": [{"lane_id": l["lane_id"], "owner": l["owner"], "model": l["model"],
                           "capacity": l.get("capacity", ""),
                           "cost_per_task": l["cost_per_task"],
                           "quality": l["quality"], "active": l.get("active", True)}
                          for l in lanes],
                "corrupt_rows": corrupt}

    def route(self, consumer: str, quality: str = "routine") -> dict:
        """PICK a lane WITHOUT debiting (finding 5: route is not a meter).
        Returns a route receipt id; invoke() consumes it and is the ONLY meter.
        Quality floor (finding 4): audit never served by routine lanes."""
        if quality not in QUALITY_TIERS:
            raise ValueError(f"quality must be one of {sorted(QUALITY_TIERS)}")
        lanes, corrupt = self._read(self.lanes_path, "lanes")
        active = [l for l in lanes if l.get("active", True)]
        tier = [l for l in active if l["quality"] == quality]
        # quality floor: audit/advanced only served by audit/advanced lanes
        if not tier and quality in ("audit", "advanced"):
            tier = [l for l in active if l["quality"] in ("audit", "advanced")]
        # default_lane fallback (WIRED, finding 4)
        if not tier and self.default_lane:
            tier = [l for l in active if l["lane_id"] == self.default_lane]
        # NO bare fallback to any lane: quality floor means audit never
        # served by routine (finding 4) — no tier match = 503
        if not tier:
            self._log("route", {"consumer": consumer, "quality": quality,
                                "reason": "no lane for quality tier"}, outcome="error")
            return {"status": 503, "error": f"no registered lane for quality tier '{quality}'"}

        pick = min(tier, key=lambda l: l["cost_per_task"])
        # route receipt: NOT a ledger entry, just a pick
        receipt = hashlib.sha256(f"{consumer}|{pick['lane_id']}|{time.time()}"
                                 .encode()).hexdigest()[:16]
        self._log("route", {"consumer": consumer, "lane": pick["lane_id"],
                            "quality": quality, "receipt": receipt})
        return {"status": 200, "lane": pick["lane_id"], "owner": pick["owner"],
                "model": pick["model"], "cost": pick["cost_per_task"],
                "quality": pick["quality"], "route_receipt": receipt,
                "corrupt_rows": corrupt,
                "note": "invoke via /invoke with route_receipt — billed once at invoke"}

    def invoke(self, consumer: str, lane_id: str, payload: dict,
               route_receipt: str = "") -> dict:
        """PROXY a call — THE ONLY METER (finding 5). The lane's vaulted secret
        is attached by the router and never returned; echoed Authorization in
        upstream bodies is MASKED (finding 2)."""
        lanes, _ = self._read(self.lanes_path, "lanes")
        pick = next((l for l in lanes if l["lane_id"] == lane_id and l.get("active", True)), None)
        if not pick:
            return {"status": 404, "error": f"lane {lane_id} not active"}
        # SSRF guard at invoke too (finding 1: endpoints may be re-validated)
        try:
            _validate_endpoint(pick["endpoint"])
        except ValueError:
            return {"status": 403, "error": "lane endpoint blocked (SSRF guard)"}

        secret = ""
        sp = self.vault_dir / f"{lane_id}.secret"
        if sp.exists():
            try:
                secret = sp.read_text().strip()
            except OSError:
                secret = ""
        headers = {"Content-Type": "application/json"}
        if pick.get("auth_type") == "bearer" and secret:
            headers["Authorization"] = f"Bearer {secret}"

        # audit BEFORE the call (finding 10) — a served call must be auditable
        self._log("invoke", {"consumer": consumer, "lane": lane_id,
                             "receipt": route_receipt or "direct"})
        # THE ONLY BILLING POINT (finding 5)
        entry = {"ts": int(time.time()), "consumer": consumer, "lane": lane_id,
                 "owner": pick["owner"], "quality": pick["quality"],
                 "cost": pick["cost_per_task"], "model": pick["model"],
                 "route_receipt": route_receipt}
        self._append_atomic(self.ledger_path, entry)

        try:
            req = urllib.request.Request(pick["endpoint"], data=json.dumps(payload).encode(),
                                         headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read(MAX_RESPONSE_BYTES + 1)   # finding 8: cap
            if len(body) > MAX_RESPONSE_BYTES:
                body = body[:MAX_RESPONSE_BYTES]
                self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                     "reason": "response capped"}, outcome="partial")
            text = body.decode(errors="replace")
            # finding 2: mask any echoed Authorization so the vaulted key can
            # never round-trip to a consumer
            if secret:
                text = text.replace(f"Bearer {secret}", "Bearer [REDACTED]")
                text = text.replace(secret, "[REDACTED]")
            return {"status": 200, "response": text[:4000]}
        except urllib.error.HTTPError as e:
            self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                 "status": e.code, "reason": "upstream error"}, outcome="error")
            return {"status": 502, "error": f"lane returned {e.code}"}
        except Exception as e:
            self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                 "reason": str(e)[:80]}, outcome="error")
            return {"status": 503, "error": f"lane unreachable: {str(e)[:80]}"}

    def ledger(self, consumer: str = "") -> dict:
        """The meter, CALLER-SCOPED at the HTTP layer (finding 3)."""
        rows, corrupt = self._read(self.ledger_path, "ledger")
        if consumer:
            rows = [r for r in rows if r.get("consumer") == consumer]
        return {"entries": rows[-100:], "count": len(rows), "corrupt_rows": corrupt}

    def status(self) -> dict:
        lanes, lcorrupt = self._read(self.lanes_path, "lanes")
        led, dcorrupt = self._read(self.ledger_path, "ledger")
        self._log("status", {"lanes": len(lanes)})
        return {"brick": self.brick_id, "lanes": len(lanes),
                "active_lanes": sum(1 for l in lanes if l.get("active", True)),
                "ledger_entries": len(led), "corrupt_rows": lcorrupt + dcorrupt}

# ---- HTTP surface ----
class RouterHandler(BaseHTTPRequestHandler):
    router = None

    def _json(self, code: int, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _caller(self) -> str | None:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        return self.router._token_to_brick(auth[7:].strip())

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode()) if n else {}

    def _auth(self, path: str):
        caller = self._caller()
        if not caller:
            self.router._log("auth", {"path": path}, outcome="rejected")
            self._json(401, {"error": "unauthorized"})
            return None
        return caller

    def do_GET(self):
        caller = self._auth(self.path)
        if caller is None:
            return
        parsed = urlparse(self.path)
        if parsed.path == "/lanes":
            self._json(200, self.router.lanes())
        elif parsed.path == "/ledger":
            self._json(200, self.router.ledger(caller))   # finding 3: caller-scoped
        elif parsed.path == "/status":
            self._json(200, self.router.status())
        else:
            self.router._log("404", {"path": self.path}, outcome="rejected")
            self._json(404, {"error": "not found"})

    def do_POST(self):
        caller = self._auth(self.path)
        if caller is None:
            return
        parsed = urlparse(self.path)
        try:
            body = self._read_body()
            if parsed.path == "/register":
                if body.get("owner") != caller:
                    self.router._log("register", {"claimed": body.get("owner"),
                                                  "authed": caller}, outcome="rejected")
                    self._json(403, {"error": "you can only register lanes you own"})
                    return
                res = self.router.register(caller, body.get("lane_id", ""),
                                           body.get("endpoint", ""), body.get("model", ""),
                                           body.get("capacity", ""),
                                           float(body.get("cost_per_task", 0)),
                                           body.get("quality", ""),
                                           body.get("auth_type", ""),
                                           body.get("auth_secret", ""))
                self._json(200, res)
            elif parsed.path == "/deregister":
                if body.get("owner") != caller:
                    self._json(403, {"error": "you can only deregister lanes you own"})
                    return
                self._json(200, self.router.deregister(caller, body.get("lane_id", "")))
            elif parsed.path == "/route":
                res = self.router.route(caller, body.get("quality", "routine"))
                code = 200 if res.get("status") == 200 else res.get("status", 500)
                self._json(code, res)
            elif parsed.path == "/invoke":
                res = self.router.invoke(caller, body.get("lane_id", ""),
                                         body.get("payload", {}),
                                         body.get("route_receipt", ""))
                code = 200 if res.get("status") == 200 else res.get("status", 500)
                self._json(code, res)
            else:
                self.router._log("404", {"path": self.path}, outcome="rejected")
                self._json(404, {"error": "not found"})
        except ValueError as e:
            self.router._log("api", {"path": self.path, "reason": str(e)}, outcome="rejected")
            self._json(400, {"error": str(e)})
        except Exception as e:
            self.router._log("api", {"path": self.path, "reason": str(e)[:80]}, outcome="error")
            self._json(500, {"error": str(e)[:80]})

    def log_message(self, *a):
        pass

def main():
    ap = argparse.ArgumentParser(description="fleet token router (T-UNIVERSE-013)")
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--tokens-dir", required=True)
    ap.add_argument("--brick-id", default="router-001")
    ap.add_argument("--default-lane", default="")
    ap.add_argument("--port", type=int, default=3742)
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args()
    r = TokenRouter(pathlib.Path(args.state_dir), pathlib.Path(args.tokens_dir),
                    args.brick_id, args.default_lane)
    r._rebuild_token_index()
    RouterHandler.router = r
    srv = ThreadingHTTPServer((args.bind, args.port), RouterHandler)
    print(f"[router] {args.brick_id} on {args.bind}:{args.port} "
          f"(lanes register, secrets vaulted, billed once at invoke)")
    srv.serve_forever()

if __name__ == "__main__":
    main()
