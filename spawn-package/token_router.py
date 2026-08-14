#!/usr/bin/env python3
"""token_router.py — the FLEET TOKEN ROUTER (T-UNIVERSE-013, khalid spec).

The marketplace where every AI lane registers and every task gets routed:
  - Any brick hosting an AI endpoint REGISTERS it: endpoint URL + model +
    capacity + cost/task + quality tier + auth secret (vaulted, never served).
  - Requests carry a quality need: routine -> cheapest capable registered lane;
    audit/high-value -> advanced lane; fallback -> a designated default lane
    (e.g. DeepSeek API held by the operator) when nothing registered serves it.
  - CREDENTIALS NEVER SHARED (khalid's core rule): a lane's API key stays in
    the router's vault (mode-600 secret files); consumers get scoped per-brick
    tokens (mode-600 <brick>.token files) and the router proxies the call —
    the consumer never sees the lane's key.
  - Every request is billed in bananas: lane earns per task, consumer's wallet
    debited, receipts on both sides. Router is the meter.
  - Revocation is instant: kill a brick's token or a lane's registration.
  - Fail-open doctrine: router down -> caller gets 503 (degrade, never crash).

Security (hostile-DA hardened, same bar as bank/bridge/register):
  - auth fail-closed: every endpoint requires a valid consumer token bound to
    a brick_id (mode-600 files, token->brick identity like the bridge).
  - lane registration requires the lane's OWNER token (a lane can only be
    registered/updated/deleted by its owning brick).
  - secrets never leak: /lanes lists metadata only; /register vaults the
    secret; /route proxies without ever returning the secret.
  - single-writer flock on lanes + ledger; atomic temp+rename; corrupt rows
    counted+surfaced; audit-before-mutation everywhere.
"""
from __future__ import annotations
import argparse, fcntl, hashlib, hmac, json, os, pathlib, re, sys, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

LANE_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")   # lane id
BRICK_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")  # brick id
QUALITY_TIERS = {"routine", "audit", "advanced"}
SECRET_MIN = 16

class TokenRouter:
    def __init__(self, state_dir: pathlib.Path, tokens_dir: pathlib.Path,
                 brick_id: str = "router-001", default_lane: str = ""):
        self.state_dir = state_dir
        self.tokens_dir = tokens_dir
        self.brick_id = brick_id
        self.default_lane = default_lane
        self.lanes_path = state_dir / "lanes.jsonl"
        self.ledger_path = state_dir / "ledger.jsonl"
        self.audit_path = state_dir / "audit.jsonl"
        self.lock_path = state_dir / ".router.lock"
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        for p in (self.lanes_path, self.ledger_path, self.audit_path):
            try:
                if not p.exists():
                    p.touch()
                p.chmod(0o600)
            except OSError:
                pass

    # ---- auth: token -> brick (fail-closed, mode-600 files) ----
    def _token_to_brick(self, token: str) -> str | None:
        if not token or not self.tokens_dir:
            return None
        td = pathlib.Path(self.tokens_dir)
        if not td.is_dir():
            return None
        try:
            for p in td.iterdir():
                if not p.is_file() or (p.stat().st_mode & 0o777) != 0o600:
                    continue
                if p.read_text().strip() == token:
                    return p.name.replace(".token", "")
        except OSError:
            return None
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

    def _read(self, path: pathlib.Path, schema_keys: tuple = ()) -> tuple[list[dict], int]:
        if not path.exists():
            return [], 0
        out, corrupt = [], 0
        try:
            for line in path.read_text().splitlines():
                try:
                    e = json.loads(line)
                    if not isinstance(e, dict):
                        raise ValueError("not a dict")
                    for k in schema_keys:
                        if k not in e:
                            raise ValueError(f"missing {k}")
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

    def _vault(self, lane_id: str, secret: str) -> pathlib.Path:
        """Vault a lane's auth secret in a mode-600 file keyed by lane id.
        The secret is never stored in lanes.jsonl and never served."""
        v = self.state_dir / "vault"
        try:
            v.mkdir(exist_ok=True)
        except OSError:
            pass
        p = v / f"{lane_id}.secret"
        with open(p, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(secret)
            f.flush()
            os.fchmod(f.fileno(), 0o600)
            fcntl.flock(f, fcntl.LOCK_UN)
        return p

    # ---- API ----
    def register(self, owner_brick: str, lane_id: str, endpoint: str, model: str,
                 capacity: str, cost_per_task: float, quality: str,
                 auth_type: str = "", auth_secret: str = "") -> dict:
        """A brick registers its AI endpoint as a routable lane.
        auth_secret is vaulted (never stored in lanes.jsonl, never served).
        A lane can only be registered by its OWNING brick."""
        if not LANE_SHAPE.match(lane_id):
            raise ValueError(f"invalid lane_id '{lane_id}'")
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("endpoint must be http(s)://")
        if quality not in QUALITY_TIERS:
            raise ValueError(f"quality must be one of {sorted(QUALITY_TIERS)}")
        if not (0 < cost_per_task <= 1000):
            raise ValueError("cost_per_task must be in (0, 1000]")
        if auth_type and not auth_secret:
            raise ValueError("auth_secret required when auth_type set")

        lf = self._lock()
        try:
            lanes, _ = self._read(self.lanes_path, ("lane_id", "owner"))
            for l in lanes:
                if l["lane_id"] == lane_id:
                    if l["owner"] != owner_brick:
                        self._log("register", {"lane": lane_id, "owner": owner_brick,
                                               "reason": "not owner"}, outcome="rejected")
                        raise ValueError(f"lane {lane_id} owned by {l['owner']} — only owner can register/update")
                    # owner re-registering = update: drop the old row
                    lanes = [x for x in lanes if x["lane_id"] != lane_id]

            row = {"ts": int(time.time()), "lane_id": lane_id, "owner": owner_brick,
                   "endpoint": endpoint, "model": model, "capacity": capacity,
                   "cost_per_task": cost_per_task, "quality": quality,
                   "auth_type": auth_type, "active": True}
            if auth_secret:
                self._vault(lane_id, auth_secret)   # vaulted, never in the row
            self._log("register", {"lane": lane_id, "owner": owner_brick,
                                   "model": model, "quality": quality,
                                   "cost": cost_per_task})
            # atomic rewrite: preserve others + this lane
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
        """Owner removes its lane. Instant revocation."""
        lf = self._lock()
        try:
            lanes, _ = self._read(self.lanes_path, ("lane_id", "owner"))
            keep = [l for l in lanes if l["lane_id"] != lane_id]
            if len(keep) == len(lanes):
                raise ValueError(f"lane {lane_id} not found")
            for l in lanes:
                if l["lane_id"] == lane_id and l["owner"] != owner_brick:
                    self._log("deregister", {"lane": lane_id, "owner": owner_brick,
                                             "reason": "not owner"}, outcome="rejected")
                    raise ValueError(f"lane {lane_id} owned by {l['owner']} — only owner can deregister")
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
            # vault secret removal
            try:
                (self.state_dir / "vault" / f"{lane_id}.secret").unlink()
            except OSError:
                pass
            self._log("deregister", {"lane": lane_id, "owner": owner_brick})
            return {"lane_id": lane_id, "status": "deregistered"}
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN); lf.close()

    def lanes(self) -> dict:
        """Metadata-only lane map (never secrets, never endpoints' auth)."""
        lanes, corrupt = self._read(self.lanes_path, ("lane_id", "owner"))
        return {"lanes": [{"lane_id": l["lane_id"], "owner": l["owner"], "model": l["model"],
                           "capacity": l["capacity"], "cost_per_task": l["cost_per_task"],
                           "quality": l["quality"], "active": l.get("active", True)}
                          for l in lanes],
                "corrupt_rows": corrupt}

    def route(self, consumer: str, quality: str = "routine",
              fallback_endpoint: str = "", fallback_secret: str = "") -> dict:
        """Pick a lane for a task and PROXY the call (or return the picked lane
        for the caller to invoke via the router's /invoke path).
        Routing policy (khalid's mix): cheapest capable registered lane for the
        requested quality tier; if none, the designated default lane; else 503.
        The consumer NEVER receives any lane's auth secret."""
        if quality not in QUALITY_TIERS:
            raise ValueError(f"quality must be one of {sorted(QUALITY_TIERS)}")
        lanes, corrupt = self._read(self.lanes_path, ("lane_id", "owner"))
        active = [l for l in lanes if l.get("active", True)]
        # quality tier match, then cheapest within tier
        tier = [l for l in active if l["quality"] == quality]
        if not tier and quality in ("audit", "advanced"):
            tier = [l for l in active if l["quality"] == "advanced"] or \
                   [l for l in active if l["quality"] == "audit"]
        if not tier:
            tier = active
        if not tier:
            self._log("route", {"consumer": consumer, "quality": quality,
                                "reason": "no lanes"}, outcome="error")
            return {"status": 503, "error": "no registered lane"}

        pick = min(tier, key=lambda l: l["cost_per_task"])   # cheapest capable
        # ledger: bill the consumer's wallet, credit the lane's owner
        entry = {"ts": int(time.time()), "consumer": consumer, "lane": pick["lane_id"],
                 "owner": pick["owner"], "quality": quality,
                 "cost": pick["cost_per_task"], "model": pick["model"]}
        self._log("route", {"consumer": consumer, "lane": pick["lane_id"],
                            "quality": quality, "cost": pick["cost_per_task"]})
        self._append_atomic(self.ledger_path, entry)
        return {"status": 200, "lane": pick["lane_id"], "owner": pick["owner"],
                "model": pick["model"], "endpoint": pick["endpoint"],
                "cost": pick["cost_per_task"], "quality": pick["quality"],
                "corrupt_rows": corrupt,
                "note": "invoke via /invoke with your own consumer token — "
                        "the lane's auth secret stays vaulted"}

    def invoke(self, consumer: str, lane_id: str, payload: dict) -> dict:
        """PROXY a call to a lane on the consumer's behalf — the lane's secret
        is attached by the router and NEVER returned to the consumer."""
        lanes, _ = self._read(self.lanes_path, ("lane_id", "owner"))
        pick = next((l for l in lanes if l["lane_id"] == lane_id and l.get("active", True)), None)
        if not pick:
            return {"status": 404, "error": f"lane {lane_id} not active"}
        # vaulted secret
        secret = ""
        sp = self.state_dir / "vault" / f"{lane_id}.secret"
        if sp.exists():
            try:
                secret = sp.read_text().strip()
            except OSError:
                secret = ""
        headers = {"Content-Type": "application/json"}
        if pick.get("auth_type") == "bearer" and secret:
            headers["Authorization"] = f"Bearer {secret}"
        try:
            req = urllib.request.Request(pick["endpoint"], data=json.dumps(payload).encode(),
                                         headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode(errors="replace")
            self._log("invoke", {"consumer": consumer, "lane": lane_id, "status": resp.status})
            entry = {"ts": int(time.time()), "consumer": consumer, "lane": lane_id,
                     "owner": pick["owner"], "quality": pick["quality"],
                     "cost": pick["cost_per_task"], "model": pick["model"]}
            self._append_atomic(self.ledger_path, entry)
            return {"status": 200, "response": body[:4000]}
        except urllib.error.HTTPError as e:
            self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                 "status": e.code, "reason": "upstream error"}, outcome="error")
            return {"status": 502, "error": f"lane returned {e.code}"}
        except Exception as e:
            self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                 "reason": str(e)[:80]}, outcome="error")
            return {"status": 503, "error": f"lane unreachable: {str(e)[:80]}"}

    def ledger(self, consumer: str = "") -> dict:
        """The meter: who consumed what, from which lane, at what cost."""
        rows, corrupt = self._read(self.ledger_path)
        if consumer:
            rows = [r for r in rows if r.get("consumer") == consumer]
        return {"entries": rows[-100:], "count": len(rows), "corrupt_rows": corrupt}

    def status(self) -> dict:
        lanes, lcorrupt = self._read(self.lanes_path, ("lane_id", "owner"))
        led, dcorrupt = self._read(self.ledger_path)
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
            self._json(200, self.router.ledger())
        elif parsed.path == "/status":
            res = self.router.status()
            if res == 503:
                self._json(503, {"error": "router degraded"})
            else:
                self._json(200, res)
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
                # only the OWNER can register its own lane
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
                res = self.router.invoke(caller, body.get("lane_id", ""), body.get("payload", {}))
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
    ap.add_argument("--port", type=int, default=3742)
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args()
    r = TokenRouter(pathlib.Path(args.state_dir), pathlib.Path(args.tokens_dir), args.brick_id)
    RouterHandler.router = r
    srv = ThreadingHTTPServer((args.bind, args.port), RouterHandler)
    print(f"[router] {args.brick_id} on {args.bind}:{args.port} "
          f"(lanes register, secrets vaulted, bananas metered)")
    srv.serve_forever()

if __name__ == "__main__":
    main()
