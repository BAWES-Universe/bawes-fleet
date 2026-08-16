#!/usr/bin/env python3
"""door_extract.py — THE DOOR READS ALL 3 DISCORDS (khalid directive 2026-08-16).
"Let it read it all and pass for you and agi."
Door is admin → REST full extraction: guilds → channels → threads → messages.
V-5: author names hashed (sha256), never stored raw.
Writes: /srv/door/knowledge/raw-<guild>-<date>.jsonl (append-only, 0600)
Distills: per-channel digest docs → fleet vector store → brain retrieval.
Silent-until-change: prints only the delta line.
"""
import hashlib, json, os, pathlib, sys, time, urllib.request

TOKEN_ENV = "BRICK_DISCORD_TOKEN"
API = "https://discord.com/api/v10"
UA = "DiscordBot (https://github.com/BAWES-Universe/bawes-fleet, 1.0)"
KNOW = pathlib.Path("/srv/door/knowledge")
RAW_DIR = KNOW / "raw"
STATE = KNOW / "extract-state.json"
STORE_PATH = "/srv/bricks/orchestrator/vector-store.json"

def api(path):
    req = urllib.request.Request(
        f"{API}{path}",
        headers={"Authorization": f"Bot {os.environ[TOKEN_ENV]}",
                 "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def hash_name(name):
    return hashlib.sha256((name or "?").encode()).hexdigest()[:16]

def extract():
    guilds = api("/users/@me/guilds")
    state = json.loads(STATE.read_text()) if STATE.exists() else {"last_msg": {}}
    total_new = 0
    seen = set()
    for g in guilds:
        gid = g["id"]; gname = g.get("name", "?")
        seen.add(gid)
        print(f"GUILD {gname} ({gid})")
        chans = api(f"/guilds/{gid}/channels")
        for ch in chans:
            cid = ch["id"]
            ctype = ch.get("type")
            if ctype not in (0, 5, 15):  # text, news, forum — skip voice/categories
                continue
            key = f"{gid}:{cid}"
            after = state.get("last_msg", {}).get(key)
            try:
                q = f"?limit=100" + (f"&after={after}" if after else "")
                msgs = api(f"/channels/{cid}/messages{q}")
            except Exception:
                continue
            if not msgs:
                continue
            out = []
            for m in msgs:
                if m.get("type") != 0 or m.get("author", {}).get("bot"):
                    continue
                out.append({"guild": gname, "channel": ch.get("name", "?"),
                            "author_h": hash_name(m.get("author", {}).get("username")),
                            "ts": m.get("timestamp"), "content": m.get("content", "")[:500]})
            if out:
                RAW_DIR.mkdir(parents=True, exist_ok=True)
                fpath = RAW_DIR / f"raw-{gname}-{time.strftime('%Y-%m-%d')}.jsonl"
                with open(fpath, "a") as f:
                    for row in out:
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                os.chmod(fpath, 0o600)
                total_new += len(out)
                state.setdefault("last_msg", {})[key] = msgs[0]["id"]
    STATE.write_text(json.dumps(state, indent=2))
    os.chmod(STATE, 0o600)
    return guilds, total_new

def distill(guilds):
    """Per-guild digest docs for the vector store — the brain's memory."""
    sys.path.insert(0, "/srv/bricks/orchestrator")
    import fleet_vector_store as vs
    store = vs.VectorStore(STORE_PATH)
    added = 0
    for g in guilds:
        gname = g.get("name", "?")
        raw = sorted(RAW_DIR.glob(f"raw-{gname}-*.jsonl"))
        msgs = []
        for rp in raw:
            for line in rp.read_text().splitlines():
                try:
                    msgs.append(json.loads(line))
                except Exception:
                    pass
        if not msgs:
            continue
        msgs = msgs[-200:]
        topics = {}
        for m in msgs:
            t = m["channel"]
            topics.setdefault(t, []).append(m["content"])
        for ch, texts in topics.items():
            sample = " ".join(texts)[:900]
            doc = (f"Discord {gname} / #{ch}: member discussion distilled — "
                   f"{len(texts)} messages. {sample}")
            try:
                r = store.add(doc, topic=f"discord-{gname}",
                              receipt=f"door-extract-{gname}-{ch}")
                if r.get("status") == "novel":
                    added += 1
            except Exception:
                pass
    return added

if __name__ == "__main__":
    tok = pathlib.Path("/srv/secrets/door.env").read_text().strip() if os.path.exists("/srv/secrets/door.env") else ""
    os.environ.setdefault(TOKEN_ENV, tok)
    if not os.environ.get(TOKEN_ENV):
        print("no token"); sys.exit(1)
    gs, new = extract()
    n = distill(gs)
    if new or n:
        print(f"EXTRACT: +{new} messages across {len(gs)} guilds, +{n} novel store docs")
    else:
        print("")  # silent-until-change
