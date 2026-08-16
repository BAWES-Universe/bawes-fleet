#!/usr/bin/env python3
"""door_gateway.py — Discord gateway for THE DOOR.
Connects via websocket, receives MESSAGE_CREATE events, routes DMs to
door_responder.handle_dm(). Long-poll, auto-reconnect, heartbeat.
- Only handles DMs (channel type 1) — never reads guild messages live
- Consent transcript written by the handler (M-7, 0600)
- V-5: consent = own words, timestamped, never automated
Run: python3 door_gateway.py
"""
import json, os, pathlib, sys, time, urllib.request

sys.path.insert(0, "/srv/door")
from door_v4 import handle_dm, TOKEN_ENV, UA

import websocket  # websocket-client

GATEWAY = "wss://gateway.discord.gg/?v=10&encoding=json"
API = "https://discord.com/api/v10"

def api(method, path, body=None):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bot {os.environ[TOKEN_ENV]}",
                 "Content-Type": "application/json",
                 "User-Agent": UA},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except Exception as e:
        return {"error": str(e)[:120]}

def send_dm(user_id, content):
    ch = api("POST", "/users/@me/channels", {"recipient_id": user_id})
    if "error" in ch:
        print("DM channel error:", ch["error"]); return
    api("POST", f"/channels/{ch['id']}/messages", {"content": content})

def run():
    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        print("no token"); return
    while True:
        try:
            ws = websocket.create_connection(GATEWAY, timeout=70)
            ws.settimeout(70)
            ws.send(json.dumps({"op": 2, "d": {
                "token": token, "intents": (1 << 12) | (1 << 1),  # DIRECT_MESSAGES | GUILD_MEMBERS
                "properties": {"os": "linux", "browser": "bawes", "device": "bawes"}}}))
            heartbeat = None
            while True:
                raw = ws.recv()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                op = msg.get("op")
                if op == 10:  # hello — set heartbeat
                    heartbeat = msg["d"]["heartbeat_interval"] / 1000.0
                    ws.send(json.dumps({"op": 1, "d": None}))
                elif op == 1:  # heartbeat request
                    ws.send(json.dumps({"op": 1, "d": None}))
                elif op == 0:  # dispatch
                    t = msg.get("t")
                    if t == "READY":
                        print("GATEWAY READY — door listening for DMs")
                    elif t == "GUILD_MEMBER_ADD":
                        d = msg["d"]
                        uid = d.get("user", {}).get("id")
                        name = d.get("user", {}).get("username", "?")
                        if uid and not d.get("user", {}).get("bot"):
                            print(f"NEW MEMBER: {name} joined — door reaching out")
                            # The door goes to THEM first: welcome + sell the brick
                            reply = handle_dm(uid, name, "__JOIN__", time.time())
                            send_dm(uid, reply)
                    elif t == "MESSAGE_CREATE":
                        d = msg["d"]
                        if d.get("channel_type") == 1 and not d.get("author", {}).get("bot"):
                            uid = d["author"]["id"]
                            name = d["author"].get("username", "?")
                            content = d.get("content", "")
                            print(f"DM from {name}: {content[:60]}")
                            reply = handle_dm(uid, name, content, time.time())
                            send_dm(uid, reply)
                elif op == 11:  # heartbeat ACK
                    pass
        except Exception as e:
            print(f"gateway error: {str(e)[:100]} — reconnecting in 5s")
            time.sleep(5)

if __name__ == "__main__":
    os.environ.setdefault(TOKEN_ENV, "")
    tok = pathlib.Path("/srv/secrets/door.env").read_text().strip() if os.path.exists("/srv/secrets/door.env") else ""
    if tok and not os.environ.get(TOKEN_ENV):
        os.environ[TOKEN_ENV] = tok
    run()
