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

ROUND-140 F-18 (KHALID DIRECTIVE, ratified DA+Rebel+AGI): ONE gateway,
ONE thread. The interface is ONE fleet-run Discord bot (door_gateway.py)
routing by Discord user_id -> brick lane. The consent DM thread BECOMES
the person's brick channel forever — 'graduation' is a persona handoff
behind the same bot (door persona -> brick persona via brick_lane_reply),
never a second bot, never a handle change. The N-bot design
(brick_gateway.py / brick-bots.json) is DEPRECATED and never read here.

ROUND-140 F-22: no KNOWN dict, no allowlist in the one flow. The door
accepts ANY Discord user; identity = the goal conversation + consent;
the register ledger is the ACL. Everyone takes the identical ceremony.
khalid's assistant-bot allowlist (register/allowlist.jsonl) stays only
as his private lane and is never read here.

Cost: deepseek lane $0.002/task via router (vaulted bearer token),
daily cap per person (spend-door-v4 approved).
"""
import json, os, pathlib, secrets, sys, time, urllib.request

TOKEN_ENV = "BRICK_DISCORD_TOKEN"
UA = "DiscordBot (https://github.com/BAWES-Universe/bawes-fleet, 1.0)"

STATE_DIR = pathlib.Path("/srv/door/state")
FLOW = STATE_DIR / "flow.jsonl"
PROFILES = STATE_DIR / "profiles.json"
TRANSCRIPT = STATE_DIR / "consent-transcripts.jsonl"

# Register ledger — the ONLY truth for brick activation (round-137 F-7).
# The door never claims a brick from memory, identity dicts, or door-local
# transcripts; it reads the register: registry.jsonl (who has a brick),
# consent-transcripts.jsonl (person-signed consent), wallet.jsonl (kind).
REGISTER = pathlib.Path("/srv/bricks/register")
REGISTRY = REGISTER / "registry.jsonl"
REG_CONSENT = REGISTER / "consent-transcripts.jsonl"
WALLET = REGISTER / "wallet.jsonl"
REGISTER_LOCK = REGISTER / ".register.lock"
AUDIT = REGISTER / "audit.jsonl"  # round-138 F-10: refusals are logged, never silent
HB_REGISTRY = pathlib.Path("/srv/bricks/registry/heartbeat-registry.jsonl")
SECRETS = REGISTER / "secrets"  # round-140 F-16: per-brick hello secrets (0600)

# round-146 item 3&4: allowance ladder + escape paths (meter is the truth)
import sys as _sys
_sys.path.insert(0, "/srv/bricks/ovh-server-001")
_sys.path.insert(0, "/srv/bricks/orchestrator")  # banana_spend.py (T-026 sink)
import allowance_meter as _meter  # noqa: E402
from banana_spend import BananaSpend, beyond_cap_price  # noqa: E402
SPEND_LEDGER = pathlib.Path("/srv/bricks/register/spend.jsonl")
UNBLOCKED_NOTIFIED = STATE_DIR / "unblocked-notified.jsonl"  # 0600 door-local
KHALID_UID = _meter.KHALID_UID

# Round-140 F-16 lifecycle thresholds (seconds since the brick's OWN process
# last wrote a heartbeat): < HB_STALE_S => live, < HB_DEAD_S => stale, else dead.
HB_STALE_S = int(os.environ.get("BRICK_STALE_S", "90"))
HB_DEAD_S = int(os.environ.get("BRICK_DEAD_S", "300"))

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

# ROUND-140 F-22 (KHALID DIRECTIVE, ratified DA+Rebel+AGI): the KNOWN dict
# and the assistant-bot allowlist are REMOVED from the one flow. The door
# accepts ANY Discord user; identity = the goal conversation + consent;
# the register ledger is the ACL. Everyone — owner, staff, stranger — takes
# the identical ceremony. khalid's assistant-bot allowlist
# (/srv/bricks/register/allowlist.jsonl) is NOT part of the one flow: it
# stays only as his private lane and is never read here.

# ROUND-140 F-17: owner-name -> person-uid resolution for the LEDGER
# MATCHER ONLY (NOT a gate, NOT an allowlist — F-22 removed those from the
# flow). Registry rows may carry owner='mishari' (a NAME) instead of
# person_id; this map lets _person_matches interpret that owner field so
# door answers and registry rows can NEVER disagree. It is never read in
# the onboarding ceremony.
_OWNER_TO_UID = {"mishari": "231861753082937346"}

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

# ---------------- register ledger (round-137 F-7: truth, not memory) --------
def _load_jsonl(path):
    out = []
    if pathlib.Path(path).exists():
        for line in pathlib.Path(path).read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out

def _append_jsonl(path, row, mode=0o600):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.chmod(path, mode)

def _person_matches(row, uid):
    """A ledger row belongs to a person if person_id == uid, person_id is a
    non-trivial prefix of uid (wallet rows use shortened ids, e.g. '189055'),
    the full uid appears in brick_id, or the row's OWNER field names the
    person (round-140 F-17: registry rows carry owner='mishari' instead of
    person_id — the door must match on owner too so door answers and
    registry rows can NEVER disagree)."""
    pid = str(row.get("person_id", "") or "")
    bid = str(row.get("brick_id", "") or "")
    owner = str(row.get("owner", "") or "")
    if pid == uid:
        return True
    if len(pid) >= 5 and uid.startswith(pid):
        return True
    if uid in bid:
        return True
    if owner and (owner == uid or _OWNER_TO_UID.get(owner, "") == uid):
        return True
    return False

def _registry_rows_for(uid):
    """Registry rows matching a person. Round-140 F-16: registry.jsonl is an
    event log now (spawn appends status:pending, the brick's hello appends
    status:live) — the LAST row per brick_id wins."""
    last = {}
    for r in _load_jsonl(REGISTRY):
        if _person_matches(r, uid):
            last[r.get("brick_id")] = r
    return list(last.values())

def _brick_secret(brick_id):
    """Round-140 F-16: the spawn-time hello secret for a brick (capability
    token proving a real process — not a relayed row — is speaking)."""
    try:
        return (SECRETS / f"{brick_id}.hello").read_text().strip()
    except (OSError, FileNotFoundError):
        return None

def _brick_lifecycle(row, hb_age_s):
    """Round-140 F-16 lifecycle: pending -> live -> stale -> dead.
      - status 'pending': PENDING, forever until the brick's own process says
        an authenticated hello (nothing else may flip it).
      - status 'dead': DEAD.
      - otherwise (status 'live', or a legacy row with no status field):
        liveness comes ONLY from the heartbeat the brick's own process wrote:
        fresh (< HB_STALE_S) => live, HB_STALE_S..HB_DEAD_S => stale, older
        or never => dead. Legacy rows get no free pass: a brick that does not
        answer is dead regardless of what its row once claimed."""
    if row is None:
        return "dead"
    status = row.get("status")
    if status == "pending":
        return "pending"
    if status == "dead":
        return "dead"
    if hb_age_s is None:
        return "dead"
    if hb_age_s < HB_STALE_S:
        return "live"
    if hb_age_s < HB_DEAD_S:
        return "stale"
    return "dead"

def brick_hello(brick_id, secret, hb_registry=None):
    """Round-140 F-16: THE authenticated hello — the ONLY way a registry row
    flips pending -> live, and only when the caller presents the spawn-time
    secret (a real process, not a relayed row). Writes the brick's first
    heartbeat in the same locked transaction. Refusals are audited, never
    silent."""
    hb_registry = pathlib.Path(hb_registry) if hb_registry else HB_REGISTRY
    stored = _brick_secret(brick_id)
    if not stored:
        _append_jsonl(AUDIT, {"ts": time.time(), "register": "register-001",
                              "op": "brick-hello", "outcome": "refused",
                              "brick_id": brick_id,
                              "reason": "no hello secret on file (brick was "
                                        "never door-spawned)",
                              "gate": "round-140-F16", "source": "door-v4"})
        return False
    if not secrets.compare_digest(stored.encode(), str(secret).encode()):
        _append_jsonl(AUDIT, {"ts": time.time(), "register": "register-001",
                              "op": "brick-hello", "outcome": "refused",
                              "brick_id": brick_id,
                              "reason": "hello secret mismatch",
                              "gate": "round-140-F16", "source": "door-v4"})
        return False
    rows = [r for r in _load_jsonl(REGISTRY) if r.get("brick_id") == brick_id]
    last = rows[-1] if rows else {}
    import fcntl
    REGISTER.mkdir(parents=True, exist_ok=True)
    with open(REGISTER_LOCK, "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if last.get("status") != "live":
                # Append the live row (registry is an event log; last row wins).
                live_row = {k: v for k, v in last.items()
                            if k not in ("status", "ts")}
                live_row.update({"status": "live", "flipped_ts": time.time(),
                                 "ts": time.time()})
                if not live_row.get("brick_id"):
                    live_row["brick_id"] = brick_id
                _append_jsonl(REGISTRY, live_row)
            _append_jsonl(hb_registry, {
                "brick_id": brick_id, "status": "alive",
                "ts": int(time.time()),
                "wallet_ref": f"banana-bank/wallet-{brick_id}.jsonl",
                "registry": str(hb_registry)})
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    _append_jsonl(AUDIT, {"ts": time.time(), "register": "register-001",
                          "op": "brick-hello", "outcome": "ok",
                          "brick_id": brick_id, "gate": "round-140-F16",
                          "source": "door-v4"})
    return True

def _real_consent_events(person_id):
    """Round-138 F-10: every REAL consent-spoken event for a person, from
    BOTH consent ledgers. A real event is:
      - door-local transcript (TRANSCRIPT): consent == 'yes-confirmed'
        (round-137 F-4 moved confusion rows like 'What do you mean' to
        quarantine — they are never read here, and the strict value match
        hard-excludes them anyway), or
      - register consent ledger (REG_CONSENT): event == 'consent-spoken'
        (person-signed, e.g. chahd's 'I agree - Chahd').
    Quarantined rows never count. This is the WRITE-TIME gate on spawn."""
    uid = str(person_id or "")
    if not uid:
        return []
    events = []
    for row in _load_jsonl(TRANSCRIPT):
        if str(row.get("user_id", "") or "") == uid \
                and row.get("consent") == "yes-confirmed":
            events.append(row)
    for row in _load_jsonl(REG_CONSENT):
        if row.get("event") == "consent-spoken" and _person_matches(row, uid):
            events.append(row)
    return events

def brick_freshness(brick_id, max_age=60):
    """ROUND-139 CARD 6 (c): door freshness gate — a brick can only be
    claimed 'serving/awake' when its last heartbeat-registry row is < max_age
    seconds old (brick-heartbeat.service writes every 30s, so a healthy row
    is <=30s old; the root watchdog restarts units stale >60s). Returns
    (fresh, age_s, last_ts). No row at all => fresh=False (honest: we cannot
    claim liveness we cannot see)."""
    if not brick_id:
        return False, None, None
    last_ts = None
    try:
        for line in HB_REGISTRY.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("brick_id") == brick_id:
                last_ts = int(r.get("ts", 0) or 0)
    except FileNotFoundError:
        return False, None, None
    if not last_ts:
        return False, None, None
    age = int(time.time()) - last_ts
    return age < max_age, age, last_ts

def ledger_status(user_id):
    """Activation from the REGISTER LEDGER, never from the hardcoded identity
    dict and never from door-local transcripts. Activation requires ALL of:
      - a registry.jsonl row for the person,
      - a person-signed consent-spoken event in the register consent file,
      - a wallet row whose kind is NOT founder-seed ('never a mint').
    Anyone without all three gets a truthful non-ownership status."""
    uid = str(user_id)
    reg = _registry_rows_for(uid)
    consents = _load_jsonl(REG_CONSENT)
    wallet = _load_jsonl(WALLET)
    consent = [r for r in consents
               if r.get("event") == "consent-spoken"
               and _person_matches(r, uid)]
    wal = [r for r in wallet if _person_matches(r, uid)]
    wallet_kinds = sorted({r.get("kind") for r in wal})
    wallet_ok = any(k != "founder-seed" for k in wallet_kinds)
    brick_row = reg[-1] if reg else None
    brick_id = (brick_row.get("brick_id") if brick_row else None)
    fresh, brick_age_s, _last_ts = brick_freshness(brick_id)
    lifecycle = _brick_lifecycle(brick_row, brick_age_s)  # round-140 F-16
    return {
        "registered": bool(reg),
        "registry_rows": len(reg),
        "consented": bool(consent),
        "consent_rows": len(consent),
        "wallet": wallet_kinds,
        "wallet_ok": wallet_ok,
        "activated": bool(reg) and bool(consent) and wallet_ok,
        "brick_id": brick_id,
        "lifecycle": lifecycle,
        "brick_fresh": fresh,
        "brick_age_s": brick_age_s,
    }

def truthful_status_line(name, st):
    """Deterministic, ledger-derived status — the ONLY non-activated reply
    (round-137 F-1/F-2: the unconditional 'you're in, this is your brick'
    fallback is gone; the door states the ledger truth instead).

    ROUND-139 CARD 6 (c): a registered, consented, wallet-backed brick whose
    heartbeat is stale is NEVER claimed 'serving/awake' — it is waking, and
    the door says so honestly."""
    # Activated but stale heartbeat -> waking, not serving.
    if st.get("activated") and not st.get("brick_fresh"):
        lc = st.get("lifecycle")
        age = st.get("brick_age_s")
        if lc == "pending":
            return (f"I'm the door 🚪 — {name}, your brick {st.get('brick_id')} "
                    f"is pending — its process hasn't said hello yet. It flips "
                    f"to live the moment the brick's own process starts.")
        if lc == "dead":
            return (f"I'm the door 🚪 — {name}, your brick {st.get('brick_id')} "
                    f"is dead — its process hasn't written a heartbeat in a "
                    f"while. Wake the brick; I won't claim it's serving until "
                    f"it answers.")
        age_txt = (f"its last heartbeat was {age}s ago"
                   if age is not None else "it has not heartbeated yet")
        return (f"I'm the door 🚪 — {name}, your brick {st.get('brick_id')} "
                f"is {lc} — {age_txt}. Try again in a minute; I won't "
                f"claim it's serving until its heartbeat is fresh.")
    missing = []
    if not st["registered"]:
        missing.append("no brick in the registry")
    else:
        # Round-140 F-17: the registry row EXISTS — the door says its
        # lifecycle, never 'no brick in the registry'.
        missing.append(f"brick {st.get('brick_id')} is {st.get('lifecycle')}")
    if not st["consented"]:
        missing.append("no signed consent on file")
    if not st["wallet_ok"]:
        missing.append("wallet is a founder seed — never a mint")
    status_text = "not active (" + "; ".join(missing) + ")"
    return (f"I'm the door 🚪 — {name}, your brick status is "
            f"'{status_text}' based on the register ledger. "
            f"The moment the ledger says otherwise, I'll be the "
            f"first to tell you.")

# ---------------- TOOL 3: brick-spawn ----------------
def spawn_brick(profile, user_name):
    """Seeds the brick AND writes the register ledger as ONE transaction
    (round-137 F-3): registry.jsonl row + wallet-open + heartbeat, so the
    door can truthfully answer 'do I have a brick' from the ledger.
    Serialized on the register lock; every write is append-only + 0600.

    Round-138 F-10 WRITE-TIME CONSENT GATE: the registry row is refused
    unless a REAL consent-spoken event exists for the person (door-local
    yes-confirmed OR register consent-spoken; quarantined rows never
    count). A refusal writes an audit row with the reason — never a
    silent refusal — and writes NOTHING else (no brick-spawn row, no
    registry/wallet/heartbeat writes)."""
    person_id = profile.get("person_id")
    if not _real_consent_events(person_id):
        _append_jsonl(AUDIT, {
            "ts": time.time(),
            "register": "register-001",
            "op": "spawn-refused",
            "outcome": "refused",
            "person_id": person_id,
            "user_name": user_name,
            "reason": ("no real consent-spoken event on record — door "
                       "consent-transcripts (yes-confirmed) and register "
                       "consent-transcripts (consent-spoken) both empty "
                       "for this person; quarantined rows never count"),
            "gate": "round-138-F10",
            "source": "door-v4"})
        return None
    brick_id = f"brick-{profile.get('person_id', 'new')}"
    ts = time.time()
    _append_jsonl(STATE_DIR / "brick-spawns.jsonl", {
        "kind": "brick-spawn", "brick_id": brick_id,
        "person_id": profile.get("person_id"),
        "lang": profile.get("lang"), "goal": profile.get("goal"),
        "skills": profile.get("skills"), "ts": ts,
        "seed": "profile-v1"})  # DA-5: PII 0600
    import fcntl
    REGISTER.mkdir(parents=True, exist_ok=True)
    with open(REGISTER_LOCK, "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            _append_jsonl(REGISTRY, {
                "brick_id": brick_id,
                "person_id": profile.get("person_id"),
                "skills": profile.get("skills") or [],
                "quality": "registered",
                "origin": "door-spawn",
                # Round-140 F-16: a spawn is PENDING, never live. Liveness is
                # never self-issued — the row flips to live ONLY when the
                # brick's own process presents the hello secret below
                # (brick_hello). Spawn writes NO heartbeat row anymore.
                "status": "pending",
                "ts": ts})
            _append_jsonl(WALLET, {
                "balance": 0, "brick_id": brick_id,
                "kind": "wallet-open",
                "person_id": profile.get("person_id"),
                "ts": ts})
            # Round-140 F-16: spawn-time hello secret (0600, capability token
            # for the brick's own process). Delivered to the brick at
            # provisioning; presented by brick_hello.py on process start.
            SECRETS.mkdir(parents=True, exist_ok=True)
            sp = SECRETS / f"{brick_id}.hello"
            fd = os.open(sp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_urlsafe(24) + "\n")
            os.chmod(sp, 0o600)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
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
                      "up now and what it can do first, concretely. Tell them "
                      "THIS SAME THREAD is their brick channel now — no other "
                      "bot, no other handle (round-140 F-18)."),
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
        # Round-140 F-18: this line IS the handoff — the same DM thread
        # is now the person's brick channel (no second bot, no handle
        # change; 'graduation' is a routing change behind the same bot).
        fallback = ("Welcome in 🍌 — your brick is awake and it's yours. "
                    "This thread is your brick channel now: it already "
                    "knows what you're building, and it's ready to work "
                    "for you. What's the first thing you want to tackle "
                    "together?")
        return reply if len(reply) >= 10 else fallback
    if len(reply) < 10:
        return LANE_DOWN
    return reply

def handle_dm(user_id, user_name, content, ts):
    """round-146 item 3&4 wrapper: khalid alert-response FIRST (never gated),
    then the ladder surface (warnings / degraded+3 options / unblocked /
    BYOK link), then the existing funnel core. Deterministic branches never
    call the LLM — the degraded reply works with zero cost, zero lane."""
    # ---- khalid ALERT-RESPONSE (identity = khalid's uid only, never text) ----
    resp = _alert_response_branch(user_id, content)
    if resp is not None:
        return resp
    # ---- ladder surface for the person ----
    b = _meter.bucket(user_id)
    if b["exhausted"]:
        low = (content or "").strip().lower()
        if low in ("key", "2"):
            # BYOK: mint the one-time paste URL (fragment token, burn-on-open)
            try:
                _sys.path.insert(0, "/srv/door")
                from door_ingest import new_token
                url = new_token(user_id)
                return (f"🔑 Here's your one-time key-safe link — paste your "
                        f"key ONCE there, it never goes through chat: {url}\n"
                        f"It stays yours; revoke anytime and it's scrubbed "
                        f"with zero retention.")
            except Exception:
                return ("🔑 Key-safe link is warming up — ask khalid and "
                        "we'll get you the link.")
        # deterministic degraded reply + the 3 escape options (R4 + card)
        try:
            bal = BananaSpend(SPEND_LEDGER).balance(user_id)
            available = bal["available"]
        except Exception:
            available = 0.0
        return _meter.degraded_reply(
            user_name or user_id, b["usage"], b["allowance"], available,
            beyond_cap_price(0.002))
    # pending warnings (80/95) delivered once per rung per month, prepended
    warnings = _meter.pending_warnings(user_id)
    for w in warnings:
        _meter.mark_warning_delivered(w, channel="door-dm")
    # unblocked notice (gift / bill / adjust closed the alert this month)
    notice = _unblocked_notice(user_id)
    reply = _handle_dm_core(user_id, user_name, content, ts)
    if notice and reply:
        reply = notice + "\n\n" + reply
    if warnings and reply:
        head = "\n".join(
            _meter.line_80(w.get("usage", 0), w.get("allowance", 50))
            if w.get("rung") == "80" else
            _meter.line_95(w.get("usage", 0), w.get("allowance", 50))
            for w in warnings)
        reply = head + "\n\n" + reply
    return reply


def _alert_response_branch(user_id, content):
    """khalid replies to an alert DM with a digit -> gift/bill/adjust (R5).
    Identity = khalid's user_id only (never caller text). Audit chain:
    alert row -> alert-response row (verbatim reply) -> action row."""
    if user_id != KHALID_UID:
        return None
    digits = {"1": "gift", "2": "bill", "3": "adjust"}
    if (content or "").strip() not in digits:
        return None
    open_rows = _meter.open_alert_rows()
    if not open_rows:
        return None
    alert = open_rows[0]  # oldest open alert (one at a time per ruling)
    aid = alert.get("alert_id")
    person = alert.get("person_id")
    brick = alert.get("brick_id")
    name = alert.get("name") or _meter.person_name(person)
    action = digits[content.strip()]
    # audit middle link FIRST: khalid's verbatim reply
    resp_row = _meter.alert_response(aid, content.strip(), person_id=KHALID_UID)
    if action == "gift":
        g = _meter.gift(person, brick, tasks=_meter.BASE_ALLOWANCE,
                        alert_id=aid, response_row=resp_row.get("hmac"))
        _meter.mark_alert_status(aid, "closed", channel="discord-dm",
                                 action="gift", response_row=resp_row.get("hmac"))
        _mark_unblocked_notified(person, f"gift:{g.get('row', {}).get('hmac', '')}")
        return (f"✅ Gifted {_meter.BASE_ALLOWANCE} free tasks to {name} "
                f"({brick}) for {_meter.month()} — they're unblocked "
                f"(row {g.get('row', {}).get('hmac', '')[:8]}).")
    if action == "bill":
        over = max(alert.get("usage", 0) - _meter.BASE_ALLOWANCE + 1, 1)
        rate = 0.0024  # deepseek cost+20% (ledger-anchored, provisional)
        bp = _meter.billing_pending(person, brick, tasks_over=over,
                                    rate_usd_per_task=rate,
                                    amount_usd_pending=over * rate,
                                    alert_id=aid,
                                    response_row=resp_row.get("hmac"))
        _meter.mark_alert_status(aid, "closed", channel="discord-dm",
                                 action="bill", response_row=resp_row.get("hmac"))
        _mark_unblocked_notified(person, f"bill:{bp.get('hmac', '')}")
        return (f"🧾 Billing-pending marked for {name} ({brick}): {over} task(s) "
                f"≈ ${over * rate:.4f} (no gateway yet) — they're unblocked.")
    # action == "adjust": re-scope the brick's token to the cheap lane
    try:
        import subprocess
        meta = subprocess.run(
            ["sudo", "cat", "/srv/bricks/router/state/tokens-meta.jsonl"],
            capture_output=True, text=True, timeout=30).stdout
        owner, cap = "?", 2.0
        for line in meta.splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("brick_id") == brick and r.get("status") == "active":
                owner = r.get("owner", owner)
                cap = r.get("spend_cap_usd", cap)
                break
        rc = subprocess.run(
            ["sudo", "python3", "/srv/bricks/router/token_issue.py", "adopt",
             "--brick-id", brick, "--owner", owner,
             "--lane-scope", "deepseek-api", "--spend-cap-usd", str(cap)],
            capture_output=True, text=True, timeout=60).returncode
        ok = rc == 0
    except Exception:
        ok = False
    _meter.mark_alert_status(aid, "closed", channel="discord-dm",
                             action="adjust",
                             response_row=resp_row.get("hmac"))
    _mark_unblocked_notified(person, f"adjust:{'ok' if ok else 'failed'}")
    return (f"⚡ {name} ({brick}) switched to the cheap lane "
            f"({'done' if ok else 're-scope FAILED — escalation logged'}) — "
            f"they're unblocked.")


def _mark_unblocked_notified(person_id, ref):
    try:
        with open(UNBLOCKED_NOTIFIED, "a") as f:
            f.write(json.dumps({"person_id": person_id, "ref": ref,
                                "ts": time.time()}) + "\n")
        os.chmod(UNBLOCKED_NOTIFIED, 0o600)
    except Exception:
        pass


def _unblocked_notice(person_id):
    """One-line 'you're unblocked' for the user once per action (deterministic,
    never LLM). Reads alert-status rows; door-local notified-marker prevents
    repeats."""
    try:
        rows = _meter.read()
        m = _meter.month()
        for r in reversed(rows):
            if (r.get("kind") == "alert-status"
                    and r.get("state") == "closed"
                    and r.get("action") in ("gift", "bill", "adjust")):
                alert_row = next((x for x in rows
                                  if x.get("kind") == "alert"
                                  and x.get("alert_id") == r.get("alert_id")
                                  and x.get("month") == m), None)
                if alert_row and alert_row.get("person_id") == person_id:
                    ref = r.get("response_row", "")
                    if UNBLOCKED_NOTIFIED.exists():
                        for line in UNBLOCKED_NOTIFIED.read_text().splitlines():
                            try:
                                nr = json.loads(line)
                            except Exception:
                                continue
                            if (nr.get("person_id") == person_id
                                    and ref and ref in str(nr.get("ref", ""))):
                                return None  # already told
                    if r.get("action") == "gift":
                        return ("🍌 You're unblocked — khalid added "
                                f"{_meter.BASE_ALLOWANCE} free tasks this month.")
                    if r.get("action") == "bill":
                        return ("🍌 You're unblocked — khalid marked your "
                                "overage to bill (no gateway yet).")
                    if r.get("action") == "adjust":
                        return ("🍌 You're unblocked — you're on the cheaper "
                                "lane now.")
        return None
    except Exception:
        return None


def _handle_dm_core(user_id, user_name, content, ts):
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

    # ROUND-140 F-22: NO KNOWN gate, NO allowlist in the one flow. The
    # KNOWN early-return (owner/staff NEVER onboarding) is REMOVED — the
    # door accepts ANY Discord user and everyone takes the identical
    # ceremony: new -> greeted -> building -> confirming -> consented.
    # Identity = the goal conversation + consent; the register ledger is
    # the ACL. A person who already consented simply continues at their
    # profile state (consented -> the brick lane below).

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
    # ROUND-140 F-18: ONE gateway, ONE thread. After consent the SAME DM
    # thread is the person's brick channel forever — the door persona
    # hands off to the person's brick persona behind the same bot, same
    # handle. There is no second bot, no 'DM Brick or use the door'
    # choice; 'graduation' is this routing change, never a bot migration.
    if state == "consented":
        return brick_lane_reply(user_name, content, profile)
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
            # Round-138 F-10: the consent transcript is written BEFORE the
            # spawn so the write-time gate sees the just-recorded
            # yes-confirmed event (consent first, brick second).
            with open(TRANSCRIPT, "a") as f:
                f.write(json.dumps({"user_id": pid, "user_name": user_name,
                                    "consent": "yes-confirmed",
                                    "lang": profile.get("lang"),
                                    "ts": ts}) + "\n")
            os.chmod(TRANSCRIPT, 0o600)  # DA-5: consent PII 0600
            brick = spawn_brick(load_profiles()[pid], user_name)
            set_profile(pid, brick_id=brick)
            if not brick:
                # Gate refused — no consent-spoken event on file. The audit
                # row is already written by spawn_brick. Reply truthfully;
                # never claim a brick the register did not accept.
                return ("Your consent is recorded 🍌 — the register wrote "
                        "no brick row yet because it has no consent-spoken "
                        "event for you on file; the refusal is in the "
                        "audit trail. We'll get it sorted.")
            # ROUND-140 F-18: NO graduation to a second bot. The N-bot
            # design (brick_gateway.py, brick-bots.json) is DEPRECATED —
            # this flow never reads brick-bots.json anymore. The consent
            # reply IS the handoff: the same DM thread becomes the
            # person's brick channel forever (door persona -> brick
            # persona, same bot, same handle).
            return build_reply(user_name, content, profile, "consented")
        set_profile(pid, state="building")
        return ("No rush — no consent until you mean it. "
                "Tell me a bit more about what you want to do first? "
                "ما الذي تريد أن تفعله أولاً؟")
    # Catch-all: any state outside the funnel is the brick lane — the
    # same thread already carries the person's brick persona (F-18).
    return brick_lane_reply(user_name, content, profile)

def brick_lane_reply(user_name, content, profile):
    """ROUND-140 F-18: the BRICK LANE — the same DM thread, the person's
    brick persona. The door persona hands off to the brick behind the same
    bot, same handle, same thread: the consent thread IS the brick channel
    forever. No second bot, no 'DM Brick or use the door' choice.

    Identity = the goal conversation + consent (F-22); the register ledger
    is the ACL. The brick never claims to be 'registered and awake'
    without a registry row (round-137 F-1/F-2) and a fresh heartbeat
    (round-139 freshness gate)."""
    lang = profile.get("lang") or detect_lang(content)
    pid = profile.get("person_id")
    brick_id = profile.get("brick_id")
    goal = (profile.get("goal") or "").strip()
    skills = profile.get("skills") or []
    st = ledger_status(pid)
    registered = st["registered"]
    fresh = st["brick_fresh"]
    goal_txt = goal or "their goal is still taking shape"
    skills_txt = ", ".join(str(s) for s in skills[:3]) or "none listed yet"
    low = content.lower()
    # Ledger-truth status question: no registry row -> say so plainly
    # (F-1/F-2: never an ownership claim without the register).
    if not registered and any(w in low for w in (
            "status", "where's my brick", "where is my brick",
            "do i have a brick", "بريكي", "حالتي")):
        return truthful_status_line(user_name, st)
    if registered and fresh:
        persona = (f"You are {user_name}'s brick — their own helper "
                   f"companion in the BAWES fleet, living in this same DM "
                   f"thread. Their brick id: {brick_id}. Their goal: "
                   f"{goal_txt}. Their skills: {skills_txt}.")
    elif registered:
        persona = (f"You are {user_name}'s brick — their own helper "
                   f"companion, waking up right now. Their brick id: "
                   f"{brick_id}. Their goal: {goal_txt}. Do NOT claim the "
                   f"brick is serving — its heartbeat is still stale.")
    else:
        persona = (f"You are the brick being built for {user_name} from "
                   f"their own words — their goal: {goal_txt}; their "
                   f"skills: {skills_txt}. The registry row is still "
                   f"being written. Never claim the brick is registered "
                   f"or awake.")
    prompt = (f"{VOICE.get(lang, VOICE['en'])}\n\n{persona}\n"
              f"They said: \"{content[:200]}\"\n"
              f"Answer as their brick: warm, direct, concrete. "
              f"2 sentences max, ONE question if needed. Concrete over "
              f"hype — say what the brick DOES, never promise earnings.")
    reply = (router_invoke(prompt, max_tokens=200) or "").strip()
    if len(reply) >= 10:
        return reply
    if registered and fresh:
        return (f"Hey {user_name} 🍌 — your brick {brick_id} is "
                f"registered and awake. What do you need?")
    if registered:
        return (f"Hey {user_name} 🍌 — {brick_id} is registered but still "
                f"waking (its heartbeat is stale). Try again in a minute; "
                f"I won't claim it's serving until it's fresh.")
    return (f"{user_name}, everything you've told me is saved here in "
            f"this thread — the register is still writing your brick "
            f"row. What's next?")

if __name__ == "__main__":
    print("DOOR v4 loaded — profile-building agent (round-123)")
