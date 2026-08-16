#!/usr/bin/env python3
"""collab_pack.py — MANY BRICKS COLLABORATING (round 2026-08-16, the pitch).
4 bricks, 4 DIFFERENT product jobs, run in PARALLEL, each verified, each
mints, combined into ONE human-visible achievement: the product surfaces."""
import hashlib, json, os, pathlib, subprocess, sys, time

BRICKS = [
    {"id": "brick-web-001",  "probe": "browser-dist-verify",  "cmd": ["/opt/orbit-repo/web-app/job_browser_verify.py"]},
    {"id": "brick-e2e-001",  "probe": "browser-e2e-verify",   "cmd": ["/opt/orbit-repo/web-app/job_brick2_e2e.py"]},
    {"id": "brick-shared-001", "probe": "shared-typecheck",   "cmd": ["/opt/orbit-repo/shells/shared/job_brick3_shared.py"]},
    {"id": "brick-eas-001",  "probe": "eas-config-verify",    "cmd": ["/opt/orbit-repo/web-app/job_brick4_eas.py"]},
]

def run_one(b):
    try:
        r = subprocess.run([sys.executable] + b["cmd"], capture_output=True, text=True, timeout=600)
        out = r.stdout.strip()
        ok = r.returncode == 0 and out.startswith("{")
        return {"brick": b["id"], "probe": b["probe"], "ok": ok,
                "output": out if ok else ("ERR: " + r.stderr[-120:])}
    except Exception as e:
        return {"brick": b["id"], "probe": b["probe"], "ok": False, "output": str(e)[:120]}

t0 = time.time()
results = [run_one(b) for b in BRICKS]  # parallel-able; serial here, each independent
dt = round(time.time() - t0, 1)

passed = [r for r in results if r["ok"]]
summary = {
    "achievement": "orbit-product-surfaces",
    "bricks": len(BRICKS), "passed": len(passed), "wall_s": dt,
    "surfaces": {r["probe"]: r["ok"] for r in results},
}
for r in results:
    print(f"BRICK {r['brick']} [{r['probe']}] -> {'PASS' if r['ok'] else 'FAIL'}")
print("SUMMARY:", json.dumps(summary, sort_keys=True))
print("COLLAB_SHA:", hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest())
