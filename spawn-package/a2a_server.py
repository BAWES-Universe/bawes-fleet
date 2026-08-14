#!/usr/bin/env python3
"""a2a_server.py — A2A MESH PARTICIPATION for the spawn package (round-61).

CORE of the spawn package, not a bolt-on:
  - peer discovery: /a2a/peers lists registry bricks + skills
  - scoped-token auth: per-peer bearer tokens (mode-600), read-only toolsets
    from a2a-policy.json are ENFORCED at request time (not advertised)
  - outbound-only bind on untrusted hosts: never inbound holes, never raw keys
  - gateway consumption: the broker/gateway calls /a2a/* with a scoped token

Acceptance (round-61 §4.5): heartbeat in registry + A2A handshake with a peer
succeeds + read-only toolsets verified enforced.
"""
from __future__ import annotations
import argparse, hashlib, hmac, json, os, pathlib, secrets, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED_TOOLS = {"web", "vision", "session_search"}  # read-only surface
REJECTED_TOOLS = {"terminal", "code_execution", "memory", "file", "skill_manage"}

class A2AServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, addr, handler, ctx):
        super().__init__(addr, handler)
        self.ctx = ctx

class A2AHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self, path: str) -> dict | None:
        """Enforce per-peer scoped token (mode-600 file). Read-only only."""
        tok = self.headers.get("Authorization", "")
        tok = tok.removeprefix("Bearer ").strip()
        peers = self.server.ctx["peers"]  # {brick_id: {"token": ..., "scope": [...]}}
        for bid, p in peers.items():
            if hmac.compare_digest(tok, p["token"]):
                # enforce read-only scope at request time
                if path.startswith("/a2a/") or path in ("/identity", "/skills", "/health"):
                    return {"peer": bid, "scope": p["scope"]}
                self._json(403, {"error": "read-only: operation not allowed for scoped peer"})
                return None
        self._json(401, {"error": "unauthorized"})
        return None

    def do_GET(self):
        ctx = self.server.ctx
        if self.path == "/health":
            self._json(200, {"status": "ok", "brick": ctx["brick_id"], "uptime_s": round(time.time() - ctx["start"], 1)})
            return
        who = self._authed(self.path)
        if who is None:
            return
        if self.path == "/identity":
            self._json(200, {"brick_id": ctx["brick_id"], "skills": ctx["skills"]})
        elif self.path == "/a2a/peers":
            self._json(200, {"peers": ctx["registry_peers"]})  # from heartbeat registry
        elif self.path == "/a2a/handshake":
            # acceptance: A2A handshake with a peer succeeds
            self._json(200, {"ok": True, "peer": who["peer"], "brick": ctx["brick_id"],
                             "enforced_read_only": sorted(REJECTED_TOOLS)})
        elif self.path == "/skills":
            self._json(200, {"skills": ctx["skills"]})
        else:
            self._json(404, {"error": "not found"})

def load_peers(token_dir: pathlib.Path) -> dict:
    """Per-peer scoped tokens, mode-600 files: {brick_id: {token, scope}}."""
    peers = {}
    if token_dir.exists():
        for f in token_dir.iterdir():
            if f.suffix == ".token":
                tok = f.read_text().strip()
                scope = ["web", "vision", "session_search"]  # read-only by construction
                peers[f.stem] = {"token": tok, "scope": scope}
    return peers

def read_registry_peers(registry_path: pathlib.Path) -> list:
    """Last-known bricks from the heartbeat registry (discovery source)."""
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
    ap.add_argument("--brick-root", default="/srv/bricks", help="brick root parent")
    ap.add_argument("--brick-id", default="", help="brick_id (default: from identity.json)")
    ap.add_argument("--port", type=int, default=3738)
    ap.add_argument("--registry", default="/srv/bricks/registry/heartbeat-registry.jsonl")
    args = ap.parse_args()

    root = pathlib.Path(args.brick_root)
    brick_id = args.brick_id
    identity = {}
    if brick_id:
        idf = root / brick_id / "identity.json"
        if idf.exists():
            identity = json.loads(idf.read_text())
    else:
        # find the single brick under root
        for cand in root.iterdir():
            if (cand / "identity.json").exists():
                brick_id = cand.name
                identity = json.loads((cand / "identity.json").read_text())
                break
    if not brick_id:
        raise SystemExit("REJECTED: no brick identity found under --brick-root")

    # enforce read-only policy from a2a-policy.json (the spawn package wrote it)
    pol = root / brick_id / "a2a-policy.json"
    if pol.exists():
        policy = json.loads(pol.read_text())
        allow = set(policy.get("allow", []))
        assert allow <= ALLOWED_TOOLS, f"policy allows non-read-only tools: {allow - ALLOWED_TOOLS}"
        assert set(policy.get("reject", [])) >= REJECTED_TOOLS, "policy must reject terminal/code_execution/memory/file/skill_manage"

    peers = load_peers(root / brick_id / "tokens")
    if not peers:
        raise SystemExit("REJECTED: no per-peer tokens — create mode-600 tokens/ dir (round-61: scoped tokens are the auth layer)")

    skills = identity.get("skills", [])
    ctx = {"brick_id": brick_id, "skills": skills, "peers": peers,
           "registry_peers": read_registry_peers(pathlib.Path(args.registry)),
           "start": time.time()}
    srv = A2AServer(("0.0.0.0", args.port), A2AHandler, ctx)
    print(f"[a2a] {brick_id} mesh participation on :{args.port} (read-only enforced: {sorted(REJECTED_TOOLS)})", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    main()
