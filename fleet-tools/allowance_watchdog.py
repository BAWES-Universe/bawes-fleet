#!/usr/bin/env python3
"""allowance_watchdog.py — round-144 R6/C3: ROOT-owned retry + escalate.

Root cron (15-min). Independent of the router/brick — a brick can never pull
this flag (round-139 doctrine). Responsibilities:
  1. RETRY undelivered/never-delivered alerts via the notifier.
  2. ESCALATE to the dashboard surface: /srv/bricks/register/allowance-alerts.json
     (read by fleet_dashboard.py "OPEN ALLOWANCE ALERTS" section) + an
     escalation audit line. Alerts stay visible until acknowledged (closed).
  3. RECONCILE daily-cap (door-cost.jsonl) vs monthly-50 (allowances) drift.
Root-owned: sudo python3 allowance_watchdog.py
"""
from __future__ import annotations
import json, pathlib, subprocess, sys, time

sys.path.insert(0, "/srv/bricks/ovh-server-001")
import allowance_meter as meter  # noqa: E402

ESCALATE = pathlib.Path("/srv/bricks/register/allowance-alerts.json")
ESCALATE_LOG = pathlib.Path("/srv/bricks/register/allowance-escalations.log")


def _retry():
    open_rows = meter.open_alert_rows()
    if not open_rows:
        return 0
    # fire the notifier once per open alert (it does its own x3 backoff);
    # this watchdog cycle is the retry engine for anything still open.
    for r in open_rows:
        subprocess.run([sys.executable,
                        "/srv/bricks/ovh-server-001/allowance_notifier.py",
                        "--alert-id", r.get("alert_id", "")],
                       capture_output=True, timeout=60)
    return len(open_rows)


def _escalate(open_rows):
    payload = []
    for r in open_rows:
        st = meter.alert_status(r.get("alert_id"))
        payload.append({"alert_id": r.get("alert_id"),
                        "person_id": r.get("person_id"),
                        "brick_id": r.get("brick_id"),
                        "month": r.get("month"),
                        "usage": r.get("usage"),
                        "allowance": r.get("allowance"),
                        "cost_usd": r.get("cost_usd"),
                        "name": r.get("name"),
                        "state": st.get("state"),
                        "ts": r.get("ts")})
        with open(ESCALATE_LOG, "a") as f:
            f.write(json.dumps({"ts": int(time.time()), "op": "escalate",
                                "alert_id": r.get("alert_id"),
                                "person_id": r.get("person_id"),
                                "state": st.get("state")}) + "\n")
    ESCALATE.write_text(json.dumps({"generated_ts": int(time.time()),
                                    "open_alerts": payload}, indent=1) + "\n")
    ESCALATE.chmod(0o600)
    return len(payload)


def _reconcile():
    """Daily-cap vs monthly-50: door spend today with zero usage rows this
    month = drift candidate. Log a line; never blocks anything."""
    day = time.strftime("%Y-%m-%d")
    door_cost = pathlib.Path("/srv/door/state/door-cost.jsonl")
    today = {}
    if door_cost.exists():
        for line in door_cost.read_text().splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("day") == day:
                today[r.get("user_id", "?")] = today.get(r.get("user_id", "?"), 0) \
                    + float(r.get("cost", 0.0) or 0.0)
    m = meter.month()
    rows = meter.read()
    users_with_usage = {r.get("person_id") for r in rows
                        if r.get("kind") == "usage_debit" and r.get("month") == m}
    drift = []
    for uid, spent in today.items():
        if uid not in users_with_usage:
            drift.append({"person_id": uid, "daily_cost_today": spent})
    if drift:
        with open(ESCALATE_LOG, "a") as f:
            f.write(json.dumps({"ts": int(time.time()), "op": "reconcile",
                                "month": m, "day": day,
                                "drift_candidates": drift}) + "\n")
    return drift


def main():
    n = _retry()
    open_rows = meter.open_alert_rows()
    n_esc = _escalate(open_rows)
    drift = _reconcile()
    print(f"watchdog: retried {n}, escalated {n_esc}, "
          f"reconcile drift {len(drift)} — {meter.status_line()}")


if __name__ == "__main__":
    main()
