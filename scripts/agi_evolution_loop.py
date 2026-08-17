#!/usr/bin/env python3
"""agi_evolution_loop.py — CHANGE-SIGNAL heartbeat (Zeus round-79 Z3).
Reports ONLY deltas: new write-up, novel-rate change, evolution verdict,
warrant event, spend. SILENT otherwise — liveness is the watchdog's job
(round-24: timers must signal change; round-16: liveness = telemetry, not signal).
Empty stdout = silent tick. Metric moved: NOVEL/hr and state transitions.
"""
import json, subprocess, time

LOG = "/root/.hermes/notes/banana-bank/evolution-rounds.jsonl"
LAST = "/root/.hermes/notes/banana-bank/.last-evo.json"
SSH = ["ssh", "-i", "/root/.hermes/keys/ovh-vps-deploy", "-o", "ConnectTimeout=15",
       "-o", "StrictHostKeyChecking=no", "ubuntu@51.75.74.214"]

def read_live_store():
    cmd = SSH + ["cd /srv/bricks/orchestrator && python3 -c "
                 "'import json; d=json.load(open(\"vector-store.json\")); print(json.dumps(d.get(\"stats\",{})))'"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout.strip())
    except Exception:
        return None

stats = read_live_store()
if stats is None:
    raise SystemExit(0)  # store unreachable — watchdog territory, not mine

raw = stats.get("raw_in", 0); novel = stats.get("novel", 0); dup = stats.get("duplicates", 0)
rate = novel / raw if raw else 0.0

prev = {}
try:
    prev = json.load(open(LAST))
except Exception:
    pass

row = {"ts": int(time.time()), "kind": "evolution-tick", "raw": raw, "novel": novel,
       "duplicates": dup, "novel_rate": round(rate, 3), "cost_usd": 0.0}
with open(LOG, "a") as f:
    f.write(json.dumps(row) + "\n")

# ---- CHANGE-SIGNAL GATE: silent unless something actually moved ----
d_raw = raw - prev.get("raw", 0)
d_novel = novel - prev.get("novel", 0)
rate_prev = prev.get("novel_rate")
rate_changed = rate_prev is not None and abs(rate - rate_prev) > 0.01

if not prev:
    with open(LAST, "w") as f:
        json.dump({"raw": raw, "novel": novel, "duplicates": dup, "novel_rate": round(rate, 3)}, f)
    raise SystemExit(0)  # first tick = baseline only, no announcement

with open(LAST, "w") as f:
    json.dump({"raw": raw, "novel": novel, "duplicates": dup, "novel_rate": round(rate, 3)}, f)

if d_raw > 0 or rate_changed:
    print(f"🧠 EVOLUTION — {time.strftime('%H:%M')}")
    if d_raw > 0:
        print(f"  +{d_raw} write-up(s), +{d_novel} novel, +{d_raw - d_novel} dup caught by gate")
    if rate_changed:
        print(f"  NOVEL rate {rate_prev:.2f} → {rate:.2f} (V-18)")
    print(f"  brain: {raw} write-ups · {novel} novel · {dup} dup · $0")
else:
    # no delta: silence. (change-signal rule, Z3)
    pass
