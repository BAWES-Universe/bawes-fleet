#!/usr/bin/env python3
"""job_brick3_shared.py — brick 3: shells/shared package typecheck.
Desktop/mobile foundation: the shared TS package compiles clean."""
import json, subprocess, sys

def run():
    r = subprocess.run(["npx", "tsc", "--noEmit"], cwd="/opt/orbit-repo/shells/shared",
                       capture_output=True, text=True, timeout=180)
    return json.dumps({"job": "shared-typecheck", "ok": r.returncode == 0,
                       "errors": len(r.stdout.splitlines()) if r.stdout else 0}, sort_keys=True)

if __name__ == "__main__":
    print(run())
