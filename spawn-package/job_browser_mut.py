#!/usr/bin/env python3
"""job_browser_mut.py — MUTATED card (consensus-growth, round 2026-08-16).
Mutation of probe-browser-001: adds dist FILE COUNT + build time as new
dimensions. New probe_id, new card_id, new dispatch_id, new expected hash.
Ledger stays append-only; the queue is additive, never re-hash."""
import hashlib, json, os, subprocess, sys, time

REPO = os.environ.get("ORBIT_REPO", "/opt/orbit-repo")

def dir_hash_and_count(path: str):
    h = hashlib.sha256(); n = 0
    for root, _, files in sorted(os.walk(path)):
        for f in sorted(files):
            fp = os.path.join(root, f)
            h.update(os.path.relpath(fp, path).encode()); h.update(b"\x00")
            with open(fp, "rb") as fh: h.update(fh.read())
            h.update(b"\x00"); n += 1
    return h.hexdigest(), n

t0 = time.time()
build = subprocess.run(["npm", "run", "build"], cwd=REPO + "/web-app",
                       capture_output=True, text=True, timeout=600)
dt = round(time.time() - t0, 1)
if build.returncode != 0:
    print(json.dumps({"ok": False, "error": build.stderr[-150:]}, sort_keys=True))
    sys.exit(0)
dh, nfiles = dir_hash_and_count(REPO + "/web-app/dist")
# NEW dimension vs probe-browser-001: dist file count + build seconds
print(json.dumps({"job": "browser-dist-mut-001", "ok": True,
                   "dist_sha256": dh, "dist_files": nfiles, "build_s": dt}, sort_keys=True))
