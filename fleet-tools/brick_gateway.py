#!/usr/bin/env python3
"""brick_gateway.py — GRADUATION GATEWAY (khalid: "Mishari and me and rest
need to exit the door and find their own bots... they need to graduate").

Each brick = its OWN Discord bot: own token, own name/avatar, own handle.
People do NOT live at the door — the door onboards, then hands off, and
the member's OWN brick bot takes over their DM.

Registry: /srv/door/brick-bots.json  (0600, root)
  { "<discord_user_id>": { "token": "bot token", "name": "bot name" } }
Each token = a Discord app created by the account owner (Discord rule:
only the account owner can create bots — the system cannot).

Behavior:
- One websocket connection per registered brick bot
- Serves ONLY its owner's DMs (allowlist = the user_id key)
- Anyone else who DMs the brick bot gets: "this brick belongs to X"
- Owner messages -> brick companion (never onboarding — they graduated)
- Door-graduation: when the door consents a member, it pings this
  gateway's registrar to check the member has a brick bot
"""
import json, os, pathlib, sys, time, urllib.request

sys.path.insert(0, "/srv/door")
from door_v4 import KNOWN, VOICE, router_invoke

import websocket  # websocket-client

GATEWAY = "wss://gateway.discord.gg/?v=10&encoding=json"
API = "https://discord.com/api/v10"
UA = "BAWES-Brick/1.0"
REGISTRY = pathlib.Path("/srv/door/brick-bots.json")

def load_registry():
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text())
    return {}

def api(token, method, path, body=None):
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
    except Exception as e:
        return {"error": str(e)[:120]}

def send_dm(token, user_id, content):
    ch = api(token, "POST", "/users/@me/channels", {"recipient_id": user_id})
    if "error" in ch:
        print("DM channel error:", ch["error"]); return
    api(token, "POST", f"/channels/{ch['id']}/messages", {"content": content})

def brick_reply(owner_id, owner_name, content):
    """The brick answers its own owner — companion, never onboarding."""
    lang = "en"
    identity = {
        "189055515819638794": ("khalid", "the owner of the fleet"),
        "231861753082937346": ("mishari", "a core engineer"),
        "690554066815811625": ("chahd", "family"),
    }.get(owner_id, (owner_name, "a member of the fleet"))
    prompt = (f"{VOICE.get(lang, VOICE['en'])}\n\n"
              f"Person: {identity[0]} — {identity[1]}, your owner. "
              f"They said: \"{content[:200]}\"\n"
              f"You are THEIR brick now. Answer as their personal brick "
              f"companion: warm, direct, concrete. You know them, you "
              f"remember their world. 2 sentences max, ONE question if needed.")
    reply = (router_invoke(prompt, max_tokens=200) or "").strip()
    return reply if len(reply) >= 10 else (
        f"Hey {identity[0]} 🍌 — I'm your brick, and I'm right here. "
        f"What do you need?")

def run_brick(user_id, cfg):
    token = cfg["token"]
    name = cfg.get("name", "Brick")
    _intents = 1 << 12  # DIRECT_MESSAGES only — a brick never reads guilds
    while True:
        try:
            ws = websocket.create_connection(GATEWAY, timeout=70)
            ws.settimeout(70)
            ws.send(json.dumps({"op": 2, "d": {
                "token": token, "intents": _intents,
                "properties": {"os": "linux", "browser": "bawes",
                               "device": "bawes"}}}))
            print(f"[brick {name}] READY — serving {user_id[:8]} only")
            while True:
                raw = ws.recv()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("op") == 0:
                    t = msg.get("t")
                    if t == "READY":
                        print(f"[brick {name}] gateway READY")
                    elif t == "MESSAGE_CREATE":
                        d = msg["d"]
                        if d.get("channel_type") == 1 and not d.get("author", {}).get("bot"):
                            uid = d["author"]["id"]
                            uname = d["author"].get("username", "?")
                            content = d.get("content", "")
                            if uid == user_id:
                                # owner -> brick companion
                                print(f"[brick {name}] owner DM: {content[:50]}")
                                try:
                                    ws.send(json.dumps({"op": 5, "d": {
                                        "channel_id": d["channel_id"]}}))
                                except Exception:
                                    pass
                                reply = brick_reply(uid, uname, content)
                                send_dm(token, uid, reply)
                            else:
                                # stranger -> this brick is owned
                                send_dm(token, uid,
                                        f"Hi {uname} — this brick belongs "
                                        f"to {name}. The door can get you "
                                        f"your own 🍌")
                                print(f"[brick {name}] stranger DM blocked: {uid[:8]}")
                elif msg.get("op") == 11:
                    pass
        except Exception as e:
            print(f"[brick {name}] error: {str(e)[:80]} — reconnect 5s")
            time.sleep(5)

def main():
    reg = load_registry()
    if not reg:
        print("NO BRICK BOTS REGISTERED — /srv/door/brick-bots.json empty")
        print("Add entries: {'<discord_id>': {'token': '...', 'name': '...'}}")
        return
    print(f"graduation gateway: {len(reg)} brick(s) registered")
    import threading
    threads = []
    for uid, cfg in reg.items():
        t = threading.Thread(target=run_brick, args=(uid, cfg), daemon=True)
        t.start()
        threads.append(t)
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
