#!/usr/bin/env python3
"""Headless worker server — the round-30 Z-1 recipe, concretized.
Zeus: 'workers are headless servers you talk to over a published HTTP port.
My fleet NEVER used SSH. Not once.'

The pattern:
  1. Image ENTRYPOINT starts THIS server on a fixed port (default 3737)
  2. Coordinator creates the instance via REST with runtype:args (MANDATORY for
     entrypoint-based images — SSH/Jupyter runtypes REPLACE the ENTRYPOINT)
  3. Coordinator polls GET /api/v1/instances/ (the LIST is truth), finds the
     port mapping, HTTP-ready-checks until 200
  4. Jobs POSTed over HTTP, results returned over HTTP, appended to JSONL,
     committed to git — never reliant on host survival
  5. Destroy via v0 DELETE, verify-zero via v1 LIST poll, sweep as backstop

No SSH. No key registration. No onstart. That's the whole answer.

Round-33 review fixes:
  - bearer token required on all non-/health routes (finding 6)
  - state file touched on every request = IPC to death_warrant (blocker 3)
  - ThreadingHTTPServer (finding 11), bounded body (finding 10),
    /job gated behind a passed probe (finding 12)
"""
import json, os, hmac, threading, time, hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PORT = int(os.environ.get("WORKER_PORT", "3737"))
TOKEN = os.environ.get("WORKER_TOKEN", "")          # required on non-/health routes
STATE_FILE = os.environ.get("STATE_FILE", "/work/worker-state.json")
MAX_BODY = int(os.environ.get("MAX_BODY", "65536"))
START = time.time()
GRANT_KEY = os.environ.get("GRANT_KEY", "")
PROBES_PASSED = set()                                # probe ids that verified this host
_state_lock = threading.Lock()

def touch_state(queue_empty=True):
    """IPC with the death warrant (round-33 blocker 3): every request updates
    last_activity; the supervisor reads this file instead of dead env defaults."""
    try:
        with _state_lock:
            with open(STATE_FILE, "w") as f:
                json.dump({"last_activity": time.time(),
                           "queue_empty": bool(queue_empty),
                           "worker": getattr(threading.current_thread(), "name", "?")}, f)
    except Exception:
        pass

class WorkerHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        """Bearer token on everything except /health (round-33 finding 6).
        /dispatch is grant-authed (T-021 F2) — Bearer not required there."""
        if TOKEN and hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {TOKEN}"):
            return True
        self._json(401, {"error": "unauthorized"})
        return False

    def do_GET(self):
        path = urlparse(self.path).path
        touch_state()
        if path == "/health":
            self._json(200, {"status": "ok", "uptime_s": round(time.time() - START, 1)})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        touch_state()
        if path != "/dispatch" and not self._authorized():
            return
        # bounded body (round-33 finding 10): cap size, tolerate bad JSON
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY:
                self._json(413, {"error": "body too large"})
                return
            payload = json.loads(self.rfile.read(length)) if length else {}
        except Exception:
            self._json(400, {"error": "malformed json"})
            return

        if path == "/probe":
            pid = payload.get("probe", "probe-000")
            if pid == "probe-001":
                ans, expect = 7 * 6, 42
            elif pid == "probe-002":
                h = hashlib.sha256(b"bawes-probe").hexdigest()
                ans, expect = h, "7562cc8852fe6a2e4981460fdc284d5fb2b5229270f3c506f673d40481384b25"
            elif pid == "probe-003":
                import sys
                ans, expect = sys.version_info >= (3, 8), True
            else:
                self._json(404, {"error": f"unknown probe {pid}"})
                return
            ok = ans == expect
            if ok:
                PROBES_PASSED.add(pid)   # gate for /job (finding 12)
            self._json(200, {"probe": pid, "answer": ans, "expected": expect,
                             "ok": ok, "worker": self.server.worker_id})
        elif path == "/dispatch":
            # T-UNIVERSE-021: orchestrator dispatches cards here. Auth = the
            # per-card HMAC GRANT (never the control token — DA round-2 F2).
            grant = payload.get("grant", {})
            if not GRANT_KEY:
                self._json(500, {"error": "GRANT_KEY not configured"})
                return
            g = dict(grant)
            sig = g.pop("sig", "")
            body = json.dumps(g, sort_keys=True)
            expect = hmac.new(GRANT_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()[:24]
            if not (hmac.compare_digest(sig, expect) and g.get("exp", 0) > time.time()
                    and g.get("scope") == "read-only"):
                self._json(403, {"error": "grant invalid or expired"})
                return
            pid = payload.get("probe_id", "")
            # deterministic known-answer probe: output hash is the receipt field
            if pid == "probe-verify-001":
                out = hashlib.sha256(b"fleet-probe-output-001").hexdigest()
            elif pid == "probe-credsan-001" or pid == "probe-credsan-002":
                # REAL JOB (round-83/88): Plugn/Yo3an + full-org credential re-scan.
                # Runs the actual scan against the public GitHub API and hashes
                # the REAL output — non-earner recomputes by re-running the scan.
                import subprocess, sys as _sys
                res = subprocess.run(
                    [_sys.executable, "/srv/bricks/orchestrator/job_credsan.py"],
                    capture_output=True, text=True, timeout=60)
                out = res.stdout.strip()
                if res.returncode != 0 or not out:
                    self._json(500, {"error": "credsan job failed"})
                    return
                out = hashlib.sha256(out.encode()).hexdigest()
            else:
                self._json(404, {"error": f"unknown probe {pid}"})
                return
            receipt = {"card_id": payload.get("card_id"),
                       "probe_id": pid, "output_hash": out,
                       "brick_id": self.server.worker_id,
                       "dispatch_id": payload.get("dispatch_id"),
                       "injected_context": payload.get("injected_context", {})}
            self._json(200, {"ok": True, "receipt": receipt})
        elif path == "/job":
            # round-33 finding 12: real jobs sit behind a passed probe — an
            # unverified host never carries real work
            if not PROBES_PASSED:
                self._json(403, {"error": "host not verified — pass a probe first"})
                return
            t0 = time.time()
            self._json(200, {
                "job": payload.get("job", "unknown"),
                "worker": self.server.worker_id,
                "result": payload.get("input", "").upper(),
                "elapsed_s": round(time.time() - t0, 4),
            })
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, *args):
        pass  # quiet

class WorkerServer(ThreadingHTTPServer):
    daemon_threads = True  # finding 11: stuck job never blocks /health

    def __init__(self, addr, handler, worker_id):
        super().__init__(addr, handler)
        self.worker_id = worker_id

def main():
    worker_id = os.environ.get("BRICK_ID", "brick-worker")
    srv = WorkerServer(("0.0.0.0", PORT), WorkerHandler, worker_id)
    print(f"[worker] {worker_id} serving on :{PORT} (headless — no SSH, round-30 recipe)", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    main()
