#!/usr/bin/env python3
"""allowance_notifier.py — round-144 R6 fail-safe delivery for the ladder.

Delivers allowance ladder messages over the EXISTING door bot Discord API
(round-140 one-gateway doctrine — no new bot):
  - khalid 100% alert  -> the one DM (person/usage/cost/3 options)
  - khalid 95% heads-up -> lead-time notice
  - user warnings (80/95) -> proactive DM to the person

Mechanics (R6): durable row written BEFORE any delivery (done by the meter);
delivery with retry x3 backoff (10s/60s/300s); success -> alert-status
state=delivered, failure -> state=undelivered (watchdog retries + escalates).
Never silent-block: the STOP (403) never waits on this process — the router
spawns it fire-and-forget.

Usage:
  python3 allowance_notifier.py                 # process all open alert/warning rows
  python3 allowance_notifier.py --alert-id X    # one alert (router spawns this)
  python3 allowance_notifier.py --dry-run       # print what WOULD be sent (tests)
"""
from __future__ import annotations
import argparse, json, os, pathlib, sys, time, urllib.request, urllib.error

sys.path.insert(0, "/srv/bricks/ovh-server-001")
import allowance_meter as meter  # noqa: E402

TOKEN_ENV = "BRICK_DISCORD_TOKEN"
UA = "DiscordBot (https://github.com/BAWES-Universe/bawes-fleet, 1.0)"
API = "https://discord.com/api/v10"
DOOR_ENV = pathlib.Path("/srv/secrets/door.env")
BACKOFF = (10, 60, 300)


def _token() -> str:
    env = os.environ.get(TOKEN_ENV, "")
    if env:
        return env
    if DOOR_ENV.exists():
        return DOOR_ENV.read_text().strip()
    return ""


def api(method: str, path: str, body=None, token: str = ""):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bot {token}",
                 "Content-Type": "application/json",
                 "User-Agent": UA},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "code": e.code}
    except Exception as e:
        return {"error": str(e)[:120]}


def send_dm(user_id: str, content: str, token: str) -> dict:
    ch = api("POST", "/users/@me/channels", {"recipient_id": user_id}, token)
    if "error" in ch:
        return ch
    return api("POST", f"/channels/{ch['id']}/messages", {"content": content}, token)


def deliver_alert(row: dict, dry_run: bool = False) -> dict:
    """The ONE DM at 100% (R2 template) + the 95% heads-up (shorter).
    Live numbers (current bucket) drive the message; the row's frozen values
    are the audit trail. Rung 95 = heads-up, rung 100 = actionable alert."""
    name = row.get("name") or meter.person_name(row.get("person_id", ""))
    b = meter.bucket(row.get("person_id", ""))
    usage = b["usage"]
    allowance = b["allowance"]
    cost = float(row.get("cost_usd", 0.0))
    if row.get("rung") == "95":
        content = meter.KHALID_HEADS_UP_TPL.format(
            name=name, usage=usage, allowance=allowance, cost=cost)
    else:
        content = meter.KHALID_ALERT_TPL.format(
            name=name, brick_id=row.get("brick_id", "?"), usage=usage,
            allowance=allowance, cost=cost, gift=meter.BASE_ALLOWANCE)
    target = meter.KHALID_UID
    if dry_run:
        return {"dry_run": True, "to": target, "content": content}
    token = _token()
    if not token:
        return {"error": "no door token"}
    last = {}
    for i, delay in enumerate(BACKOFF + (0,)):  # 3 backoffs + final attempt
        if i:
            time.sleep(delay)
        last = send_dm(target, content, token)
        if "error" not in last:
            meter.mark_alert_status(row.get("alert_id"), "delivered",
                                    channel="discord-dm")
            return {"delivered": True, "alert_id": row.get("alert_id")}
    meter.mark_alert_status(row.get("alert_id"), "undelivered",
                            channel="discord-dm")
    return {"delivered": False, "alert_id": row.get("alert_id"),
            "error": last.get("error")}


def deliver_warning(row: dict, dry_run: bool = False) -> dict:
    rung = row.get("rung")
    usage = row.get("usage", 0)
    allowance = row.get("allowance", meter.BASE_ALLOWANCE)
    if rung == "80":
        content = meter.line_80(usage, allowance)
    elif rung == "95":
        content = meter.line_95(usage, allowance)
    else:
        content = meter.line_100(usage, allowance)
    target = row.get("person_id", "")
    if dry_run:
        return {"dry_run": True, "to": target, "content": content}
    token = _token()
    if not token:
        return {"error": "no door token"}
    last = {}
    for i, delay in enumerate(BACKOFF + (0,)):
        if i:
            time.sleep(delay)
        last = send_dm(target, content, token)
        if "error" not in last:
            meter.mark_warning_delivered(row, channel="discord-dm")
            return {"delivered": True, "warning": row.get("hmac")}
    return {"delivered": False, "warning": row.get("hmac"),
            "error": last.get("error")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert-id", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    results = []
    if args.alert_id:
        rows = [r for r in meter.open_alert_rows()
                if r.get("alert_id") == args.alert_id]
        for r in rows:
            results.append(deliver_alert(r, dry_run=args.dry_run))
    else:
        # khalid alerts first (the stop transaction), then user warnings
        for r in meter.open_alert_rows():
            results.append(deliver_alert(r, dry_run=args.dry_run))
        for person in sorted({r.get("person_id") for r in meter.read()
                              if r.get("kind") == "warning"}):
            for w in meter.pending_warnings(person):
                results.append(deliver_warning(w, dry_run=args.dry_run))
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
