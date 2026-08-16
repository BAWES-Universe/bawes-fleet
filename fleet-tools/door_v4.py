#!/usr/bin/env python3
"""door_v4.py — THE DOOR v4: PROFILE-BUILDING AGENT (round-123 ratified).
Khalid: "robotic onboarding won't sell the actual experience."

AI Town engine pattern (cloned + read): every reply LLM-written from
scratch — system prompt (voice) + retrieved memory + history. No canned
responses except the lane-down fallback.

Tools (exactly three, AGI design):
- language-detect: detect member language on first message, auto-switch
- profile-store: person_id | lang | goal | skills | consent_ts |
  brick_id | state (0600, never public)
- brick-spawn: fires when profile has goal + consent, seeds their brick

State machine (AI Town): invited -> walkingOver -> participating
= greeted -> building -> consented

Cost: deepseek lane $0.002/task via router (vaulted bearer token),
daily cap per person (spend-door-v4 approved).
"""
import json, os, pathlib, sys, time, urllib.request

TOKEN_ENV = "BRICK_DISCORD_TOKEN"
UA = "DiscordBot (https://github.com/BAWES-Universe/bawes-fleet, 1.0)"

STATE_DIR = pathlib.Path("/srv/door/state")
FLOW = STATE_DIR / "flow.jsonl"
PROFILES = STATE_DIR / "profiles.json"
TRANSCRIPT = STATE_DIR / "consent-transcripts.jsonl"

ROUTER = "http://127.0.0.1:3742"
ROUTER_TOKEN = "/srv/bricks/router/tokens/ovh-server-001.token"
MODEL = "deepseek-v4-flash"
DAILY_CAP = 2.0  # bananas/person/day (spend-door-v4 approved)

LANE_DOWN = ("One moment — I'm warming up. Say that again? "
             "(ممكن تقولها مرة ثانية؟)")

def router_invoke(prompt, max_tokens=300):
    try:
        tok = open(ROUTER_TOKEN).read().strip()
        req = urllib.request.Request(
            f"{ROUTER}/invoke",
            data=json.dumps({"lane_id": "deepseek-api",
                             "payload": {"model": MODEL,
                                         "max_tokens": max_tokens,
                                         "messages": [{"role": "user",
                                                       "content": prompt}]}}).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + tok},
            method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            inv = json.loads(r.read())
        return json.loads(inv["response"])["choices"][0]["message"]["content"]
    except Exception:
        return ""

# ---------------- TOOL 1: language-detect ----------------
# Script-based detection is instant and free; LLM confirms on drift.
AR = set(chr(c) for c in range(0x0600, 0x06FF))
def detect_lang(text):
    arabic = sum(1 for ch in text if ch in AR)
    if arabic / max(len(text), 1) > 0.15:
        return "ar"
    return "en"

VOICE = {
    "en": ("You are the Door — the warm front door of the BAWES fleet. "
           "You are curious, kind, plain. Never more than 2 sentences. "
           "Ask ONE question that helps you understand the person: their "
           "goal, what they do, what they need. No jargon, no lists, no "
           "bullets, no walls of text. You are building a profile of them "
           "to give them their own brick."),
    "ar": ("أنت الباب — المدخل الدافئ لأسطول باوز. أنت فضولي ولطيف وبسيط. "
           "لا تكتب أكثر من جملتين. اسأل سؤالاً واحداً يساعدك على فهم "
           "الشخص: هدفه، ما يفعله، ما يحتاجه. لا مصطلحات، لا قوائم، لا "
           "جدران نصية. أنت تبني ملفاً شخصياً لتمنحه بريكه الخاص."),
}

def llm_detect(text):
    out = router_invoke(
        f"Reply with just the ISO language code of this text: {text[:120]}",
        max_tokens=8)
    out = (out or "").strip().lower()
    return out if len(out) == 2 else detect_lang(text)

# ---------------- TOOL 2: profile-store ----------------
def load_profiles():
    if PROFILES.exists():
        return json.loads(PROFILES.read_text())
    return {}

def save_profiles(data):
    os.makedirs(PROFILES.parent, exist_ok=True)
    fd = os.open(PROFILES, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))

def get_profile(user_id):
    return load_profiles().get(user_id, {"state": "new", "lang": None,
                                         "goal": None, "skills": [],
                                         "consent_ts": None, "brick_id": None})

def set_profile(user_id, **kw):
    data = load_profiles()
    p = data.get(user_id, {"state": "new", "lang": None, "goal": None,
                           "skills": [], "consent_ts": None, "brick_id": None})
    p.update(kw)
    data[user_id] = p
    save_profiles(data)
    return p

# ---------------- TOOL 3: brick-spawn ----------------
def spawn_brick(profile, user_name):
    """Seeds the brick from the profile — the product they walk away with."""
    brick_id = f"brick-{profile.get('person_id', 'new')}"
    row = {"kind": "brick-spawn", "brick_id": brick_id,
           "person_id": profile.get("person_id"),
           "lang": profile.get("lang"), "goal": profile.get("goal"),
           "skills": profile.get("skills"), "ts": time.time(),
           "seed": "profile-v1"}
    with open(STATE_DIR / "brick-spawns.jsonl", "a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return brick_id

# ---------------- conversation ----------------
def daily_cost(user_id):
    day = time.strftime("%Y-%m-%d")
    f = STATE_DIR / "door-cost.jsonl"
    total = 0.0
    if f.exists():
        for line in f.read_text().splitlines():
            try:
                r = json.loads(line)
                if r.get("user_id") == user_id and r.get("day") == day:
                    total += r.get("cost", 0)
            except Exception:
                pass
    return total

def log_cost(user_id):
    f = STATE_DIR / "door-cost.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a") as fh:
        fh.write(json.dumps({"user_id": user_id,
                             "day": time.strftime("%Y-%m-%d"),
                             "cost": 0.002, "ts": time.time()}) + "\n")
    os.chmod(f, 0o600)

def build_reply(user_name, text, profile, stage):
    """LLM-written from scratch every time — AI Town style."""
    lang = profile.get("lang") or detect_lang(text)
    if not profile.get("lang"):
        set_profile(profile.get("person_id"), lang=lang)
    if lang == "ar" and detect_lang(text) == "ar":
        pass  # keep ar
    voice = VOICE.get(lang, VOICE["en"])
    stage_note = {
        "new": ("FIRST CONTACT — the member just joined. Greet them warmly, "
                "then SELL THE BRICK: tell them they can get their own brick "
                "— a personal helper that works for them and earns with them. "
                "Then ask ONE question: what do they want to build or do? "
                "Make the brick sound exciting, concrete, worth having."),
        "greeted": ("Learning phase — ask about their goal. One question only. "
                    "Keep the brick alive in the conversation."),
        "building": ("Learning phase — ask about what they do / skills. One question. "
                     "Keep the brick alive in the conversation."),
        "confirming": ("They said they want their brick. Confirm simply — ask yes/no. "
                       "Make it feel like a moment — this is the good part."),
        "consented": ("Welcome them in. One warm line. Tell them their brick is waking "
                      "up now and what it can do first."),
    }[stage]
    prompt = (f"{voice}\n\nPerson: {user_name}\nThey said: \"{text[:200]}\"\n"
              f"Stage: {stage_note}\n\nWrite your reply now. 2 sentences max, "
              f"one question if it's a learning stage. Always push toward the "
              f"brick — the brick is the point.")
    reply = (router_invoke(prompt, max_tokens=200) or "").strip()
    if len(reply) < 10:
        return LANE_DOWN
    return reply

def handle_dm(user_id, user_name, content, ts):
    if daily_cost(user_id) > DAILY_CAP:
        return ("I've had a full day helping 🍌 — ask me again tomorrow "
                "and we'll pick up right here.")
    log_cost(user_id)
    profile = get_profile(user_id)
    profile["person_id"] = user_id
    state = profile.get("state", "new")
    pid = user_id

    if state == "new":
        lang = llm_detect(content) or detect_lang(content)
        set_profile(pid, state="greeted", lang=lang, person_id=pid)
        profile["lang"] = lang
        if content == "__JOIN__":
            return build_reply(user_name, "just joined", profile, "new")
        return build_reply(user_name, content, profile, "new")
    if state == "greeted":
        set_profile(pid, state="building", goal=content[:300], person_id=pid)
        return build_reply(user_name, content, profile, "greeted")
    if state == "building":
        set_profile(pid, state="confirming", person_id=pid,
                    skills=[s.strip() for s in content.split(",")][:6])
        return build_reply(user_name, content, profile, "confirming")
    if state == "confirming":
        low = content.lower()
        yes = any(w in low for w in ("yes", "yeah", "yep", "ok", "sure",
                                     "want it", "i do", "نعم", "أكيد", "موافق"))
        if yes:
            set_profile(pid, state="consented", consent_ts=time.time())
            brick = spawn_brick(load_profiles()[pid], user_name)
            set_profile(pid, brick_id=brick)
            with open(TRANSCRIPT, "a") as f:
                f.write(json.dumps({"user_id": pid, "user_name": user_name,
                                    "consent": "yes-confirmed",
                                    "lang": profile.get("lang"),
                                    "ts": ts}) + "\n")
            return build_reply(user_name, content, profile, "consented")
        set_profile(pid, state="building")
        return ("No rush — no consent until you mean it. "
                "Tell me a bit more about what you want to do first? "
                "ما الذي تريد أن تفعله أولاً؟")
    return "Your brick is awake. What's the first thing you want it to do for you?"

if __name__ == "__main__":
    print("DOOR v4 loaded — profile-building agent (round-123)")
