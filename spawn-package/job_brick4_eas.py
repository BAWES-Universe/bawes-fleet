#!/usr/bin/env python3
"""job_brick4_eas.py — brick 4: eas.json validity (iOS/macOS build config).
Desktop/mobile: the EAS build profiles are valid JSON + named profiles exist."""
import json, pathlib

def run():
    p = pathlib.Path("/opt/orbit-repo/web-app/eas.json")
    d = json.loads(p.read_text())
    profiles = list(d.get("build", {}).keys())
    ok = len(profiles) >= 2 and all(k in profiles for k in ("development", "production"))
    return json.dumps({"job": "eas-config-verify", "ok": ok,
                       "profiles": profiles}, sort_keys=True)

if __name__ == "__main__":
    print(run())
