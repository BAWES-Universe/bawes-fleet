#!/usr/bin/env python3
"""Staleness watchdog for the skills marketplace (khalid condition).

Reads marketplace/config.yaml (N = adoption_threshold, window_days) and every
marketplace/<skill_key>.yaml entry. Flags entries whose adoption count is below
the threshold within the window as STALE candidates.

REPORT ONLY — never writes files, never mutates state. A human/agent turns a
candidate into an actual `stale` status via PR (consensus + CI + khalid ratify).

Exit 0 always (reporting tool; CI runs the guardrail scan, not this).
"""
import datetime as dt
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "marketplace" / "config.yaml").read_text())
STALE = CONFIG["staleness"]
N = STALE["adoption_threshold"]
WINDOW = STALE["window_days"]
NOW = dt.datetime.now(dt.timezone.utc)

entries = sorted((ROOT / "marketplace").glob("*.yaml"))
entries = [e for e in entries if e.name not in ("config.yaml", "example.yaml")]

flagged = []
for path in entries:
    data = yaml.safe_load(path.read_text())
    key = data.get("skill_key", path.stem)
    status = data.get("lifecycle", {}).get("status", "?")
    if status in ("archived",):  # terminal — nothing to do
        continue

    adoption = data.get("adoption", {})
    count = adoption.get("count", 0)
    last = adoption.get("last_adoption_at")
    last_dt = None
    if last:
        try:
            last_dt = dt.datetime.fromisoformat(last.replace("Z", "+00:00"))
        except ValueError:
            last_dt = None

    in_window = last_dt is not None and (NOW - last_dt).days <= WINDOW
    below = count < N
    if below or not in_window:
        reason = "adoption count below threshold" if below else f"no adoption in {WINDOW}d window"
        flagged.append((key, status, count, last, reason))

if not flagged:
    print(f"✅ no stale candidates — all {len(entries)} listings meet adoption ≥ {N} in {WINDOW}d")
else:
    print(f"STALE CANDIDATES ({len(flagged)}): review → PR to set lifecycle.status=stale (then archived):")
    for key, status, count, last, reason in flagged:
        print(f"  - {key} [status={status}] adoption={count} last={last or 'never'} — {reason}")
print(f"(N={N}, window={WINDOW}d — knobs owned by khalid in marketplace/config.yaml)")
sys.exit(0)
