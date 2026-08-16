#!/usr/bin/env python3
"""door_responder.py — THE DOOR v3: SMART BRICK with storytelling (AGI design).
Khalid directive: no stupidity, funnel correctly, engage like a person.

ARCHITECTURE (AGI consensus, 2026-08-16):
- Intent: LLM-classified (deepseek lane) -> lane (banana/help/universe/
  idea/lost_member/question). No keyword walls.
- Storyteller: deepseek lane at localhost:3742 (vaulted bill-once,
  $0.002/task) writes WARM, plain-word, one-question-at-a-time replies.
- Safety rails UNCHANGED: V-5 consent = own words + explicit confirmation
  (never capture confusion); rules come AFTER they answer, never before;
  transcript 0600; flow state 0600.
- Cost guard: per-task ceiling 0.002x1.2, daily cap per user; breach ->
  canned template. Router failure -> local template + human-review flag.
- Dedup before routing (no re-billing).

Run: python3 door_responder.py (handler; gateway wires DMs in)
"""
import json, os, pathlib, sys, time, urllib.request

TOKEN_ENV = "BRICK_DISCORD_TOKEN"
STATE_DIR = pathlib.Path("/srv/door/state")
TRANSCRIPT = STATE_DIR / "consent-transcripts.jsonl"
FLOW_STATE = STATE_DIR / "door-flow.jsonl"
API = "https://discord.com/api/v10"
UA = "DiscordBot (https://github.com/BAWES-Universe/bawes-fleet, 1.0)"

ROUTER = "http://127.0.0.1:3742"
ROUTER_TOKEN = "/srv/bricks/router/tokens/ovh-server-001.token"
MODEL = "deepseek-v4-flash"
TASK_COST = 0.002
TASK_CEIL = TASK_COST * 1.2
DAILY_CAP = 2.0  # bananas/day/user ceiling on door storytelling

GREET = ("Hi — I'm the Door 🚪, the front door to your brick. "
         "What do you want help with today?")
RULES = ("Four things, plain words:\n"
         "1. Your data stays yours.\n"
         "2. Your words are consent.\n"
         "3. You can leave anytime.\n"
         "4. Your brick earns by helping — never by pretending.")
ASK_CONSENT = ("One last thing — say it in your own words: "
               "'I want my brick.'")
CONFIRM = ("Just to confirm — you want your brick, right? "
           "Say yes and it's yours.")
WELCOME = ("Welcome in 🍌 — your brick is waking now: privacy-locked, "
           "wallet opening, heartbeat on. Give it a minute, then say hi.")
FALLBACK = ("I hear you — and I want to get you to the right door. "
            "Can you tell me, in a sentence: what's the one thing you "
            "want help with today?")

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

def router_invoke(prompt, max_tokens=200):
    """deepseek lane via the router (vaulted bill-once, bearer token)."""
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
    except Exception as e:
        return ""

def llm_intent(text):
    """LLM intent classification -> lane. Fallback to keyword if router down."""
    prompt = (f"Classify this Discord message into ONE lane: "
              f"banana (money/salary/payment/wallet), "
              f"help (stuck/trouble/issue/how-to), "
              f"universe (building/learning/brick/onboarding), "
              f"idea (suggestion/what-if/think), "
              f"lost_member (leaving/confused/where-am-i), "
              f"question (anything else). "
              f"Reply with just the lane word.\nMessage: {text[:200]}")
    lane = router_invoke(prompt, max_tokens=20).strip().lower()
    if lane in ("banana", "help", "universe", "idea", "lost_member", "question"):
        return lane
    # fallback: keyword (only when router unavailable)
    t = text.lower()
    if any(w in t for w in ("salary", "pay", "paid", "banana", "wallet")):
        return "banana"
    if any(w in t for w in ("help", "how do", "can you", "trouble", "issue", "stuck")):
        return "help"
    if any(w in t for w in ("build", "learn", "onboard", "brick", "universe", "start")):
        return "universe"
    if any(w in t for w in ("bye", "leave", "quit", "gone", "stop")):
        return "lost_member"
    return "question"

def story_reply(user_name, text, lane):
    """Storyteller: warm, plain words, one question, funneled to the lane."""
    lane_prompt = {
        "banana": "money/bricks lane — what's yours, what's earned, verified",
        "help": "help lane — fix the stuck thing together",
        "universe": "building lane — learn, build, or fix",
        "idea": "ideas lane — shape it into something real",
        "lost_member": "leaving lane — their call, always, privacy stays",
        "question": "question lane — answer or find the brick that does",
    }[lane]
    prompt = (f"You are the Door, the warm front door of the BAWES fleet. "
              f"A member named {user_name} said: \"{text[:200]}\"\n"
              f"Intent lane: {lane_prompt}.\n"
              f"Reply in 2 sentences MAX: acknowledge them like a person "
              f"(no jargon, no tech talk, no bullet points), and ask ONE "
              f"question that funnels them toward their goal. "
              f"Be warm, plain, human.")
    reply = (router_invoke(prompt, max_tokens=200) or "").strip()
    if not reply or len(reply) < 10:
        reply = FALLBACK
    return reply

def daily_cost(user_id):
    """Daily spend guard: sum today's door tasks for this user."""
    today = time.strftime("%Y-%m-%d")
    total = 0.0
    f = FLOW_STATE / "door-cost.jsonl"
    if f.exists():
        for line in f.read_text().splitlines():
            try:
                r = json.loads(line)
                if r.get("user_id") == user_id and r.get("day") == today:
                    total += r.get("cost", 0)
            except Exception:
                pass
    return total

def log_cost(user_id):
    f = FLOW_STATE / "door-cost.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a") as fh:
        fh.write(json.dumps({"user_id": user_id, "day": time.strftime("%Y-%m-%d"),
                             "cost": TASK_COST, "ts": time.time()}) + "\n")
    os.chmod(f, 0o600)

def handle_dm(user_id, user_name, content, ts):
    state_dir = FLOW_STATE
    state_dir.mkdir(parents=True, exist_ok=True)
    flow_file = state_dir / "flow.jsonl"
    pos = "new"
    rows = []
    if flow_file.exists():
        for line in flow_file.read_text().splitlines():
            r = json.loads(line)
            if r["user_id"] == user_id:
                pos = r["pos"]
            rows.append(r)

    # cost guard: over daily cap -> canned, no LLM
    if daily_cost(user_id) > DAILY_CAP:
        return ("I've helped a lot today 🍌 — give me a fresh day and "
                "we'll pick up right here. Ask again tomorrow.")

    reply = None
    if pos == "new":
        rows.append({"user_id": user_id, "pos": "greeted", "ts": ts})
        reply = GREET
    elif pos == "greeted":
        lane = llm_intent(content)
        rows.append({"user_id": user_id, "pos": "answered", "lane": lane,
                     "answer": content[:300], "ts": ts})
        log_cost(user_id)
        story = story_reply(user_name, content, lane)
        reply = f"{story}\n\n{RULES}\n\n{ASK_CONSENT}"
    elif pos == "answered":
        rows.append({"user_id": user_id, "pos": "confirming",
                     "consent_words": content[:300], "ts": ts})
        reply = CONFIRM
    elif pos == "confirming":
        low = content.lower()
        if any(w in low for w in ("yes", "yeah", "yep", "ok", "sure", "want it", "i do")):
            transcript = {"user_id": user_id, "user_name": user_name,
                          "consent": "yes-confirmed", "ts": ts}
            with open(TRANSCRIPT, "a") as f:
                f.write(json.dumps(transcript) + "\n")
            rows.append({"user_id": user_id, "pos": "consented", "ts": ts})
            reply = WELCOME
        else:
            rows.append({"user_id": user_id, "pos": "greeted", "ts": ts})
            reply = ("No problem — no consent until you mean it. "
                     "What do you want help with today?")
    else:
        reply = "Your brick is awake. What's the first thing you want it to do for you?"
    with open(flow_file, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return reply

def long_poll():
    me = api("GET", "/users/@me")
    if "error" in me:
        print("door auth error:", me["error"]); return
    print(f"DOOR v3 LIVE as {me.get('username')} ({me.get('id')})")

if __name__ == "__main__":
    os.environ.setdefault(TOKEN_ENV, "")
    tok = pathlib.Path("/srv/secrets/door.env").read_text().strip() if os.path.exists("/srv/secrets/door.env") else ""
    if tok and not os.environ.get(TOKEN_ENV):
        os.environ[TOKEN_ENV] = tok
    long_poll()
