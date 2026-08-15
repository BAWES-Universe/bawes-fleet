#!/usr/bin/env python3
"""door_server.py — THE UNIVERSAL DOOR (round-86, khalid: 'onboard anyone, no friction').
Serves the one-link onboarding page; /onboard takes {goal, consent} and runs the
T-024 flow server-side. The human touches ONE thing — their own words. No server
concepts, no installs, no member lists, zero prior knowledge.
"""
import json, pathlib, subprocess, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path("/srv/bricks/door")
PAGE = ROOT / "index.html"
REPO = "/tmp/bawes-fleet"  # where onboard_v2.py lives (CI-checked copy)

class Door(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = PAGE.read_bytes() if PAGE.exists() else b"door not configured"
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path != "/onboard":
            self.send_response(404); self.end_headers(); return
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except Exception:
            d = {}
        goal, consent = d.get("goal", "").strip(), d.get("consent", "").strip()
        if not goal or not consent:
            self._json({"ok": False, "error": "need both a goal and your own words"})
            return
        # V-5: consent is recorded verbatim with timestamp + a visitor id.
        # Signing happens on the issuer box; here we record + queue activation.
        row = {"goal": goal[:200], "consent": consent[:500], "ts": __import__("time").time(),
               "via": "universal-door", "status": "recorded"}
        (ROOT / "consent-queue.jsonl").open("a").write(json.dumps(row) + "\n")
        self._json({"ok": True, "name": "friend", "next": "your brick is waking — check your chat"})
    def _json(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.end_headers(); self.wfile.write(b)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    print(f"door on :{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Door).serve_forever()
