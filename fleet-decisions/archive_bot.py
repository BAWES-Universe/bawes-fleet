#!/usr/bin/env python3
"""archive_bot.py — READ-ONLY Discord archive bot (S1, approved 2026-08-16).
Sees channel history, writes messages to the archive store, NEVER speaks in
channels, NEVER edits/deletes. Every read is logged to the append-only audit
trail. Raw member data stays in the store; human docs never name members (V-5).
Requires: DISCORD_TOKEN (vaulted, never in git), ARCHIVE_DIR.
Invite with ONLY read history + view channels permissions."""
import asyncio, hashlib, json, os, pathlib, sys, time, urllib.request

TOKEN = os.environ.get("DISCORD_TOKEN", "")
ARCHIVE = pathlib.Path(os.environ.get("ARCHIVE_DIR", "/srv/archives/universe"))
REST = "https://discord.com/api/v10"
SELF = "https://discord.com/api/v10"

def audit(op, scope, detail):
    row = {"ts": time.time(), "op": op, "scope": scope, "detail": detail}
    with open(ARCHIVE / "audit.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")

def api(method, path, token):
    req = urllib.request.Request(REST + path, method=method,
        headers={"Authorization": f"Bot {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def archive_message(msg, channel_id):
    """Store message: hashed member id (V-5: no raw names), content, ts."""
    mid = msg.get("id"); author = msg.get("author", {})
    row = {"id": mid, "channel": channel_id,
           "author_sha": hashlib.sha256(author.get("id", "").encode()).hexdigest()[:16],
           "author_name": author.get("username", "") if False else None,  # NEVER store raw names
           "content": msg.get("content", "")[:2000], "ts": msg.get("timestamp"),
           "attachments": len(msg.get("attachments", []))}
    with open(ARCHIVE / "messages.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")

async def archive_guild(token):
    g = api("GET", "/users/@me/guilds", token)
    for guild in g:
        gid = guild["id"]
        audit("guild_scan", gid, f"{guild.get('name')} ({len(guild.get('permissions', ''))} perm bits)")
        channels = api("GET", f"/guilds/{gid}/channels", token)
        for ch in channels:
            if ch["type"] not in (0, 5, 15):  # text, announcement, forum
                continue
            cid = ch["id"]
            audit("channel_start", f"{gid}/{cid}", ch.get("name", ""))
            after = None; n = 0
            while True:
                path = f"/channels/{cid}/messages?limit=100" + (f"&after={after}" if after else "")
                msgs = api("GET", path, token)
                if not msgs: break
                for m in msgs:
                    archive_message(m, cid); n += 1
                    after = m["id"]
                if len(msgs) < 100: break
                await asyncio.sleep(0.5)  # rate-limit courtesy
            audit("channel_done", f"{gid}/{cid}", f"{n} messages")

async def main():
    if not TOKEN:
        print("DISCORD_TOKEN not set"); sys.exit(1)
    audit("boot", "self", "archive_bot started (read-only)")
    await archive_guild(TOKEN)
    audit("shutdown", "self", "archive pass complete")

if __name__ == "__main__":
    asyncio.run(main())
