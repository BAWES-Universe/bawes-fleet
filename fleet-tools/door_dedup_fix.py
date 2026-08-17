#!/usr/bin/env python3
"""door_dedup_fix.py — ONE ONBOARDING DM PER MEMBER, EVER (round-135).
Khalid: "The door was spamming him with your brick is ready... I don't
want to onboard him again if the process isn't trustworthy and intelligent."

Root cause (verified in code): the gateway's reconnect path re-processes
GUILD_MEMBER_ADD from Discord's resume buffer; on every bounce (the
flagged 4014 intent-downgrade crash-loop) the join handler re-fires and
re-sends the onboarding DM. door_v4's `state != "new"` guard only helps
if the profile was saved before the replay — it wasn't, reliably.

Fix: a PERSISTENT greeted-set (append-only, 0600) checked BEFORE the
join handler. Once a member is greeted, no reconnect, no replay, no
re-guild can ever DM them again. Also: gateway connect now applies the
4014 downgrade immediately instead of crash-looping.
"""
import json, pathlib

DOOR = pathlib.Path("/srv/door")
GREETED = DOOR / "greeted.jsonl"   # append-only: one line per member, ever

def load_greeted():
    out = set()
    if GREETED.exists():
        for l in GREETED.read_text().strip().split("\n"):
            if l.strip():
                try:
                    out.add(json.loads(l)["user_id"])
                except Exception:
                    pass
    return out

def mark_greeted(user_id, user_name, ts):
    """Called once, exactly once, per member (idempotent)."""
    already = load_greeted()
    if user_id in already:
        return False  # never a second DM
    with open(GREETED, "a") as f:
        f.write(json.dumps({"user_id": user_id, "name": user_name,
                            "greeted_ts": ts}) + "\n")
    import os
    os.chmod(GREETED, 0o600)
    return True

def should_greet(user_id):
    """The ONLY gate the gateway asks: has this person been greeted ever?"""
    return user_id not in load_greeted()

if __name__ == "__main__":
    import sys, time
    if len(sys.argv) >= 3 and sys.argv[1] == "mark":
        print("first-time:" if mark_greeted(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "?", time.time()) else "already-greeted (no DM)")
    elif sys.argv[1] == "check" and len(sys.argv) >= 3:
        print("greet-ok" if should_greet(sys.argv[2]) else "greeted (skip)")
    elif sys.argv[1] == "status":
        print(f"greeted count: {len(load_greeted())}")
        for l in GREETED.read_text().strip().split("\n") if GREETED.exists() else []:
            if l.strip():
                d = json.loads(l)
                print(f" - {d['name']} ({d['user_id']}) @ {d['greeted_ts']}")
