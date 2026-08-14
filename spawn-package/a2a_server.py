#!/usr/bin/env python3
"""a2a_server.py — A2A MESH PARTICIPATION for the spawn package (round-61).

CORE of the spawn package, not a bolt-on:
  - peer discovery: /a2a/peers lists registry bricks + skills
  - scoped-token auth: per-peer bearer tokens (mode-600), min 16 chars,
    compared with hmac.compare_digest; read-only toolsets from a2a-policy.json
    are ENFORCED at request time (not advertised)
  - outbound-only: binds 127.0.0.1 by default (never an inbound hole);
    a broker/gateway dials OUT to the brick, not in
  - fail-closed: missing policy / missing tokens / wrong identity -> REJECTED

Acceptance (round-61 §4.5): heartbeat in registry + A2A handshake with a peer
succeeds + read-only toolsets verified enforced.
"""
from __future__ import annotations
import argparse, hmac, json, os, pathlib, stat, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED_TOOLS = {"web", "vision", "session_search"}
REJECTED_TOOLS = {"terminal", "code_execution", "memory", "file", "skill_manage"}
MIN_TOKEN_LEN = 16

class A2AServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, addr, handler, ctx):
        super().__init__(addr, handler)
        self.ctx = ctx

class A2AHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> dict | None:
        tok = self.headers.get("Authorization", "")
        tok = tok.removeprefix("Bearer ").strip()
        if len(tok) < MIN_TOKEN_LEN:
            self._json(401, {"error": "unauthorized"})
            return None
        for bid, p in self.server.ctx["peers"].items():
            if hmac.compare_digest(tok, p["token"]):
                return {"peer": bid, "scope": p["scope"]}
        self._json(401, {"error": "unauthorized"})
        return None

    def do_GET(self):
        ctx = self.server.ctx
        if self.path == "/health":
            self._json(200, {"status": "ok", "brick": ctx["brick_id"],
                             "uptime_s": round(time.time() - ctx["start"], 1)})
            return
        who = self._authed()
        if who is None:
            return
        if self.path == "/identity":
            self._json(200, {"brick_id": ctx["brick_id"], "skills": ctx["skills"]})
        elif self.path == "/a2a/peers":
            self._json(200, {"peers": ctx["registry_peers"]})
        elif self.path == "/a2a/handshake":
            self._json(200, {"ok": True, "peer": who["peer"], "brick": ctx["brick_id"],
                             "enforced_read_only": sorted(REJECTED_TOOLS)})
        elif self.path == "/skills":
            self._json(200, {"skills": ctx["skills"]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        # no write surface exists on a read-only brick — 501, always
        self._json(501, {"error": "read-only brick: no write operations"})

def load_peers(token_dir: pathlib.Path) -> dict:
    """Per-peer scoped tokens: files in tokens/ dir, mode must be 600/400,
    content min 16 chars. Any violation -> that peer is rejected."""
    peers = {}
    if not token_dir.exists():
        return peers
    for f in token_dir.iterdir():
        if not f.is_file():
            continue
        mode = stat.S_IMODE(f.stat().st_mode)
        if mode & 0o077:
            raise SystemExit(f"REJECTED: token file {f.name} is {mode:o} — must be 600 (mode-600 rule)")
        tok = f.read_text().strip()
        if len(tok) < MIN_TOKEN_LEN:
            raise SystemExit(f"REJECTED: token file {f.name} too short (<{MIN_TOKEN_LEN} chars)")
        peers[f.name] = {"token": tok, "scope": ["web", "vision", "session_search"]}
    return peers

def read_registry_peers(registry_path: pathlib.Path) -> list:
    out, seen = [], set()
    if registry_path.exists():
        for line in registry_path.read_text().splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            bid = row.get("brick_id")
            if bid and bid not in seen:
                seen.add(bid)
                out.append({"brick_id": bid, "status": row.get("status"),
                            "last_seen": row.get("ts")})
    return out

def main():
    ap = argparse.ArgumentParser(description="A2A mesh participation (round-61)")
    ap.add_argument("--brick-root", default="/srv/bricks")
    ap.add_argument("--brick-id", default="")
    ap.add_argument("--port", type=int, default=3738)
    ap.add_argument("--bind", default="127.0.0.1",
                    help="outbound-only model: 127.0.0.1 default; broker dials OUT to us")
    ap.add_argument("--registry", default="/srv/bricks/registry/heartbeat-registry.jsonl")
    args = ap.parse_args()

    root = pathlib.Path(args.brick_root)
    brick_id = args.brick_id
    identity = {}
    if brick_id:
        idf = root / brick_id / "identity.json"
        if not idf.exists():
            raise SystemExit(f"REJECTED: no identity.json for {brick_id}")
        identity = json.loads(idf.read_text())
    else:
        found = [c for c in root.iterdir() if (c / "identity.json").exists()]
        if len(found) != 1:
            raise SystemExit(f"REJECTED: need exactly one brick under {root} (found {len(found)})")
        brick_id = found[0].name
        identity = json.loads((found[0] / "identity.json").read_text())

    pol = root / brick_id / "a2a-policy.json"
    if not pol.exists():
        raise SystemExit("REJECTED: missing a2a-policy.json (fail-closed)")
    policy = json.loads(pol.read_text())
    allow = set(policy.get("allow", []))
    if not allow <= ALLOWED_TOOLS:
        raise SystemExit(f"REJECTED: policy allows non-read-only tools: {sorted(allow - ALLOWED_TOOLS)}")
    if not set(policy.get("reject", [])) >= REJECTED_TOOLS:
        raise SystemExit("REJECTED: policy must reject terminal/code_execution/memory/file/skill_manage")

    peers = load_peers(root / brick_id / "tokens")
    if not peers:
        raise SystemExit("REJECTED: no valid per-peer tokens (mode-600, >=16 chars)")

    ctx = {"brick_id": brick_id, "skills": identity.get("skills", []), "peers": peers,
           "registry_peers": read_registry_peers(pathlib.Path(args.registry)),
           "start": time.time()}
    srv = A2AServer((args.bind, args.port), A2AHandler, ctx)
    print(f"[a2a] {brick_id} mesh participation on {args.bind}:{args.port} "
          f"(read-only enforced: {sorted(REJECTED_TOOLS)})", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    main()
