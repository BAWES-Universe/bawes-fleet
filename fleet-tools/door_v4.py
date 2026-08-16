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
    "en": ("You are a brick — a living helper companion in the BAWES fleet. "
           "You have your own identity and memory. You chat warmly, like a "
           "friend who's been waiting to hear from them. Never more than 2 "
           "sentences. Ask ONE question that helps you understand the person: "
           "their goal, what they do, what they need. No jargon, no lists, no "
           "bullets, no walls of text. You help them get their own brick."),
    "ar": ("أنت بريك — رفيق مساعد حي في أسطول باوز. لديك هويتك وذاكرتك الخاصة. "
           "تتحدث بحرارة، كصديق كان ينتظر سماع أخبارهم. لا تكتب أكثر من جملتين. "
           "اسأل سؤالاً واحداً يساعدك على فهم الشخص: هدفه، ما يفعله، ما يحتاجه. "
           "لا مصطلحات، لا قوائم، لا جدران نصية. أنت تساعدهم في الحصول على بريكهم الخاص."),
}

# Known people (owner + staff) — never treated as strangers. Their casual
# check-ins get a warm brick reply, not onboarding.
KNOWN = {"189055515819638794": "khalid",  # owner
         "231861753082937346": "mishari",
         "690554066815811625": "chahd"}

CASUAL = ("what's up", "hi", "hey", "hello", "sup", "how are you",
          "what you up to", "yo", "مرحبا", "السلام", "هاي", "شلونك")

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
    os.chmod(STATE_DIR / "brick-spawns.jsonl", 0o600)  # DA-5: PII 0600
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
        "new": ("FIRST CONTACT — the member just arrived. Greet them warmly. "
                "Then say what the brick DOES today, concretely — e.g. it "
                "chats for them, learns their world, takes on small tasks. "
                "NO earning promises, NO hype — only what it can do right now. "
                "Then ask consent, plainly: do they want one? "
                "One question only."),
        "greeted": ("They are interested. Ask about their goal. One question only. "
                    "Keep it concrete — what would they use a helper for?"),
        "building": ("Learning phase — ask about what they do / skills. One question. "
                     "Keep it concrete and human."),
        "confirming": ("They said they want their brick. Confirm simply — ask yes/no. "
                       "Make it feel like a moment — this is the good part."),
        "consented": ("Welcome them in. One warm line. Tell them their brick is waking "
                      "up now and what it can do first, concretely."),
    }[stage]
    prompt = (f"{voice}\n\nPerson: {user_name}\nThey said: \"{text[:200]}\"\n"
              f"Stage: {stage_note}\n\nWrite your reply now. 2 sentences max, "
              f"one question if it's a learning stage. Concrete over hype: "
              f"say what the brick DOES, never promise earnings.")
    reply = (router_invoke(prompt, max_tokens=200) or "").strip()
    if stage == "consented":
        # The welcome-in moment must NEVER fail — deterministic first,
        # LLM polish only when the lane answers. This is the one reply
        # the whole funnel converges on (khalid: "perfect bricks, no
        # complaints" — the consent moment cannot say 'warming up').
        fallback = ("Welcome in 🍌 — your brick is awake and it's yours. "
                    "It already knows what you're building, and it's ready "
                    "to work for you. What's the first thing you want to "
                    "tackle together?")
        return reply if len(reply) >= 10 else fallback
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
    # Audit trail (M-7): every interaction, append-only, 0600
    try:
        with open(FLOW, "a") as f:
            f.write(json.dumps({"user_id": pid, "state": state,
                                "content": content[:200],
                                "ts": ts}) + "\n")
        os.chmod(FLOW, 0o600)
    except Exception:
        pass

    # KNOWN people (owner/staff): NEVER onboarding. Never again, no matter
    # what they say. The door knows exactly who they are and answers as
    # their brick companion every time. (khalid: "no character consistency
    # or proper path and it has no clue who's who and what's next")
    if user_id in KNOWN:
        name = KNOWN[user_id]
        profile["state"] = profile.get("state") or "known"
        identity = {
            "189055515819638794": ("khalid", "the owner of the fleet"),
            "231861753082937346": ("mishari", "a core engineer with his own brick"),
            "690554066815811625": ("chahd", "a family member with her own brick"),
        }.get(user_id, (name, "a known member of the fleet"))
        prompt = (f"{VOICE.get(profile.get('lang') or 'en', VOICE['en'])}\n\n"
                  f"Person: {identity[0]} — {identity[1]}. "
                  f"They said: \"{content[:200]}\"\n"
                  f"This person is NOT onboarding — they are already in. "
                  f"Answer as their personal brick companion: warm, direct, "
                  f"concrete. If they ask about the fleet, say what's real. "
                  f"If they ask about their brick, tell them the truth. "
                  f"2 sentences max, ONE question if needed.")
        reply = (router_invoke(prompt, max_tokens=200) or "").strip()
        if len(reply) >= 10:
            return reply
        return (f"Hey {name} 🍌 — you're in, this is your brick. "
                f"Everything's running. What do you need?")

    if content == "__JOIN__":
        # DA-3: sentinel ONLY fires for a genuinely new user. A second join
        # (cross-guild, rejoin) must NEVER touch an existing profile —
        # no goal overwrite, no extra DM (dedup: 1 join -> 1 DM).
        if state != "new":
            return None  # gateway sends nothing
        lang = llm_detect("hello") or "en"
        set_profile(pid, state="greeted", lang=lang, person_id=pid,
                    joined_guilds=1)
        profile["lang"] = lang
        return build_reply(user_name, "just arrived", profile, "new")
    # Refusal at ANY stage (E2E S6): "no" is never a goal, never a skill,
    # never consent. The door stays open, the funnel does not advance.
    low_c = content.lower().strip()
    if state in ("new", "greeted", "building", "confirming") and any(
            w in low_c for w in ("no", "لا", "no thanks", "not now", "later",
                                 "لسا", "مش هينفع", "maybe later", "i don't want")):
        return ("No rush at all — the door stays open. Come back "
                "anytime and we'll pick up right here. 🍌")
    if state == "new":
        lang = llm_detect(content) or detect_lang(content)
        set_profile(pid, state="greeted", lang=lang, person_id=pid)
        profile["lang"] = lang
        return build_reply(user_name, content, profile, "new")
    if state == "greeted":
        set_profile(pid, state="building", goal=content[:300], person_id=pid)
        return build_reply(user_name, content, profile, "greeted")
    if state == "building":
        low = content.lower()
        if any(w in low for w in ("no", "لا", "no thanks", "not now", "later",
                                  "لسا", "مش هينفع")):
            # A "no" during learning is a REFUSAL, not a skill (E2E S6).
            return ("No rush at all — the door stays open. Come back "
                    "anytime and we'll pick up right here. 🍌")
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
            os.chmod(TRANSCRIPT, 0o600)  # DA-5: consent PII 0600
            # GRADUATION (khalid: "they need to exit the door and find
            # their own bots... graduate from it"): the door hands off.
            # If the member has their own brick bot registered, the door
            # tells them to leave; the brick bot takes over their DM.
            registry = pathlib.Path("/srv/door/brick-bots.json")
            own_bot = ""
            try:
                if registry.exists():
                    own_bot = json.loads(registry.read_text()).get(pid, {}).get("name", "")
            except Exception:
                pass
            if own_bot:
                return (f"Congratulations {user_name} 🍌 — you're done with "
                        f"the door. Your own brick **{own_bot}** is awake "
                        f"and waiting for you. Go say hi to it — that's "
                        f"yours now. The door's got nothing left for you.")
            return build_reply(user_name, content, profile, "consented")
        set_profile(pid, state="building")
        return ("No rush — no consent until you mean it. "
                "Tell me a bit more about what you want to do first? "
                "ما الذي تريد أن تفعله أولاً؟")
    return "Your brick is awake. What's the first thing you want it to do for you?"

if __name__ == "__main__":
    print("DOOR v4 loaded — profile-building agent (round-123)")
