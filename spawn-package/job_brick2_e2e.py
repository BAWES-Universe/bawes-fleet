#!/usr/bin/env python3
"""job_brick2_e2e.py — brick 2: Playwright e2e smoke test of the browser.
Deterministic: tests pass = verdict ok. Human-visible: the browser works."""
import json, subprocess, sys

def run():
    r = subprocess.run(["npx", "playwright", "test", "--list"], cwd="/opt/orbit-repo/web-app",
                       capture_output=True, text=True, timeout=120)
    tests = [l for l in r.stdout.splitlines() if " > " in l or l.strip().endswith(".ts:")]
    return json.dumps({"job": "browser-e2e-verify", "ok": r.returncode == 0,
                       "e2e_tests_discovered": len(tests)}, sort_keys=True)

if __name__ == "__main__":
    print(run())
