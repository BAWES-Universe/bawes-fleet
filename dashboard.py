#!/usr/bin/env python3
"""
BAWES FLEET DASHBOARD v3 — OVH box :3999
BAWES-branded, login-page + HMAC session auth, money-first. Reads REAL fleet
data only: heartbeat registry, wallet, vector store, door-cost ledger, spend
balances, GitHub API, shared work queue, Hermes session DBs. Nothing is
invented; anything not measurable is labelled "not yet instrumented".

Auth (v3, replaces HTTP Basic):
  - GET /login serves a phone-first BAWES login form (username + password).
  - POST /login verifies against users.json (scrypt hash, 0600) and sets an
    HMAC-signed session cookie `bawes_session` (secret in session.key, 0600;
    TTL 12h; HttpOnly; SameSite=Lax; no Secure flag because :3999 is served
    over plain http as well as https://fleet.bawes.net via Caddy).
  - Every route except /login, /logout and /favicon.ico requires a valid
    session: HTML routes -> 302 /login, /api/* -> 401 JSON. No WWW-Authenticate
    header anywhere (no browser basic-auth popup).
  - Roles (v14): owner (khalid — everything incl. role-granting via /api/roles, money,
    approvals final authority) | decision_maker (approve/reject cards routed to their lanes:
    studenthub, plugn — mishari is CTO of both) | contributor (read-only) | brick_issuer
    (can issue bricks to people). Role + lanes come from users.json at request time (changes
    apply immediately; removed users lose access immediately).
  - Users managed by gen_user.py (add/remove/change/list) — atomic writes,
    validates username/password, refuses to remove the last owner.

Approvals (/approvals): khalid's decision-card queue — approve/reject/feedback from the
phone. Append-only JSONL (approval-cards.jsonl) + local decisions-ledger.jsonl + the
canonical GitHub decisions ledger (BAWES-Universe/bawes-knowledge decisions/ledger.md).

Money truth:
  - spend.jsonl            daily provider balances (deepseek/openrouter) — synced from control host
  - door-cost.jsonl        metered USD spend per door call ($0.002 deepseek-flash)
  - ledger-cost-rows.log   banana-priced dispatch log (NOT usd)
  - /srv/vault/nous.env    khalid's paid Nous key — NOT on this box (control host); usage not metered here
  - OVH VPS invoice        not derivable from box files

Threads truth:
  - /home/ubuntu/.hermes/profiles/door/state.db  door-profile Hermes sessions (sqlite, read-only)
  - gateway_state.json     gateway snapshot (stale)
  - /proc scan             live fleet python processes
  - Hermes Cloud instance spec (8 vCPU / 4 GB / 20 concurrent ≈ $1.09/day) — Nous plan, per fleet notes
"""
import json, os, re, time, hmac, hashlib, base64, secrets, datetime, html, urllib.request, urllib.error, urllib.parse, threading, collections, subprocess, fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

HOST, PORT = "0.0.0.0", 3999
BASE = "/srv/build/fleet-dashboard"
USERS_FILE = os.path.join(BASE, "users.json")        # [{username, salt, hash, role, created}] — 0600, gen_user.py
SESSION_KEY_FILE = os.path.join(BASE, "session.key")  # HMAC secret for session cookies — 0600, auto-created
SESSION_TTL = 12 * 3600                               # session cookie lifetime (12h)
SESSION_COOKIE = "bawes_session"

WALLET = "/srv/bricks/register/wallet.jsonl"
ACHIEVEMENTS = "/srv/bricks/orchestrator/achievements.jsonl"
DISPATCHES = "/srv/bricks/orchestrator/dispatches.jsonl"
VECTOR = "/srv/bricks/orchestrator/vector-store.json"
QUEUE_FALLBACKS = ["/srv/bricks/orchestrator/shared-work-queue.md",
                   "/root/.hermes/notes/shared-work-queue.md"]
HEARTBEAT = "/srv/bricks/registry/heartbeat-registry.jsonl"
REGISTRY = "/srv/bricks/register/registry.jsonl"
DOOR_COST = "/srv/door/state/door-cost.jsonl"
SPEND = "/srv/fleet-state/register/spend.jsonl"
LEDGER_COST = "/srv/bricks/register/ledger-cost-rows.log"
PAT_FILE = "/srv/vault/github-hearth.pat"
DOOR_DB = "/home/ubuntu/.hermes/profiles/door/state.db"
GATEWAY_STATE = "/home/ubuntu/.hermes/gateway_state.json"
RATE_CARD = "/srv/bricks/orchestrator/rate-card.json"
APPROVALS = "/srv/bricks/orchestrator/approval-cards.jsonl"          # decision cards (append-only JSONL)
DECISIONS_LEDGER = "/srv/bricks/orchestrator/decisions-ledger.jsonl"  # local append-only decision rows
# VELOCITY + EVOLUTION panel sources (/panel/velocity + /api/velocity) — read-only,
# additive panel. Real ledgers only: burn receipts, verify queue, wallet mints,
# realtime scoreboard, live telemetry, brick ledger (75-thread capacity contract).
FLEET_REALTIME = "/srv/bricks/orchestrator/fleet-realtime.json"
TELEMETRY_LIVE = "/srv/bricks/orchestrator/telemetry-live.json"
RECEIPTS_OVH = "/srv/bricks/orchestrator/receipts-ovh.jsonl"
VERIFY_QUEUE = "/srv/bricks/orchestrator/verify-queue.jsonl"
BRICK_LEDGER = "/srv/bricks/orchestrator/brick-ledger.json"
VELOCITY_CACHE_SECS = 10.0
VELOCITY_LOCK = threading.Lock()
velocity_cache = {"ts": 0.0, "out": None}
GH_KNOWLEDGE = "https://api.github.com/repos/BAWES-Universe/bawes-knowledge"
LEDGER_MD = "decisions/ledger.md"   # canonical fleet decisions ledger (markdown table, GitHub)
REPO = "BAWES-Universe/hearth"
GH = "https://api.github.com/repos/" + REPO

APPROVAL_LOCK = threading.Lock()

# ---------------------------------------------------------------- roles + decision routing (v14, 2026-08-25)
# khalid: "Why is mishari read only? All should be able to login and I can give roles and
# permissions to ppl or issue them bricks no?" + "Mishari is cto of StudentHub and Plugn, so
# he needs to also make decisions and brick needs to request he make decisions."
# Role model: owner (everything incl. role-granting, money, final approvals authority) |
# decision_maker (approve/reject cards routed to their lanes: studenthub, plugn) |
# contributor (read-only) | brick_issuer (can issue bricks to people — grantable via /api/roles;
# the issuance flow itself lives on the fleet side, no dashboard endpoint for it).
# users.json rows gain optional `lanes` (decision_maker) + `discord_id` bind (OAuth login
# honors the users.json role — no more hardcoded read-only for mishari).
ROLE_REGISTRY = {
    "owner": "everything — role-granting, money, approvals, final authority",
    "decision_maker": "approve/reject cards routed to their lanes (studenthub, plugn)",
    "contributor": "read-only dashboard",
    "brick_issuer": "can issue bricks to people",
}
LANE_IDS = ("studenthub", "plugn", "fleet")
ROLES_AUDIT = os.path.join(BASE, "roles-audit.jsonl")   # append-only role-change audit (0600)
ROLE_LOCK = threading.Lock()

# ---------------------------------------------------------------- portfolio + invest leg (v10, 2026-08-25)
# khalid ratified 2026-08-25: "I shouldn't be the one brainstorming — you all know and we discussed
# many times... Time Machine and all". Invest leg: projects.jsonl ledger (named object per epic:
# goal, funded amount, funded-by positions, build status, earning status) + wallet rows
# kind=invest {person, project_id, bananas, ts, terms_sha}. WRITE lands ONLY through the approvals
# path — a card carrying an invest payload binds on khalid's sign; the API only ever READS invest
# state (portfolio + pending cards). Reversals = new wallet rows with negative bananas (DA rule:
# corrections as reversals, append-only). Project account = derived balance per F-19 pattern.
PROJECTS = "/srv/bricks/orchestrator/projects.jsonl"        # investable projects (append-only, latest per id wins)
FLEET_TOKENS_DIR = "/srv/vault/fleet-tokens"                 # BYOK key files — names only, values never read
VAULT_STORE = "/srv/vault/store.jsonl"                       # key registry rows {kind:key, service, person, key_sha, key(masked), ts, custody}
INGEST_TOKENS = "/srv/vault/ingest_tokens.json"              # per-person ingest tokens (names only)
INVEST_TERMS_V1 = ("BAWES invest terms v1 (2026-08-25): an invest row is a REAL debit from the "
                   "investor's derived balance (earns + credits + seeds - docks - prior invests, "
                   "F-19 pattern). Projects are epic-scoped accounts; funded = sum of invest rows "
                   "per project. Corrections are reversals (append-only negative rows). BYOK keys "
                   "stay vaulted at 0600 - never in git, never in chat. No dividends: funding "
                   "names an epic and returns are measured as build + earning status, not interest.")
INVEST_TERMS_SHA = hashlib.sha256(INVEST_TERMS_V1.encode()).hexdigest()[:16]
WALLET_LOCK = threading.Lock()
TIMEFLOW_LOCK = threading.Lock()
timeflow_cache = {"ts": 0, "out": None}

# ---------------------------------------------------------------- MONEY LIVE (v11, 2026-08-25)
# khalid 2026-08-25: "no visibility and no roi or showing my per second spend and roi".
# Beat 12 + /api/moneylive: per-minute spend rail (last 60 min, zero-filled), 24h free/paid
# split, ROI ticker (bananas × peg vs paid spend), burn $/hr + projected daily. Real rows
# only from measurements.jsonl (per-call spend ledger {ts, lane, model, cost_usd, billed}),
# router ledger as fallback. Peg per task spec: 1🍌 = $0.01 verified compute cost (the v1.1
# rate-card peg $0.012 still powers /api/data roi — both reported, never mixed).
MEASUREMENTS = "/srv/bricks/register/measurements.jsonl"  # per-call spend ledger (billed rows)
MONEY_PEG_USD = 0.01
moneylive_cache = {"ts": 0, "out": None}
MONEYLIVE_LOCK = threading.Lock()

# Agent relay (comms) — canonical append-only file, mirrored to the bawes-fleet
# repo drop-box every 60s by relay_sync.py (see README-RELAY.md).
# Row schema: {ts, from, to(all|brick|agi|oxalpha|oxbaby), kind(msg|task|ack|approval), body, receipt}
RELAY = "/srv/bricks/orchestrator/agent-relay.jsonl"
RELAY_LOCK = threading.Lock()
_relay_rate = {}            # in-memory rate limiter: username -> deque of post timestamps
RATE_OWNER_PER_MIN = 1      # khalid (owner): 1 msg/min
RATE_OTHER_PER_HOUR = 5     # everyone else: 5 msg/hr

# ---------------------------------------------------------------- discord oauth (human login, 2026-08-25)
# khalid: "The fleet app needs to allow me to login w discord and you as fleet can login and
# utilize the infra as well." Authorization-code flow, scope=identify ONLY, invite-only mapping.
DISCORD_OAUTH_ENV = "/srv/vault/discord-oauth.env"  # 0600, door.env pattern: CLIENT_ID=/CLIENT_SECRET=
DISCORD_APP_ID = "1538492803196125214"              # public app id ("Brick") — OAuth client_id fallback
DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/v10/oauth2/token"
DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_REDIRECT_URI = "https://fleet.bawes.net/oauth/discord/callback"
OAUTH_STATE_COOKIE = "bawes_oauth_state"            # one-time CSRF nonce cookie (10 min)
OAUTH_STATE_TTL = 600
# Invite-only mapping: Discord snowflake (STRING) -> fleet account. Everyone else gets NOT FOUND.
DISCORD_ID_MAP = {
    "189055515819638794": ("khalid", "owner"),      # khalid
    "231861753082937346": ("mishari", "contributor"),  # mishari
}
# ---------------------------------------------------------------- fleet agent machine identity (2026-08-25)
# Scoped bearer token: fleet agents (ox-alpha, OxBaby, claimer, ...) authenticate to /api/* and
# MCP :8004 like logged-in citizens instead of reading files directly. 0600, one token, audited.
AGENT_TOKEN_FILE = "/srv/vault/fleet-tokens/agent-api.token"      # the scoped bearer token (0600)
AGENT_USAGE_LOG = "/srv/vault/fleet-tokens/agent-api.usage.log"   # audit: every agent-token call (0600)
AGENT_SESSION_USER = "fleet-agent"                  # synthetic username for bearer-authed requests

BANANA_PEG_USD = 0.012  # v1.1 rate card peg
FRESH_SEC = 300         # heartbeat within 5 min = LIVE
SEEN7D_SEC = 7 * 86400  # seen within 7 days = IDLE
NOUS_SPEC = {"vcpu": 8, "ram_gb": 4, "concurrent_sessions": 20,
             "usd_per_day": 1.09,
             "source": "Nous Hermes Cloud plan (fleet notes 2026-08-24; nous-cloud-ops)"}

# ---------------------------------------------------------------- who / burn / cut-burn (v5, 2026-08-24)
# khalid 2026-08-24: "It's also stating who's live but doing what and capacity burn
# rate etc not showing. To see the spend and roi live and cut burns or pivot..."
# A) WHO'S DOING WHAT — per-agent live/idle + most recent REAL activity.
# B) BURN RATE        — spend velocity ($/hr, $/day) from the router ledger + free-vs-paid split.
# C) CUT BURN         — owner-only per-lane pause/resume toggles -> lane-control.jsonl + kanban comment.
LANES = "/srv/bricks/router/state/lanes.jsonl"           # router lanes (append-only; latest row per lane wins)
LANE_LEDGER = "/srv/bricks/router/state/ledger.jsonl"    # every routed call appends a real row (lane, model, cost)
LANE_CONTROL = "/srv/bricks/orchestrator/lane-control.jsonl"  # owner lane directives {ts, lane, action, by}
# spawn-ecosystem (spawn_ecosystem.py) — bottleneck events + spawn log (append-only)
BOTTLENECKS = "/srv/bricks/register/bottlenecks.jsonl"
SPAWNS = "/srv/bricks/register/spawns.jsonl"
TELEMETRY = "/srv/bricks/register/telemetry.jsonl"   # The Net — per-brick cpu/ram rows (append-only)
KANBAN_BOARD_DB = "/home/ubuntu/.hermes/kanban/boards/fleet/kanban.db"  # fleet board (sqlite, read-only)
KANBAN_BOARD = "fleet"
KANBAN_CTRL_TITLE = "lane-control — owner's kill switch (fleet dashboard)"
TOGGLE_LANES = ["free-ox", "free-gen", "free-liquid", "free-nemotron",
                "nvidia-nim", "deepseek-api", "nous-paid"]
FREE_LANE_IDS = {"free-ox", "free-gen", "free-liquid", "free-nemotron",
                 "glm-5.2-free", "nvidia-nim"}  # lanes whose router cost_per_task == 0
LANE_LOCK = threading.Lock()
ledger_cache = {"ts": 0, "out": None}
lanes_cache = {"ts": 0, "out": None}

gh_cache = {"ts": 0, "data": None, "error": None}
hb_cache = {"size": 0, "last": {}, "rows": 0, "ts": 0}


def now_iso():
    return datetime.datetime.now(datetime.UTC).isoformat()


def read_jsonl(path, limit=None):
    """Line-based JSONL reader with a whole-file fallback: some fleet ledgers
    (notably wallet.jsonl) are pretty-printed JSON ARRAYS, not line-JSONL, so a
    pure line parse sees ~0 rows. When the whole file parses as one JSON list
    with MORE rows than the line parse found, prefer that (dicts only — stray
    strings like a bare `"brick-eas-001"` row are ledger noise, not records)."""
    out = []
    raw = None
    try:
        with open(path) as f:
            raw = f.read()
    except FileNotFoundError:
        return None
    for i, line in enumerate(raw.split("\n"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
        if limit and len(out) >= limit:
            break
    if not limit:
        tail_rows = []
        doc = None
        try:
            doc = json.loads(raw)
        except Exception as ex:
            pos = getattr(ex, "pos", None)
            # ONLY pretty-printed arrays (prefix starts with "[") take the
            # prefix+tail path — for plain NDJSON the whole-file parse fails
            # on line 1 and the tail-reparse would DOUBLE every row
            # (registry 156 -> 311 etc.). NDJSON stays pure line-parse.
            if pos and raw[:pos].lstrip().startswith("["):
                try:
                    doc = json.loads(raw[:pos].rstrip())
                except Exception:
                    doc = None
                # pretty-printed array followed by appended compact rows
                # (e.g. `]{...}` glued after the closing bracket)
                for line in raw[pos:].split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        v = json.loads(line)
                        if isinstance(v, dict):
                            tail_rows.append(v)
                    except Exception:
                        pass
        if isinstance(doc, list) and len(doc) > len(out):
            out = list(doc)
        out.extend(tail_rows)
    return [r for r in out if isinstance(r, dict)]


def file_age_min(path):
    try:
        return (time.time() - os.path.getmtime(path)) / 60.0
    except OSError:
        return None


def strip_md(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    return s.strip()


# ---------------------------------------------------------------- auth (v3: users.json + HMAC session cookie)
def load_users():
    """users.json -> list of user dicts. Missing/corrupt file -> []."""
    try:
        with open(USERS_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def find_user(username):
    for u in load_users():
        if hmac.compare_digest(str(u.get("username", "")), str(username or "")):
            return u
    return None


# ---------------------------------------------------------------- roles + decision routing helpers (v14)
def user_lanes(user):
    """Valid lanes a user decides. Non-decision_makers carry none."""
    if not user or user.get("role") != "decision_maker":
        return []
    return [l for l in (user.get("lanes") or []) if l in LANE_IDS]


def card_lane(card):
    """Normalized lane of a card (studenthub|plugn|fleet), else ''."""
    lane = str((card or {}).get("lane") or "").strip().lower()
    return lane if lane in LANE_IDS else ""


def lane_decision_maker(lane):
    """Username of the decision_maker for a lane, else None (cards then route to the owner)."""
    for u in load_users():
        if u.get("role") == "decision_maker" and lane in user_lanes(u):
            return u.get("username")
    return None


def card_decider(card):
    """Who decides a card: lane cards route to the lane's decision_maker, everything else to
    the owner (khalid, final authority)."""
    lane = card_lane(card)
    if lane in ("studenthub", "plugn"):
        dm = lane_decision_maker(lane)
        if dm:
            return dm
    return "khalid"


def can_decide(user, card):
    """Owner decides everything (final authority); decision_maker decides cards in their lanes."""
    if not user:
        return False
    r = user.get("role")
    if r == "owner":
        return True
    if r == "decision_maker" and card_lane(card) in user_lanes(user):
        return True
    return False


def save_users(users):
    """Atomic users.json write (temp + os.replace), 0600 — same recipe as gen_user.py."""
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(users, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, USERS_FILE)


def roles_audit_append(row):
    """Append-only role-change audit (0600, flock). Never edited, never deleted."""
    try:
        with open(ROLES_AUDIT, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)
        os.chmod(ROLES_AUDIT, 0o600)
    except Exception as e:
        print(f"roles audit append error: {e}", flush=True)


def roles_data():
    """Roster + role registry + audit tail for the Roles & People panel. NEVER exposes hashes."""
    people = []
    for u in load_users():
        people.append({"username": u.get("username"), "role": u.get("role", "contributor"),
                       "lanes": user_lanes(u), "discord_id": u.get("discord_id"),
                       "created": u.get("created")})
    audit = [r for r in (read_jsonl(ROLES_AUDIT) or []) if isinstance(r, dict)][-12:]
    return {"roles": ROLE_REGISTRY, "lanes": list(LANE_IDS), "people": people,
            "audit": audit, "file": USERS_FILE, "audit_file": ROLES_AUDIT}


def apply_role_change(person, role, lanes, by_user, revoke=False):
    """Owner-only role mutation: grant/change a role (with lanes for decision_maker) or revoke
    a role back to contributor. Audits every change (roles-audit.jsonl) and tells the fleet via
    the agent relay. Refuses to demote the last owner. Returns (ok, payload)."""
    person = str(person or "").strip()
    role = str(role or "").strip().lower()
    with ROLE_LOCK:
        users = load_users()
        target = next((u for u in users if u.get("username") == person), None)
        if target is None:
            return False, {"error": f"no such user '{person}'"}
        if role not in ROLE_REGISTRY:
            return False, {"error": f"unknown role '{role}' — choose: {', '.join(ROLE_REGISTRY)}"}
        prev_role = target.get("role", "contributor")
        prev_lanes = user_lanes(target)
        if revoke:
            if role == "contributor":
                role = prev_role  # revoke with no role = revoke whatever they have
            if role == prev_role and prev_role == "contributor":
                return False, {"error": f"{person} is already contributor — nothing to revoke"}
            new_role = "contributor"
        else:
            new_role = role
        if prev_role == "owner" and new_role != "owner" and \
                sum(1 for u in users if u.get("role") == "owner") <= 1:
            return False, {"error": f"refusing to demote '{person}' — last owner. "
                                    "Promote someone else to owner first."}
        new_lanes = [l for l in (lanes or []) if l in LANE_IDS] if new_role == "decision_maker" else []
        target["role"] = new_role
        if new_lanes:
            target["lanes"] = new_lanes
        else:
            target.pop("lanes", None)
        target["roles_changed"] = now_iso()
        save_users(users)
        action = "revoke" if revoke else ("grant" if prev_role == "contributor" else "change")
        row = {"ts": now_iso(), "by": by_user, "action": action, "person": person,
               "role": new_role, "lanes": new_lanes, "prev_role": prev_role,
               "prev_lanes": prev_lanes, "source": "api /api/roles"}
        roles_audit_append(row)
        try:
            lane_txt = f" lanes: {', '.join(new_lanes)}" if new_lanes else ""
            relay_append({"ts": now_iso(), "from": by_user, "to": "all", "kind": "role",
                          "body": f"{by_user} set {person}'s role to {new_role}{lane_txt}",
                          "receipt": None})
        except Exception as e:
            print(f"role relay notify error: {e}", flush=True)
        return True, {"user": {"username": person, "role": new_role, "lanes": new_lanes},
                      "audit": row, "roles": roles_data()}


def hash_password(pw, salt):
    """scrypt (stdlib) — same recipe as gen_user.py. Salt is a hex string."""
    return hashlib.scrypt(pw.encode(), salt=salt.encode(), n=2 ** 14, r=8, p=1).hex()


def verify_user(username, pw):
    """(user_dict | None) — password check via constant-time compare."""
    u = find_user(username)
    if not u or not pw:
        return None
    try:
        want = str(u.get("hash", ""))
        got = hash_password(pw, str(u.get("salt", "")))
        return u if hmac.compare_digest(got, want) else None
    except Exception:
        return None


_session_secret = None


def session_secret():
    """HMAC secret for session cookies — session.key (0600), auto-created on first boot."""
    global _session_secret
    if _session_secret:
        return _session_secret
    try:
        if not os.path.exists(SESSION_KEY_FILE):
            with open(SESSION_KEY_FILE, "w") as f:
                f.write(secrets.token_hex(32) + "\n")
            os.chmod(SESSION_KEY_FILE, 0o600)
        with open(SESSION_KEY_FILE) as f:
            _session_secret = f.read().strip()
        return _session_secret
    except Exception as e:
        print(f"session.key error: {e}", flush=True)
        return "dev-insecure-fallback"


def make_session(user):
    """Signed cookie value: base64url(json{u,r,e}).hex_hmac. Tamper-evident."""
    payload = {"u": user.get("username"), "r": user.get("role"),
               "e": int(time.time()) + SESSION_TTL}
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(session_secret().encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_session(cookie):
    """(user_dict | None) — HMAC + expiry + user still exists (removed users lose access)."""
    if not cookie:
        return None
    try:
        b64, _, sig = cookie.partition(".")
        if not b64 or not sig:
            return None
        expect = hmac.new(session_secret().encode(), b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            return None
        pad = "=" * (-len(b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(b64 + pad).decode())
        if int(payload.get("e", 0)) < time.time():
            return None
        u = find_user(payload.get("u"))
        return u if u else None
    except Exception:
        return None


def session_cookie_header(user):
    return (f"{SESSION_COOKIE}={make_session(user)}; Path=/; HttpOnly; "
            f"SameSite=Lax; Max-Age={SESSION_TTL}")


def clear_cookie_header():
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


def parse_form(body):
    """application/x-www-form-urlencoded body -> dict."""
    try:
        return {k: v[0] for k, v in urllib.parse.parse_qs(body.decode(), keep_blank_values=True).items()}
    except Exception:
        return {}


def safe_next(raw):
    """Only allow same-site relative redirect targets (no //host, no ..)."""
    if raw and raw.startswith("/") and not raw.startswith("//") and ".." not in raw:
        return raw
    return "/"


# ---------------------------------------------------------------- discord oauth helpers (2026-08-25)
def discord_oauth_env():
    """client_id/client_secret from /srv/vault/discord-oauth.env (0600, door.env pattern).
    Returns (cfg_dict, None) or (None, error_message). The OAuth2 Client Secret is NOT the
    bot token — it lives in the Discord Developer Portal (Applications -> Brick -> OAuth2)."""
    cfg = {"client_id": DISCORD_APP_ID, "redirect_uri": DISCORD_REDIRECT_URI}
    try:
        with open(DISCORD_OAUTH_ENV) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    key = k.strip().upper()
                    if key.startswith("DISCORD_"):
                        key = key[len("DISCORD_"):]
                    cfg[key] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        return None, (f"Discord login is not configured yet — {DISCORD_OAUTH_ENV} is missing. "
                      "The fleet owner must paste the app's OAuth2 Client Secret there "
                      "(Discord Developer Portal → Applications → Brick → OAuth2 → Client Secret).")
    except Exception as e:
        return None, f"Discord login config unreadable: {e}"
    if not cfg.get("CLIENT_SECRET"):
        return None, (f"Discord login is not configured yet — DISCORD_CLIENT_SECRET is empty in "
                      f"{DISCORD_OAUTH_ENV}. The fleet owner must paste the app's OAuth2 Client Secret "
                      "(Discord Developer Portal → Applications → Brick → OAuth2 → Client Secret).")
    if cfg.get("CLIENT_ID"):
        cfg["client_id"] = cfg["CLIENT_ID"]
    cfg["client_secret"] = cfg["CLIENT_SECRET"]
    return cfg, None


def oauth_state_make(nxt="/"):
    """HMAC-signed OAuth state: base64url(json{n,e,nxt}).hex_hmac (signed with session.key)."""
    payload = {"n": secrets.token_urlsafe(16), "e": int(time.time()) + OAUTH_STATE_TTL,
               "nxt": safe_next(nxt)}
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(session_secret().encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def oauth_state_verify(state, cookie_nonce):
    """(dict | None) — signature ok, not expired, nonce matches this browser's cookie."""
    if not state or "." not in state:
        return None
    b64, _, sig = state.partition(".")
    expect = hmac.new(session_secret().encode(), b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expect):
        return None
    try:
        pad = "=" * (-len(b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(b64 + pad).decode())
    except Exception:
        return None
    if int(data.get("e", 0)) < time.time():
        return None
    if not hmac.compare_digest(str(data.get("n", "")), str(cookie_nonce or "")):
        return None
    return data


def discord_http(url, data=None, headers=None, timeout=15):
    """JSON GET/POST against Discord (form bodies for token, Bearer for /users/@me).
    Uses `requests` when available: Discord's Cloudflare edge 403s python-urllib's
    TLS fingerprint from datacenter IPs (error 1010) but accepts requests/curl —
    verified 2026-08-25 from the OVH box (clean 401 invalid_client on fake secret)."""
    try:
        if _HAS_REQUESTS:
            kw = {"timeout": timeout, "headers": headers or {}}
            if data is not None:
                kw["data"] = data
            r = requests.request("POST" if data is not None else "GET", url, **kw)
            if r.status_code >= 400:
                raise RuntimeError(f"discord http {r.status_code}: {r.text[:200]}")
            return r.json() if r.content else {}
        # stdlib fallback (works where no Cloudflare edge is in the way)
        req = urllib.request.Request(url, data=data, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode() or "{}")
    except RuntimeError:
        raise
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"discord http {e.code}: {e.read()[:200]}")
    except Exception as e:
        raise RuntimeError(f"discord http failed: {e}")


def discord_exchange_code(code, cfg):
    """POST /oauth2/token (authorization_code) -> access_token. Raises on failure."""
    form = urllib.parse.urlencode({
        "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": cfg["redirect_uri"]}).encode()
    tok = discord_http(DISCORD_TOKEN_URL, data=form,
                       headers={"Content-Type": "application/x-www-form-urlencoded"})
    if not tok.get("access_token"):
        raise RuntimeError("token exchange returned no access_token")
    return tok


def discord_me(token):
    """GET /users/@me with Bearer -> Discord user object (id is a snowflake STRING)."""
    me = discord_http(f"{DISCORD_API_BASE}/users/@me",
                      headers={"Authorization": f"Bearer {token}"})
    if not me.get("id"):
        raise RuntimeError("/users/@me returned no id")
    return me


def discord_map_user(discord_id):
    """Invite-only: Discord snowflake -> fleet user row. users.json discord_id bind first,
    then the hardcoded khalid/mishari map. Unknown -> None (NOT FOUND page)."""
    did = str(discord_id or "")
    if not did:
        return None
    for u in load_users():
        if hmac.compare_digest(str(u.get("discord_id", "")), did):
            return u
    hit = DISCORD_ID_MAP.get(did)
    return find_user(hit[0]) if hit else None


def oauth_page(title, message, status=500):
    """Small honest BAWES-branded HTML page for OAuth states (config error, invite-only...).
    Both title and message are HTML-escaped — never pass raw user input here."""
    body = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)} · BAWES Fleet</title></head>"
            f"<body style='margin:0;background:#0a0c10;color:#e8edf4;font-family:system-ui;"
            f"display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px'>"
            f"<div style='max-width:34rem;text-align:center;background:#141922;border:1px solid #232c3a;"
            f"border-radius:18px;padding:36px 28px'>"
            f"<div style='font-weight:800;color:#f5b942;font-size:12px;letter-spacing:2.5px'>BAWES FLEET</div>"
            f"<h1 style='font-size:20px;margin:14px 0 10px'>{html.escape(title)}</h1>"
            f"<p style='color:#8b98a9;font-size:14.5px;line-height:1.65'>{html.escape(message)}</p>"
            f"<p><a href='/login' style='color:#3dd6a4;font-size:14px;text-decoration:none'>&larr; back to sign in</a></p>"
            f"</div></body></html>").encode()
    return body


# ---------------------------------------------------------------- fleet agent token helpers (2026-08-25)
_agent_token_cache = {"tok": None, "mtime": 0.0}


def agent_token():
    """Scoped fleet-agent bearer token (0600). Cached by mtime so rotation applies live."""
    try:
        m = os.path.getmtime(AGENT_TOKEN_FILE)
        if _agent_token_cache["tok"] is not None and _agent_token_cache["mtime"] == m:
            return _agent_token_cache["tok"]
        with open(AGENT_TOKEN_FILE) as f:
            tok = f.read().strip()
        _agent_token_cache["tok"] = tok
        _agent_token_cache["mtime"] = m
        return tok
    except Exception:
        return ""


def agent_usage_log(path, agent):
    """Audit trail: one line per agent-token API call (0600, append)."""
    try:
        with open(AGENT_USAGE_LOG, "a") as f:
            f.write(json.dumps({"ts": now_iso(), "path": path,
                                "agent": agent or AGENT_SESSION_USER}) + "\n")
        os.chmod(AGENT_USAGE_LOG, 0o600)
    except Exception:
        pass


# ---------------------------------------------------------------- money
def spend_data():
    """spend.jsonl — daily provider balances (real snapshots, control-host cron)."""
    rows = read_jsonl(SPEND)
    if not rows:
        return {"status": "missing", "note": "spend.jsonl not found — balances not available"}
    series = []
    latest = {}
    for r in rows:
        b = r.get("balances", {}) or {}
        row = {"ts": r.get("ts"), "deepseek": b.get("deepseek"), "openrouter": b.get("openrouter")}
        series.append(row)
        if isinstance(b.get("deepseek"), (int, float, str)) and not str(b.get("deepseek")).startswith("err"):
            latest["deepseek"] = float(b["deepseek"])
        if isinstance(b.get("openrouter"), (int, float)) or (
                isinstance(b.get("openrouter"), str) and not b["openrouter"].startswith("err")):
            latest["openrouter"] = float(b["openrouter"])
    deep_vals = [float(s["deepseek"]) for s in series
                 if isinstance(s["deepseek"], (int, float, str)) and not str(s["deepseek"]).startswith("err")]
    open_vals = [float(s["openrouter"]) for s in series
                 if isinstance(s["openrouter"], (int, float, str)) and not str(s["openrouter"]).startswith("err")]
    max_deep = max(deep_vals) if deep_vals else 0.0
    committed = {"deepseek": max_deep, "openrouter": max(open_vals) if open_vals else 0.0,
                 "total": round(max_deep + (max(open_vals) if open_vals else 0.0), 2)}
    remaining = {"deepseek": latest.get("deepseek"), "openrouter": latest.get("openrouter")}
    if remaining["deepseek"] is not None and remaining["openrouter"] is not None:
        remaining["total"] = round(remaining["deepseek"] + remaining["openrouter"], 2)
    else:
        remaining["total"] = None
    return {"status": "ok", "series": series, "committed_lower_bound": committed,
            "remaining": remaining, "latest_ts": series[-1]["ts"] if series else None,
            "note": "balances snapshotted daily 09:00Z by control-host cron; box copy synced 2026-08-24. "
                    "Committed = max recorded balance per provider (lower bound — top-ups only counted when they raise the peak)."}


def door_cost_data():
    rows = read_jsonl(DOOR_COST)
    if rows is None:
        return {"status": "missing"}
    total = 0.0
    per_day = {}
    for r in rows:
        try:
            c = float(r.get("cost", 0))
        except (TypeError, ValueError):
            c = 0.0
        total += c
        d = r.get("day", "?")
        per_day[d] = per_day.get(d, 0.0) + c
    return {"status": "ok", "rows": len(rows), "total_usd": round(total, 4),
            "per_day": [{"day": d, "usd": round(v, 4)} for d, v in sorted(per_day.items())],
            "unit": "deepseek-flash $0.002/call (door lane)"}


def money_data(wallet):
    spend = spend_data()
    door = door_cost_data()
    metered = door.get("total_usd", 0.0) if door.get("status") == "ok" else None
    rem = spend.get("remaining", {}) if spend.get("status") == "ok" else {}
    comm = spend.get("committed_lower_bound", {}) if spend.get("status") == "ok" else {}
    # rails — what is configured, what is metered (real evidence only)
    rails = [
        {"name": "ox/stealth (OpenRouter free tier)", "usd_per_task": 0.0,
         "evidence": "OPENROUTER_API_KEY in /srv/vault/openrouter.env (mode 600). Free-tier burn NOT metered per-model on box — no free-tier rows recorded."},
        {"name": "deepseek-flash", "usd_per_task": 0.002,
         "evidence": "(filled below from live reads)"},
        {"name": "GLM-5.2", "usd_per_task": 0.03,
         "evidence": "no GLM key/env found on box — $0 recorded, lane not configured here"},
        {"name": "Nous hermes-4 (paid)", "usd_per_task": None,
         "evidence": "key /srv/vault/nous.env (mode 600, control host, NOT on this box). $0 metered here; usage not yet instrumented. Policy: $10/day cap, paid lane only when free tier fails."},
    ]
    metered_txt = f"${metered:.2f}" if metered is not None else "no door-cost rows on this box yet"
    ds_bal = rem.get("deepseek")
    ds_bal_txt = f"${ds_bal:.2f}" if isinstance(ds_bal, (int, float)) else str(ds_bal or "?")
    for r in rails:
        if r["name"] == "deepseek-flash":
            r["evidence"] = (f"metered on box: {metered_txt} across {door.get('rows', 0)} door calls; "
                             f"balance {ds_bal_txt} (spend.jsonl {spend.get('latest_ts', '?')})")
    return {"spend": spend, "door_cost": door, "rails": rails,
            "metered_usd": metered,
            "total_invested": {"label": "provider credit committed (lower bound)",
                               "usd": comm.get("total") if comm else None,
                               "breakdown": comm},
            "remaining": rem,
            "note": "OVH VPS cost not derivable from box files (no invoice present) — flag khalid to supply. "
                    "credits are gifts, not earnings — ROI computed on earned bananas only."}


# ---------------------------------------------------------------- bricks (heartbeat registry)
def heartbeat_data():
    """Incremental tail read of heartbeat-registry.jsonl (append-only)."""
    now = time.time()
    try:
        size = os.path.getsize(HEARTBEAT)
    except OSError:
        return {"status": "missing"}
    if hb_cache["ts"] and now - hb_cache["ts"] < 60 and size >= hb_cache["size"]:
        return hb_cache["out"]
    last = dict(hb_cache["last"]) if hb_cache["ts"] else {}
    rows_seen = hb_cache["rows"]
    start = hb_cache["size"] if (hb_cache["ts"] and size >= hb_cache["size"]) else 0
    new_rows = 0
    try:
        with open(HEARTBEAT) as f:
            if start:
                f.seek(start)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                new_rows += 1
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                bid = d.get("brick_id")
                ts = d.get("ts")
                if bid and isinstance(ts, (int, float)):
                    last[str(bid)] = float(ts)
    except OSError:
        return {"status": "error"}
    hb_cache.update(size=size, last=last, rows=rows_seen + new_rows, ts=now)
    out = {"status": "ok", "total_rows": rows_seen + new_rows}
    live, idle, silent = [], [], []
    for bid, ts in sorted(last.items(), key=lambda kv: -kv[1]):
        age = now - ts
        rec = {"id": bid, "last_ts": ts, "age_sec": int(age),
               "last_seen": datetime.datetime.fromtimestamp(ts, datetime.UTC).strftime("%Y-%m-%d %H:%MZ")}
        if age <= FRESH_SEC:
            rec["state"] = "LIVE"
            live.append(rec)
        elif age <= SEEN7D_SEC:
            rec["state"] = "IDLE"
            idle.append(rec)
        else:
            rec["state"] = "SILENT"
            silent.append(rec)
    out.update(live=live, idle=idle, silent=silent,
               live_count=len(live), idle_count=len(idle), silent_count=len(silent),
               known_count=len(last),
               live_window_sec=FRESH_SEC,
               note="LIVE = heartbeat ≤ 5 min ago. IDLE = seen ≤ 7 days. SILENT = > 7 days.")
    hb_cache["out"] = out
    return out


def registry_data():
    rows = read_jsonl(REGISTRY)
    if not rows:
        return {"status": "missing"}
    ids = {}
    for r in rows:
        bid = r.get("brick_id") or r.get("id")
        if bid:
            ids[str(bid)] = r.get("quality") or r.get("state") or "registered"
    verified = [k for k, v in ids.items() if v == "verified"]
    return {"status": "ok", "registered_count": len(ids),
            "verified_count": len(verified), "verified": verified,
            "note": "register registry.jsonl: registered ≠ working. Live count comes from heartbeat, not this file."}


# ---------------------------------------------------------------- wallet / roi
def wallet_data():
    rows = read_jsonl(WALLET)
    if rows is None:
        return {"error": "wallet.jsonl missing", "total_rows": 0}
    by_kind = {}
    earned = credited = founder = spend = 0.0
    earned_rows = 0
    contested_earn = 0.0
    contested_earn_rows = 0
    last_ts = None
    for r in rows:
        k = r.get("kind") or r.get("type") or "unlabeled"
        b = r.get("bananas", 0) or 0
        try:
            b = float(b)
        except (TypeError, ValueError):
            b = 0.0
        e = by_kind.setdefault(k, {"count": 0, "bananas": 0.0})
        e["count"] += 1
        e["bananas"] += b
        if k == "earn":
            earned += b
            earned_rows += 1
            if r.get("contested"):
                contested_earn += b
                contested_earn_rows += 1
        elif k == "credit":
            credited += b
        elif k == "founder-seed":
            founder += b
        elif k == "dock":
            spend += b
        t = r.get("ts")
        if t:
            last_ts = t
    return {
        "total_rows": len(rows),
        "by_kind": by_kind,
        "earned_bananas": round(earned, 1),
        "earn_rows": earned_rows,
        "contested_earn_bananas": round(contested_earn, 1),
        "contested_earn_rows": contested_earn_rows,
        "clean_earned_bananas": round(earned - contested_earn, 1),
        "credited_bananas": round(credited, 1),
        "founder_seed_bananas": round(founder, 1),
        "spend_bananas": round(spend, 1),
        "last_ts": last_ts,
        "note": "contested earns = legacy self-mints (pre round-137, no non-earner signer) — kept for history, not evidence",
    }


def roi_data(w, money):
    metered = money.get("metered_usd")
    earned = w.get("clean_earned_bananas", 0.0)
    usd_value = round(earned * BANANA_PEG_USD, 4)
    out = {"peg_usd_per_banana": BANANA_PEG_USD}
    if metered is not None and metered > 0:
        out["roi_vs_metered_spend"] = round(usd_value / metered, 2)
        out["label"] = f"{earned}🍌 clean-earned × ${BANANA_PEG_USD} peg = ${usd_value} vs metered ${metered} spend"
    else:
        out["roi_vs_metered_spend"] = None
        out["label"] = "no metered spend yet — ROI n/a"
    out["note"] = "credits are gifts, not earnings — ROI on clean-earned bananas only"
    return out


# ---------------------------------------------------------------- evolution (time-series)
def _iso_to_ts(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def vector_series():
    try:
        d = json.load(open(VECTOR))
    except Exception:
        return {"error": "vector-store.json unreadable"}
    docs = d.get("docs", [])
    days = {}
    for doc in docs:
        ts = _iso_to_ts(doc.get("ts"))
        if not ts:
            continue
        day = datetime.datetime.fromtimestamp(ts, datetime.UTC).strftime("%Y-%m-%d")
        days[day] = days.get(day, 0) + 1
    cum = 0
    series = []
    for day in sorted(days):
        cum += days[day]
        series.append({"day": day, "added": days[day], "total": cum})
    return {"series": series, "docs": len(docs), "stats": d.get("stats", {}),
            "first_day": series[0]["day"] if series else None,
            "note": "history accrues from 2026-08-15 (store creation) — curve is real, built from per-doc ts fields"}


def wallet_series(w):
    rows = read_jsonl(WALLET) or []
    earns = []
    for r in rows:
        if (r.get("kind") or r.get("type")) != "earn":
            continue
        ts = _iso_to_ts(r.get("ts"))
        if not ts:
            continue
        try:
            b = float(r.get("bananas", 0) or 0)
        except (TypeError, ValueError):
            b = 0.0
        earns.append((ts, b, bool(r.get("contested"))))
    earns.sort()
    cum = 0.0
    cum_clean = 0.0
    series = []
    for ts, b, contested in earns:
        cum += b
        if not contested:
            cum_clean += b
        day = datetime.datetime.fromtimestamp(ts, datetime.UTC).strftime("%Y-%m-%d")
        series.append({"day": day, "cum": round(cum, 1), "cum_clean": round(cum_clean, 1)})
    return {"series": series, "total": w.get("earned_bananas"), "clean": w.get("clean_earned_bananas")}


def pr_series(gh):
    dates = gh.get("merged_dates") or []
    cum = 0
    series = []
    by_day = {}
    for d in dates:
        by_day[d] = by_day.get(d, 0) + 1
    for day in sorted(by_day):
        cum += by_day[day]
        series.append({"day": day, "merged": by_day[day], "cum": cum})
    return {"series": series, "merged_count": gh.get("merged_count"),
            "prs_per_day": gh.get("prs_per_day")}


def spend_series(money):
    spend = money.get("spend", {})
    series = spend.get("series") or []
    out = []
    for s in series:
        try:
            d = float(s["deepseek"]) if not str(s["deepseek"]).startswith("err") else None
        except Exception:
            d = None
        try:
            o = float(s["openrouter"]) if not str(s["openrouter"]).startswith("err") else None
        except Exception:
            o = None
        out.append({"ts": s["ts"], "deepseek": d, "openrouter": o})
    return {"series": out, "note": "daily balance snapshots — drops = burn, jumps = top-up"}


# ---------------------------------------------------------------- threads (utilization)
def door_sessions():
    import sqlite3
    try:
        con = sqlite3.connect("file:" + DOOR_DB + "?mode=ro", uri=True, timeout=5)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM sessions")
        total = cur.fetchone()[0]
        now = time.time()
        def since(secs):
            cut = now - secs
            cur.execute("SELECT COUNT(*) FROM sessions WHERE last_activity_at >= ?", (cut,))
            return cur.fetchone()[0]
        a24 = since(86400)
        a7d = since(7 * 86400)
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT model), COALESCE(SUM(api_call_count),0), "
                    "COALESCE(SUM(estimated_cost_usd),0) FROM session_model_usage")
        u = cur.fetchone()
        cur.execute("SELECT model, COUNT(*), COALESCE(SUM(api_call_count),0) FROM session_model_usage "
                    "GROUP BY model ORDER BY 2 DESC LIMIT 6")
        models = [{"model": r[0], "rows": r[1], "calls": r[2]} for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL")
        open_sessions = cur.fetchone()[0]
        con.close()
        return {"status": "ok", "db": DOOR_DB, "sessions_total": total,
                "active_24h": a24, "active_7d": a7d, "open_sessions": open_sessions,
                "usage_rows": u[0], "distinct_models": u[1], "api_calls": u[2],
                "estimated_cost_usd": round(u[3] or 0, 4), "models": models}
    except Exception as e:
        return {"status": "error", "note": str(e)}


def gateway_snapshot():
    try:
        with open(GATEWAY_STATE) as f:
            g = json.load(f)
        return {"status": "ok", "gateway_state": g.get("gateway_state"),
                "active_agents": g.get("active_agents"),
                "platforms": list((g.get("platforms") or {}).keys()),
                "updated_at": g.get("updated_at"),
                "stale": (time.time() - os.path.getmtime(GATEWAY_STATE)) > 86400}
    except Exception as e:
        return {"status": "error", "note": str(e)}


def fleet_processes():
    n = 0
    names = []
    known = ("bridge", "heartbeat", "orchestrator", "headless_worker", "token_router",
             "door_gateway", "door_ingest", "a2a_server", "dashboard", "allowance",
             "earn", "brain", "evolution", "spread", "vault", "bandit")
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    raw = f.read().replace(b"\x00", b" ").decode(errors="ignore")
            except Exception:
                continue
            if "python3" not in raw:
                continue
            n += 1
            for m in re.findall(r"([A-Za-z0-9_\-]+\.py)", raw):
                base = m.lower()
                if any(k in base for k in known) and m not in names:
                    names.append(m)
    except Exception:
        pass
    names.sort()
    return {"count": n, "processes": names}


def threads_data():
    spec = dict(NOUS_SPEC)
    sess = door_sessions()
    gw = gateway_snapshot()
    procs = fleet_processes()
    measured = {
        "door_sessions": sess if sess.get("status") == "ok" else None,
        "gateway": gw if gw.get("status") == "ok" else None,
        "fleet_processes": procs,
    }
    return {
        "spec": spec,
        "measured": measured,
        "gaps": [
            "true concurrent-session count on the Hermes Cloud instance is NOT yet instrumented "
            "(cloud MCP needs an OAuth browser round-trip the headless box can't complete) — showing on-box proxies instead",
            "door-profile model metering shows every call on deepseek-v4-flash at $0.00 estimated — free/cheap lane only, "
            "no paid-lane burn recorded on box",
        ],
        "verdict": "Spec allows 20 concurrent sessions @ $1.09/day. On-box proxies: 0 sessions active in last 24h "
                   "(door profile DB), gateway active_agents 0, {n} fleet python processes running. "
                   "Concurrency is far under capacity — a cheaper brick is likely viable once true utilization is instrumented.".format(n=procs["count"]),
    }


# ---------------------------------------------------------------- github
def gh_get(url, pat, timeout=15):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + pat,
        "Accept": "application/vnd.github+json",
        "User-Agent": "fleet-dashboard-v2",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def github_data(force=False):
    now = time.time()
    if not force and gh_cache["data"] and now - gh_cache["ts"] < 60:
        return gh_cache["data"]
    try:
        pat = open(PAT_FILE).read().strip()
        open_prs = gh_get(f"{GH}/pulls?state=open", pat)
        closed = gh_get(f"{GH}/pulls?state=closed&per_page=100", pat)
        merged = [p for p in closed if p.get("merged_at")]
        ci = {}
        for p in open_prs:
            sha = (p.get("head") or {}).get("sha", "")
            try:
                st = gh_get(f"{GH}/commits/{sha}/status", pat)
                ci[p["number"]] = {"state": st.get("state", "n/a"), "n_statuses": len(st.get("statuses", []))}
            except Exception:
                ci[p["number"]] = {"state": "unknown", "n_statuses": 0}
        merged_dates = sorted(p["merged_at"][:10] for p in merged)
        prs_per_day = None
        if len(merged_dates) >= 2:
            d0 = datetime.date.fromisoformat(merged_dates[0])
            d1 = datetime.date.fromisoformat(merged_dates[-1])
            days = max((d1 - d0).days + 1, 1)
            prs_per_day = round(len(merged_dates) / days, 2)
        data = {
            "open": [{"number": p["number"], "title": p["title"], "created": p["created_at"][:10],
                      "head": (p.get("head") or {}).get("ref"), "ci": ci.get(p["number"])} for p in open_prs],
            "merged_count": len(merged),
            "merged_dates": merged_dates,
            "merged_titles": [p.get("title") or "" for p in merged],
            "prs_per_day": prs_per_day,
            "ci_summary": f"success on {sum(1 for v in ci.values() if v['state'] == 'success')}/{len(ci)} open PRs",
            "fetched_at": now_iso(),
        }
        gh_cache.update(ts=now, data=data, error=None)
        return data
    except Exception as e:
        gh_cache["error"] = str(e)
        if gh_cache["data"]:
            gh_cache["data"]["stale"] = True
            gh_cache["data"]["error"] = str(e)
            return gh_cache["data"]
        return {"open": [], "merged_count": None, "prs_per_day": None,
                "ci_summary": f"GitHub unreachable: {e}", "merged_dates": [], "error": str(e)}


# ---------------------------------------------------------------- epics (queue)
def epics_data():
    md = None
    used = None
    for cand in QUEUE_FALLBACKS:
        try:
            md = open(cand).read()
            used = cand
            break
        except Exception:
            continue
    if md is None:
        return {"error": "queue not readable", "epics": []}
    epics = []
    in_table = False
    for line in md.splitlines():
        if line.startswith("## Active ownership"):
            in_table = True
            continue
        if line.startswith("## "):
            in_table = False
        if in_table and line.startswith("|") and "Task" not in line and "---" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 3 and cells[0]:
                epics.append({"task": strip_md(cells[0]), "owner": strip_md(cells[1]), "status": strip_md(cells[2])})
    in_next = False
    for line in md.splitlines():
        if line.startswith("## Next-steps"):
            in_next = True
            continue
        if in_next and line.startswith("## "):
            in_next = False
        if in_next and re.match(r"^\s*\d+\.\s", line):
            txt = re.sub(r"^\s*\d+\.\s*", "", line).strip()
            if txt:
                epics.append({"task": strip_md(txt), "owner": "claimable", "status": "OPEN — claimable"})
    return {"epics": epics, "source": used}


# ---------------------------------------------------------------- vector store
def vector_data():
    try:
        d = json.load(open(VECTOR))
    except Exception as e:
        return {"error": str(e)}
    docs = d.get("docs", [])
    stats = d.get("stats", {})
    topics = {}
    for doc in docs:
        t = doc.get("topic", "?")
        topics[t] = topics.get(t, 0) + 1
    raw_in = stats.get("raw_in", 0)
    novel = stats.get("novel", 0)
    return {
        "docs": len(docs),
        "topics": len(topics),
        "topic_counts": sorted(topics.items(), key=lambda x: -x[1])[:10],
        "stats": stats,
        "novel_rate": round(novel / raw_in, 3) if raw_in else None,
        "note": "seed/leech per brick: retrievals not yet tracked — novel adds only (raw_in → novel dedup)",
    }


# ---------------------------------------------------------------- fleet status
def fleet_status():
    brick = {"status": "LIVE", "detail": "session live on box (Hermes), dashboard server running", "signal_min": 0}
    ages = [a for a in (file_age_min(VECTOR), file_age_min("/srv/bricks/orchestrator/audit.jsonl")) if a is not None]
    agi_age = min(ages) if ages else None
    agi = {"status": ("LIVE" if agi_age is not None and agi_age <= 360 else "IDLE"),
           "detail": "last store write", "signal_min": round(agi_age, 1) if agi_age is not None else None}
    hb = heartbeat_data()
    ox = {"status": "IDLE", "detail": "hermes-local (ox-alpha) last heartbeat "
          + (hb.get("idle", [{}])[0]["last_seen"] if hb.get("idle") else "n/a") + " — remote-mcp:8932"}
    return {"Brick": brick, "AGI": agi, "ox-alpha (Hermes Cloud)": ox}


# ---------------------------------------------------------------- approvals (decision cards)
# Append-only JSONL: every action appends a NEW row for the card id (latest row wins),
# so the file is a full audit trail and never silently edited. Fields:
#   id|title|proposer|summary|impact|cost|created_ts|status|feedback|khalid-*-ts|updated_ts
# status: PENDING | APPROVED | REJECTED | NEEDS-FEEDBACK
def approvals_data():
    rows = read_jsonl(APPROVALS)
    if rows is None:
        return {"status": "missing", "cards": [], "pending_count": 0, "file": APPROVALS}
    by_id = {}
    for r in rows:
        if isinstance(r, dict) and r.get("id"):
            by_id[str(r["id"])] = r  # latest row for an id wins (append-only history)
    cards = sorted(by_id.values(), key=lambda c: (c.get("status") != "PENDING",
                                                  c.get("created_ts") or ""))
    for c in cards:
        c["lane"] = card_lane(c)          # normalized (studenthub|plugn|fleet|"")
        c["decider"] = card_decider(c)    # who this card routes to (lane DM or khalid)
    pending = [c for c in cards if c.get("status") == "PENDING"]
    return {"status": "ok", "cards": cards, "pending_count": len(pending), "file": APPROVALS,
            "statuses": ["PENDING", "APPROVED", "REJECTED", "NEEDS-FEEDBACK"],
            "lanes": {"studenthub": {"decision_maker": lane_decision_maker("studenthub")},
                      "plugn": {"decision_maker": lane_decision_maker("plugn")},
                      "fleet": {"decision_maker": "khalid"}},
            "note": "append-only JSONL — every decision appends a new row; latest row per card wins. "
                    "Cards with lane=studenthub|plugn route to that lane's decision_maker; "
                    "everything else binds on the owner's sign. The owner keeps final authority "
                    "(overrides are recorded)."}


def achievements_data():
    """Accomplishments ledger: count + latest rows with their real text (cv_line/action).
    Additive — the accomplishments panel renders these; count alone was useless."""
    rows = [r for r in (read_jsonl(ACHIEVEMENTS) or []) if isinstance(r, dict)]
    latest = []
    for r in rows[-8:]:
        latest.append({
            "iso": r.get("iso") or (str(r.get("ts"))[:16] if r.get("ts") else None),
            "action": r.get("action"),
            "line": r.get("cv_line") or r.get("action"),
            "owner": r.get("owner"),
            "contested": bool(r.get("contested")),
            "verification": r.get("verification"),
        })
    return {"count": len(rows), "file": ACHIEVEMENTS, "rows": latest,
            "note": "achievements.jsonl — verified cycle completions (contested = legacy self-mints, kept for history)"}


def gh_append_decision(row):
    """Append a row to the canonical decisions ledger (BAWES-Universe/bawes-knowledge decisions/ledger.md).
    Best-effort: failures are reported, never fatal to the action."""
    pat = open(PAT_FILE).read().strip()
    url = f"{GH_KNOWLEDGE}/contents/{LEDGER_MD}"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + pat,
                                               "Accept": "application/vnd.github+json",
                                               "User-Agent": "fleet-dashboard-approvals"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        cur = json.loads(resp.read().decode())
    sha = cur["sha"]
    content = base64.b64decode(cur["content"]).decode()
    if not content.endswith("\n"):
        content += "\n"
    date = str(row.get("ts", ""))[:10]
    title = re.sub(r"\|", "/", str(row.get("title", row.get("card_id", "?"))))
    decision = re.sub(r"\|", "/", str(row.get("decision_text", "")))
    proposer = re.sub(r"\|", "/", str(row.get("proposer", "?")))
    action = row.get("action")
    by = row.get("by", "khalid")
    actor_col = {"approve": "✅ approved", "reject": "❌ rejected",
                 "feedback": "💬 feedback given"}.get(action, action)
    status_col = {"approve": "APPROVED via /approvals", "reject": "REJECTED via /approvals",
                  "feedback": "NEEDS-FEEDBACK via /approvals"}.get(action, row.get("status", "?"))
    md_row = (f"| {date} | APPROVAL CARD {row.get('card_id','?')} — {title} — {decision} | "
              f"{proposer} | {by} ({row.get('role','?')}) | {actor_col} | {status_col} |\n")
    new_content = content + md_row
    body = json.dumps({"message": f"fleet-dashboard: {by} {action} on approval card {row.get('card_id','?')}",
                       "content": base64.b64encode(new_content.encode()).decode(),
                       "sha": sha}).encode()
    put = urllib.request.Request(url, data=body, method="PUT",
                                 headers={"Authorization": "Bearer " + pat,
                                          "Content-Type": "application/json",
                                          "Accept": "application/vnd.github+json",
                                          "User-Agent": "fleet-dashboard-approvals"})
    with urllib.request.urlopen(put, timeout=20) as resp:
        return json.loads(resp.read().decode())


def approval_action(card_id, action, feedback=None, actor=None):
    """Apply a decision to a card. The card's DECIDER decides it: cards with lane=studenthub|plugn
    route to that lane's decision_maker (Mishari); everything else binds on the owner (khalid).
    The owner keeps FINAL authority and can override a lane decision (the original decision is
    preserved in `overrides`). Every action appends a NEW row (append-only, latest wins), a
    decisions-ledger row, and a best-effort canonical GitHub ledger row. Returns (ok, payload)."""
    uname = (actor or {}).get("username", "?")
    role = (actor or {}).get("role", "?")
    with APPROVAL_LOCK:
        rows = read_jsonl(APPROVALS) or []
        if not rows:
            return False, {"error": "approval-cards.jsonl missing — no cards"}
        card = None
        for r in reversed(rows):
            if isinstance(r, dict) and r.get("id") == card_id:
                card = r
                break
        if card is None:
            return False, {"error": "card not found"}
        if action not in ("approve", "reject", "feedback"):
            return False, {"error": f"unknown action '{action}'"}
        if not can_decide(actor, card):
            return False, {"error": f"this card routes to {card_decider(card)} — you don't decide it",
                           "forbidden": True}
        terminal = card.get("status") in ("APPROVED", "REJECTED")
        owner_override = (role == "owner" and terminal
                          and card.get("decided_by") and card.get("decided_by") != uname)
        if terminal and not owner_override:
            return False, {"error": f"card already {card.get('status')} — no re-decision"}
        # invest leg (v10): an invest card binds ONLY on the owner's sign — validate BEFORE any
        # write (derived-balance check; no wallet row lands without this passing). Invest cards
        # carry no lane, so their decider is always the owner.
        inv = card.get("invest")
        if action == "approve" and inv:
            ok, verr = _validate_invest(card)
            if not ok:
                return False, {"error": verr}
        ts_iso = now_iso()
        new = dict(card)
        fb = list(card.get("feedback") or [])
        if owner_override:
            overrides = list(card.get("overrides") or [])
            overrides.append({"by": card.get("decided_by"), "action": card.get("decision"),
                              "ts": card.get("decided_ts")})
            new["overrides"] = overrides
        if action == "approve":
            new.update(status="APPROVED", decision="approve",
                       decided_by=uname, decided_role=role, decided_ts=ts_iso,
                       approved_by=uname)
            if role == "owner":
                new["khalid_approved_ts"] = ts_iso
        elif action == "reject":
            new.update(status="REJECTED", decision="reject",
                       decided_by=uname, decided_role=role, decided_ts=ts_iso,
                       rejected_by=uname)
            if role == "owner":
                new["khalid_rejected_ts"] = ts_iso
        else:
            fb.append({"ts": ts_iso, "text": str(feedback or "").strip(), "by": uname})
            new.update(status="NEEDS-FEEDBACK", feedback=fb, decision="feedback",
                       decided_by=uname, decided_role=role, decided_ts=ts_iso,
                       feedback_by=uname)
            if role == "owner":
                new["khalid_feedback_ts"] = ts_iso
        new["updated_ts"] = ts_iso
        # invest leg: approved invest card -> append the kind=invest wallet row (real debit).
        # Written BEFORE the card row so a failed wallet append aborts the whole approval.
        invest_result = None
        if action == "approve" and inv:
            invest_result = _write_invest_row(card, new)
            if not invest_result.get("written"):
                return False, {"error": invest_result.get("error")}
        # 1) append the new row to the card ledger (append-only, latest wins)
        with open(APPROVALS, "a") as f:
            f.write(json.dumps(new, ensure_ascii=False) + "\n")
        # 2) local append-only decisions ledger
        ledger_row = {"ts": ts_iso,
                      "kind": "khalid-decision" if role == "owner" else "lane-decision",
                      "card_id": card_id,
                      "action": action, "title": card.get("title"),
                      "proposer": card.get("proposer"),
                      "decision_text": card.get("summary", "")[:160],
                      "status": new["status"], "by": uname, "role": role,
                      "lane": card_lane(card),
                      "feedback": feedback if action == "feedback" else None,
                      "source": "fleet-dashboard /approvals"}
        with open(DECISIONS_LEDGER, "a") as f:
            f.write(json.dumps(ledger_row, ensure_ascii=False) + "\n")
        # 3) canonical GitHub decisions ledger (best-effort — hearth PAT is read-only on
        #    bawes-knowledge; a write-scoped PAT must be vaulted to activate the sync)
        gh = {"synced": False, "error": None}
        try:
            gh_append_decision(ledger_row)
            gh["synced"] = True
        except Exception as e:
            gh["error"] = f"{type(e).__name__}: {e}"
            with open(DECISIONS_LEDGER, "a") as f:
                f.write(json.dumps({"ts": now_iso(), "kind": "gh-ledger-sync-failed",
                                    "card_id": card_id, "action": action,
                                    "error": gh["error"]}, ensure_ascii=False) + "\n")
    return True, {"card": new, "decision_row": ledger_row, "gh_sync": gh,
                  "invest": invest_result,
                  "pending_count": approvals_data()["pending_count"]}


# ---------------------------------------------------------------- agent relay (comms)
def relay_rows(limit=20):
    """Latest relay messages, newest first. Reads the canonical append-only
    /srv/bricks/orchestrator/agent-relay.jsonl (mirrored to the repo drop-box
    by relay_sync.py every 60s)."""
    rows = read_jsonl(RELAY)
    if rows is None:
        return {"status": "missing", "messages": [], "total": 0, "file": RELAY}
    return {"status": "ok", "messages": rows[-limit:][::-1], "total": len(rows),
            "file": RELAY,
            "note": "append-only agent-relay.jsonl — mirrored to the bawes-fleet drop-box every 60s by relay_sync.py (≤60s lag for cloud agents)"}


def relay_append(row):
    """Append one row under a cross-process flock (dashboard + relay_sync share it)."""
    with RELAY_LOCK:
        fd = os.open(RELAY, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o664)
        try:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.write(fd, (json.dumps(row, ensure_ascii=False) + "\n").encode())
            os.fsync(fd)
        finally:
            os.close(fd)
    return row


def relay_rate_check(user):
    """(ok, retry_after_sec). owner (khalid): 1 msg/min; others: 5 msg/hr.
    In-memory only (deliberately simple) — resets on service restart."""
    name = str(user.get("username") or "?")
    role = str(user.get("role") or "")
    now = time.time()
    q = _relay_rate.setdefault(name, collections.deque())
    window = 60.0 if role == "owner" else 3600.0
    limit = RATE_OWNER_PER_MIN if role == "owner" else RATE_OTHER_PER_HOUR
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False, int(window - (now - q[0])) + 1
    q.append(now)
    return True, 0


# ---------------------------------------------------------------- aggregate
# ---------------------------------------------------------------- who / burn / cut-burn (v5)
def _num(v):
    try:
        n = float(v)
        return n if n == n and abs(n) != float("inf") else None
    except (TypeError, ValueError):
        return None


def lanes_data(force=False):
    """Latest row per lane_id from the router lanes.jsonl (append-only, latest wins)."""
    now = time.time()
    if not force and lanes_cache["ts"] and now - lanes_cache["ts"] < 60:
        return lanes_cache["out"]
    rows = read_jsonl(LANES)
    if not rows:
        out = {"status": "missing", "lanes": {}, "lane_count": 0, "file": LANES}
    else:
        by_id = {}
        for r in rows:
            if isinstance(r, dict) and r.get("lane_id"):
                by_id[str(r["lane_id"])] = r
        out = {"status": "ok", "lanes": by_id, "lane_count": len(by_id), "file": LANES,
               "note": "router lanes.jsonl — latest row per lane wins; 'active' is what the router currently allows."}
    lanes_cache.update(ts=now, out=out)
    return out


def lane_control_rows():
    rows = read_jsonl(LANE_CONTROL)
    return [r for r in (rows or []) if isinstance(r, dict)]


def ledger_summary():
    """Real router ledger: per-lane calls/spend + last-1h/24h velocity (append-only real rows)."""
    now = time.time()
    if ledger_cache["ts"] and now - ledger_cache["ts"] < 60:
        return ledger_cache["out"]
    rows = read_jsonl(LANE_LEDGER)
    if not rows:
        out = {"status": "missing", "rows": 0, "by_lane": {}, "file": LANE_LEDGER,
               "per_hour": None, "per_hour_calls": 0, "per_day": None, "per_day_calls": 0,
               "total_cost": 0.0, "last_ts": None}
        ledger_cache.update(ts=now, out=out)
        return out
    by_lane = {}
    total_cost = 0.0
    maxts = 0
    for r in rows:
        lane = str(r.get("lane") or r.get("lane_id") or "?")
        ts = r.get("ts")
        if isinstance(ts, (int, float)):
            maxts = max(maxts, float(ts))
        cost = _num(r.get("cost")) or 0.0
        total_cost += cost
        e = by_lane.setdefault(lane, {"calls": 0, "cost": 0.0, "last_ts": None, "model": r.get("model")})
        e["calls"] += 1
        e["cost"] += cost
        if isinstance(ts, (int, float)) and (e["last_ts"] is None or ts > e["last_ts"]):
            e["last_ts"] = float(ts)
            if r.get("model"):
                e["model"] = r.get("model")
    h1 = {"cost": 0.0, "calls": 0}
    d1 = {"cost": 0.0, "calls": 0}
    if maxts:
        for r in rows:
            ts = r.get("ts")
            if not isinstance(ts, (int, float)):
                continue
            cost = _num(r.get("cost")) or 0.0
            if ts >= maxts - 3600:
                h1["cost"] += cost
                h1["calls"] += 1
            if ts >= maxts - 86400:
                d1["cost"] += cost
                d1["calls"] += 1
    out = {"status": "ok", "rows": len(rows), "total_cost": round(total_cost, 4),
           "last_ts": maxts, "by_lane": by_lane,
           "per_hour": round(h1["cost"], 4), "per_hour_calls": h1["calls"],
           "per_day": round(d1["cost"], 4), "per_day_calls": d1["calls"],
           "file": LANE_LEDGER,
           "note": "router ledger.jsonl — every routed call appends a real row (lane, model, cost). "
                   "Velocity = real rows in the last 1h / 24h."}
    ledger_cache.update(ts=now, out=out)
    return out


def burn_data():
    """BURN RATE: spend velocity ($/hr, $/day) + free-vs-paid split, real rows only."""
    led = ledger_summary()
    lanes = lanes_data().get("lanes", {})
    door = door_cost_data()
    free_lanes, paid_lanes = [], []
    for lid in sorted(lanes):
        r = lanes[lid]
        if not isinstance(r, dict):
            continue
        cpt = _num(r.get("cost_per_task"))
        is_free = (cpt == 0.0) or lid in FREE_LANE_IDS
        bl = led.get("by_lane", {}).get(lid, {})
        rec = {"lane": lid, "model": r.get("model"), "cost_per_task": cpt,
               "active": bool(r.get("active")), "calls": bl.get("calls", 0),
               "cost": round(bl.get("cost", 0.0), 4), "last_ts": bl.get("last_ts")}
        (free_lanes if is_free else paid_lanes).append(rec)
    free_calls = sum(l["calls"] for l in free_lanes)
    paid_calls = sum(l["calls"] for l in paid_lanes)
    total_calls = free_calls + paid_calls
    free_pct = round(free_calls * 100.0 / total_calls, 1) if total_calls else 0.0
    carrying = sorted([l["lane"] for l in free_lanes if l["calls"] > 0])
    drawdown = None
    try:
        sp = spend_data()
        series = sp.get("series") or []
        ds = [(s.get("ts"), _num(s.get("deepseek"))) for s in series if _num(s.get("deepseek")) is not None]
        if len(ds) >= 2:
            t2, b2 = ds[-1]
            t1, b1 = ds[-2]
            try:
                t2f = datetime.datetime.fromisoformat(str(t2).replace("Z", "+00:00")).timestamp()
                t1f = datetime.datetime.fromisoformat(str(t1).replace("Z", "+00:00")).timestamp()
            except Exception:
                t2f, t1f = 0.0, 0.0
            days = max((t2f - t1f) / 86400.0, 0.001)
            drawdown = {"per_day": round((b1 - b2) / days, 2), "from": b1, "to": b2,
                        "from_ts": str(t1)[:16], "to_ts": str(t2)[:16],
                        "note": "deepseek balance drawdown between consecutive spend.jsonl snapshots — balance change, not metered usage"}
    except Exception:
        drawdown = None
    return {
        "status": led.get("status"),
        "rows": led.get("rows"), "total_spend": led.get("total_cost"),
        "per_hour": led.get("per_hour"), "per_hour_calls": led.get("per_hour_calls"),
        "per_day": led.get("per_day"), "per_day_calls": led.get("per_day_calls"),
        "last_ledger_ts": led.get("last_ts"),
        "free": {"lanes": free_lanes, "calls": free_calls, "pct": free_pct, "carrying": carrying},
        "paid": {"lanes": paid_lanes, "calls": paid_calls,
                 "pct": round(100.0 - free_pct, 1) if total_calls else 0.0},
        "door_cost": {"rows": door.get("rows"),
                      "total": door.get("total_usd"),
                      "last_ts": (door.get("per_day") or [{}])[-1].get("day") if door.get("status") == "ok" else None,
                      "note": ("door-cost.jsonl metered door calls ($0.002 deepseek-flash)"
                               if door.get("status") == "ok"
                               else "door-cost meter not on this box yet — it is not $0")},
        "drawdown": drawdown,
        "notes": [
            "per-lane USD metering IS real: every routed call appends a row to the router ledger",
            "free lanes cost $0 per call — zero-USD lanes, not 'free capacity'",
            "Nous paid usage lives on the control host — not metered on this box",
        ],
    }


def vector_last_ts():
    """Latest doc write ts + doc count from vector-store.json (single JSON doc array)."""
    try:
        d = json.load(open(VECTOR))
        docs = d.get("docs", []) or []
        ts = None
        for doc in docs:
            t = doc.get("ts")
            if isinstance(t, (int, float)) and (ts is None or t > ts):
                ts = float(t)
        return ts, len(docs)
    except Exception:
        return None, None


def _relay_by_from():
    rows = read_jsonl(RELAY)
    out = {}
    for r in (rows or []):
        if isinstance(r, dict) and r.get("from"):
            f = str(r["from"]).lower()
            if f not in out or str(r.get("ts", "")) > str(out[f].get("ts", "")):
                out[f] = r
    return out


def _kanban_fleet():
    """Fleet kanban board (sqlite, read-only): tasks + latest comment. No CLI spawn on refresh."""
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{KANBAN_BOARD_DB}?mode=ro", uri=True, timeout=3)
        cur = con.cursor()
        tasks = []
        try:
            for row in cur.execute("SELECT id, title, assignee, status, created_at FROM tasks ORDER BY created_at DESC LIMIT 30"):
                tasks.append({"id": row[0], "title": row[1], "assignee": row[2],
                              "status": row[3], "created_at": row[4]})
        except Exception:
            pass
        last_comment = None
        try:
            row = cur.execute("SELECT task_id, author, substr(body,1,160), created_at "
                              "FROM task_comments ORDER BY created_at DESC LIMIT 1").fetchone()
            if row:
                last_comment = {"task_id": row[0], "author": row[1], "body": row[2], "created_at": row[3]}
        except Exception:
            pass
        con.close()
        return {"status": "ok", "tasks": tasks, "count": len(tasks), "last_comment": last_comment}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}", "tasks": [], "count": 0,
                "last_comment": None}


def who_data():
    """WHO'S DOING WHAT — per known agent: live/idle + most recent REAL activity.
    Sources: agent-relay (last msg per from), router ledger (last call per lane),
    heartbeat registry (per brick_id), fleet kanban board (task states), /proc (fleet processes).
    Anything with no signal on this box says so — never invented."""
    now = time.time()
    relay = _relay_by_from()
    led = ledger_summary()
    hb = heartbeat_data()
    hb_last = {r["id"]: r["last_ts"] for r in (hb.get("live", []) + hb.get("idle", []) + hb.get("silent", []))}
    kb = _kanban_fleet()
    kb_by_assignee = {}
    for t in kb.get("tasks", []):
        a = str(t.get("assignee") or "").lower()
        if a:
            kb_by_assignee.setdefault(a, []).append(t)
    vec_ts, vec_count = vector_last_ts()
    procs = fleet_processes()
    running = {p.lower() for p in procs.get("processes", [])}

    def iso_ts(v):
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
        except Exception:
            return None

    def state_from(age):
        if age is None:
            return "NO SIGNAL"
        if age <= FRESH_SEC:
            return "LIVE"
        if age <= SEEN7D_SEC:
            return "IDLE"
        return "SILENT"

    def build(name, sigs):
        """sigs: list of (ts, source_label, activity_text). Newest wins for status+activity."""
        sigs = [s for s in sigs if s and s[0] is not None]
        if not sigs:
            return {"name": name, "status": "NO SIGNAL", "activity": "no signal on this box",
                    "when": None, "source": None, "sources": []}
        sigs.sort(key=lambda s: -s[0])
        top = sigs[0]
        return {"name": name, "status": state_from(now - top[0]), "activity": top[2],
                "when": top[0], "source": top[1],
                "sources": [s[2] for s in sigs[:3]]}

    agents = []
    # Brick — on-box PM/orchestrator (worker-001)
    sigs = []
    rb = relay.get("brick")
    if rb:
        t = iso_ts(rb.get("ts"))
        if t:
            sigs.append((t, "relay", f"relay: {str(rb.get('body'))[:100]}"))
    if "orchestrator.py" in running:
        sigs.append((now, "process", "orchestrator.py serving (worker-001) — process is up right now"))
    agents.append(build("Brick", sigs))

    # AGI — fleet brain judge
    sigs = []
    ra = relay.get("agi")
    if ra:
        t = iso_ts(ra.get("ts"))
        if t:
            sigs.append((t, "relay", f"relay: {str(ra.get('body'))[:100]}"))
    if vec_ts:
        sigs.append((vec_ts, "knowledge", f"knowledge store last write ({vec_count} docs)"))
    for t in kb_by_assignee.get("agi", []):
        if t.get("created_at"):
            sigs.append((float(t["created_at"]), "kanban", f"kanban task '{str(t.get('title'))[:60]}' ({t.get('status')})"))
    agents.append(build("AGI", sigs))

    # ox-alpha — free-ox lane + hermes-local heartbeat
    sigs = []
    bl = led.get("by_lane", {}).get("free-ox", {})
    if bl.get("last_ts"):
        sigs.append((bl["last_ts"], "router", f"last routed call on free-ox lane ({bl.get('calls', 0)} calls)"))
    hl = hb_last.get("hermes-local")
    if hl:
        sigs.append((hl, "heartbeat", "last heartbeat as hermes-local"))
    ro = relay.get("oxalpha") or relay.get("ox-alpha")
    if ro:
        t = iso_ts(ro.get("ts"))
        if t:
            sigs.append((t, "relay", f"relay: {str(ro.get('body'))[:100]}"))
    agents.append(build("ox-alpha", sigs))

    # OxBaby — no direct channel on this box yet
    sigs = []
    rob = relay.get("oxbaby")
    if rob:
        t = iso_ts(rob.get("ts"))
        if t:
            sigs.append((t, "relay", f"relay: {str(rob.get('body'))[:100]}"))
    agents.append(build("OxBaby", sigs))

    # DA — ruling body; rulings land in the knowledge store, no live channel yet
    sigs = []
    rda = relay.get("da")
    if rda:
        t = iso_ts(rda.get("ts"))
        if t:
            sigs.append((t, "relay", f"relay: {str(rda.get('body'))[:100]}"))
    agents.append(build("DA", sigs))

    # Rebel — dissenting voice; no direct channel on this box
    sigs = []
    rr = relay.get("rebel")
    if rr:
        t = iso_ts(rr.get("ts"))
        if t:
            sigs.append((t, "relay", f"relay: {str(rr.get('body'))[:100]}"))
    agents.append(build("Rebel", sigs))

    return {"status": "ok", "agents": agents, "probed": {
        "relay_rows": len(read_jsonl(RELAY) or []),
        "ledger_rows": led.get("rows"),
        "kanban_tasks": kb.get("count"),
        "fleet_processes": procs.get("processes"),
    },
        "note": "signals: agent-relay (last msg), router ledger (last routed call), heartbeat registry, "
                "fleet kanban board, /proc processes. LIVE ≤5 min, IDLE ≤7 d, SILENT >7 d. "
                "Cloud agents that signal through the repo drop-box only show 'no signal' until their message reaches the relay."}


def lane_state():
    """Merged toggle state: router lanes.jsonl active flag + lane-control.jsonl pauses (latest wins)."""
    lanes = lanes_data().get("lanes", {})
    last_ctl = {}
    for r in lane_control_rows():
        lane = str(r.get("lane") or "")
        if lane:
            last_ctl[lane] = r
    out = []
    for lid in TOGGLE_LANES:
        r = lanes.get(lid)
        c = last_ctl.get(lid)
        router_active = bool(r and r.get("active"))
        cpt = _num(r.get("cost_per_task")) if r else None
        is_free = (cpt == 0.0) if cpt is not None else (lid in FREE_LANE_IDS)
        ctl_action = c.get("action") if c else None
        if ctl_action == "pause":
            on = False
        elif ctl_action == "resume":
            on = router_active
        else:
            on = router_active
        bl = ledger_summary().get("by_lane", {}).get(lid, {})
        out.append({
            "lane": lid,
            "model": r.get("model") if r else None,
            "registered": r is not None,
            "router_active": router_active,
            "control": ctl_action,
            "on": on,
            "free": is_free,
            "cost_per_task": cpt,
            "calls": bl.get("calls", 0),
            "cost": round(bl.get("cost", 0.0), 4),
            "last_call_ts": bl.get("last_ts"),
            "last_control": {"ts": c.get("ts"), "by": c.get("by")} if c else None,
        })
    return {"status": "ok", "lanes": out, "file": LANES, "control_file": LANE_CONTROL,
            "note": "switch = router lane active AND not paused by a lane-control directive. "
                    "nous-paid has no router lane on this box — toggling logs the directive + kanban comment only."}


def kanban_ensure_ctrl_task():
    """Find or create the lane-control task on the fleet board (hermes CLI). Returns task id or None."""
    env = dict(os.environ)
    env.setdefault("HOME", "/home/ubuntu")
    env["PATH"] = "/usr/local/bin:" + env.get("PATH", "")

    def run(args, timeout=45):
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)
    try:
        r = run(["hermes", "kanban", "--board", KANBAN_BOARD, "list", "--json"])
        if r.returncode == 0:
            try:
                tasks = json.loads(r.stdout or "[]")
            except Exception:
                tasks = []
            for t in tasks:
                if str(t.get("title", "")).startswith("lane-control"):
                    return str(t.get("id")) or None
        r = run(["hermes", "kanban", "--board", KANBAN_BOARD, "create", KANBAN_CTRL_TITLE,
                 "--body", "Khalid's lane pause/resume directives land here as comments. "
                           "Written by the fleet dashboard when he flips a CUT BURN toggle.",
                 "--json"])
        if r.returncode == 0:
            try:
                return str(json.loads(r.stdout or "{}").get("id") or "") or None
            except Exception:
                return None
    except Exception:
        return None
    return None


def lane_control_append(lane, action, by):
    """Append {ts, lane, action, by} to lane-control.jsonl (flock) AND comment it on the
    fleet kanban board so agents see the cut in-band. Kanban is best-effort — a failure
    is reported in the response, never fatal to the directive."""
    row = {"ts": now_iso(), "lane": lane, "action": action, "by": by}
    kanban = {"ok": False, "error": None, "task_id": None}
    with LANE_LOCK:
        fd = os.open(LANE_CONTROL, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o664)
        try:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.write(fd, (json.dumps(row, ensure_ascii=False) + "\n").encode())
            os.fsync(fd)
        finally:
            os.close(fd)
    try:
        task_id = kanban_ensure_ctrl_task()
        kanban["task_id"] = task_id
        verb = "PAUSED (cut)" if action == "pause" else "RESUMED"
        text = (f"LANE CONTROL by {by}: {verb} lane '{lane}' at {row['ts']}. "
                f"Written from the fleet dashboard CUT BURN toggle. Agents: honor this in-band — "
                f"{'stop routing to ' + lane + ' until the owner resumes it.' if action == 'pause' else lane + ' is open again.'}")
        if task_id:
            env = dict(os.environ)
            env.setdefault("HOME", "/home/ubuntu")
            env["PATH"] = "/usr/local/bin:" + env.get("PATH", "")
            r = subprocess.run(["hermes", "kanban", "--board", KANBAN_BOARD, "comment",
                                task_id, text, "--author", by],
                               capture_output=True, text=True, timeout=60, env=env)
            kanban["ok"] = (r.returncode == 0)
            if not kanban["ok"]:
                kanban["error"] = (r.stderr or r.stdout or "").strip()[:300]
        else:
            kanban["error"] = "could not find/create lane-control task on the fleet kanban board"
    except Exception as e:
        kanban["error"] = f"{type(e).__name__}: {e}"
    return row, kanban


def ecosystem_data():
    """Spawn-orchestrator panel: bottleneck events, spawns, brick lifecycle states.
    Read-only — the detector/spawner/killer write the files; the dashboard renders."""
    bots = [r for r in (read_jsonl(BOTTLENECKS) or []) if isinstance(r, dict)]
    sps = [r for r in (read_jsonl(SPAWNS) or []) if isinstance(r, dict)]
    reg_rows = [r for r in (read_jsonl(REGISTRY) or []) if isinstance(r, dict)]
    wal_rows = [r for r in (read_jsonl(WALLET) or []) if isinstance(r, dict)]

    # latest registry row per brick -> lifecycle state counts
    latest = {}
    for r in reg_rows:
        if r.get("brick_id"):
            latest[r["brick_id"]] = r
    counts = {"active": 0, "verified": 0, "registered": 0, "retiring": 0, "retired": 0, "unknown": 0}
    for bid, row in latest.items():
        st = "unknown"
        if row.get("kind") == "retired" or row.get("status") == "retired":
            st = "retired"
        elif row.get("status") == "retiring":
            st = "retiring"
        elif row.get("active") is True:
            st = "active"
        elif row.get("quality") == "verified":
            st = "verified"
        else:
            st = "registered"
        counts[st] += 1

    # empty wallets: brick has wallet-open row(s) but zero earn rows
    earners = {r.get("brick_id") for r in wal_rows if r.get("kind") == "earn"}
    wallet_ids = {r.get("brick_id") for r in wal_rows if r.get("kind") == "wallet-open"}
    empty_wallets = len(wallet_ids - earners)

    def brief(e):
        return {"ts": e.get("ts"), "reason": e.get("reason"), "brick_id": e.get("brick_id"),
                "metric_value": e.get("metric_value"), "threshold": e.get("threshold"),
                "detail": e.get("detail")}

    return {
        "status": "ok",
        "file": {"bottlenecks": BOTTLENECKS, "spawns": SPAWNS},
        "counts": counts,
        "empty_wallets": empty_wallets,
        "bottlenecks": {"total": len(bots), "latest": [brief(e) for e in bots[-8:]]},
        "spawns": {"total": len(sps), "latest": [{
            "ts": s.get("ts"), "new_brick_id": s.get("new_brick_id"),
            "replaces": s.get("replaces"), "reason": s.get("reason"),
            "card_id": s.get("card_id")} for s in sps[-5:]]},
        "note": "bottlenecks.jsonl / spawns.jsonl written by spawn_ecosystem.py (append-only). "
                "Retiring = tagged phase-1; retired = reaped phase-2 after 24h + handoff evidence.",
    }


def _vel_iso(ts):
    """Epoch or ISO ts -> 'MM-DD HH:MMZ' UTC display label."""
    t = _iso_to_ts(ts)
    if t is None:
        s = str(ts or "")
        return s[5:16].replace("T", " ") if "T" in s else "?"
    return time.strftime("%m-%d %H:%M", time.gmtime(t)) + "Z"


def _vel_base(path):
    """Basename only — panels never expose absolute filesystem paths publicly."""
    s = str(path or "").strip()
    return s.replace("\\", "/").rsplit("/", 1)[-1] if s else None


def velocity_data():
    """VELOCITY + EVOLUTION — khalid's burn -> verify -> mint loop, made VISIBLE.

    Real ledgers only, nothing fabricated (V-18 house rule):
      burn    = receipts-ovh.jsonl rows (calls/tokens/$0 free-lane burns + artifacts)
      verify  = verify-queue.jsonl verification-requests (pre/post state deltas)
      mint    = wallet.jsonl kind=earn rows (card_id + bananas + artifact + verifier)
      capacity= brick-ledger.json (threads budget contract) + fleet-realtime.json
    RED->GREEN flips are DERIVED honestly: a verify probe whose post-state differs
    from its pre-state counts as one flip. No flip data yet => honest zero.
    Sanitised for public serving: basenames only, no keys/tokens/IPs/person ids,
    no absolute paths. Cached ~10s (matches the panel auto-refresh beat).
    """
    with VELOCITY_LOCK:
        if time.time() - velocity_cache["ts"] < VELOCITY_CACHE_SECS and velocity_cache["out"] is not None:
            return velocity_cache["out"]
    now = time.time()

    def _load_json(p):
        try:
            with open(p) as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    rt = _load_json(FLEET_REALTIME)
    ledger = _load_json(BRICK_LEDGER)
    tel_live = _load_json(TELEMETRY_LIVE)

    # ---- BURN leg (receipts = real burn rows; realtime scoreboard = headline) ----
    rec_rows = [r for r in (read_jsonl(RECEIPTS_OVH) or []) if isinstance(r, dict)]
    rec_1h = [r for r in rec_rows if _iso_to_ts(r.get("ts")) is not None
              and now - _iso_to_ts(r.get("ts")) <= 3600]
    calls_1h_rec = sum(int(r.get("calls") or 1) for r in rec_1h)
    tokens_1h_rec = sum(int(r.get("tokens") or 0) for r in rec_1h)
    cost_1h = round(sum(float(r.get("cost") or 0) for r in rec_1h), 4)
    burns_all = []
    for r in rec_rows:
        t = _iso_to_ts(r.get("ts"))
        burns_all.append({
            "_t": t or 0, "ts": r.get("ts"), "iso": _vel_iso(r.get("ts")),
            "task_id": str(r.get("task_id") or r.get("goal") or "?")[:40],
            "lane": r.get("lane"), "kind": r.get("kind") or "burn",
            "calls": int(r.get("calls") or 1), "tokens": int(r.get("tokens") or 0),
            "cost": float(r.get("cost") or 0),
            "artifact": _vel_base(r.get("artifact")),
        })
    burns_all.sort(key=lambda b: b["_t"], reverse=True)
    novel_docs = sorted({_vel_base(b.get("artifact")) for b in burns_all
                         if b.get("artifact") and now - (b["_t"] or 0) <= 86400})

    # ---- MINT leg (wallet earn rows; classify like evolution_feed.py) ----
    wal = [r for r in (read_jsonl(WALLET) or []) if isinstance(r, dict)]
    earns = [r for r in wal if r.get("kind") == "earn"]
    mints = []
    n_verified = n_contested = n_legacy = 0
    for e in earns:
        try:
            ban = float(e.get("bananas", 0) or 0)
        except (TypeError, ValueError):
            ban = 0.0
        verified_sig = bool(e.get("response_signature")) or str(e.get("signature_alg") or "") == "ES256"
        if e.get("contested"):
            status = "contested"
            n_contested += 1
        elif verified_sig:
            status = "verified"
            n_verified += 1
        else:
            status = "legacy"
            n_legacy += 1
        mints.append({
            "_t": _iso_to_ts(e.get("ts")) or 0, "iso": _vel_iso(e.get("ts")),
            "card_id": str(e.get("card_id") or "?")[:48], "bananas": ban,
            "artifact": _vel_base(e.get("artifact")),
            "brick": str(e.get("brick_id") or e.get("person_id") or "?")[:32],
            "status": status, "verifier": str(e.get("verifier") or "")[:24],
        })
    mints.sort(key=lambda m: m["_t"], reverse=True)
    bananas_total = sum(m["bananas"] for m in mints)

    # ---- VERIFY leg + merged EVOLUTION FEED (burn -> verify -> mint, newest first) ----
    vrows = [r for r in (read_jsonl(VERIFY_QUEUE) or []) if isinstance(r, dict)]
    events = []
    flips_24h = 0
    for v in vrows:
        pre, post = v.get("pre") or {}, v.get("post") or {}
        delta = {k: [pre[k], post[k]] for k in post
                 if k in pre and post.get(k) != pre.get(k)
                 and isinstance(pre.get(k), (int, float, str))}
        flip = bool(delta)
        vt = _iso_to_ts(v.get("ts")) or 0
        if flip and now - vt <= 86400:
            flips_24h += 1
        snippet = " ".join(str(v.get("proposal") or "").split())[:110]
        events.append({"type": "verify", "ts": v.get("ts"), "iso": _vel_iso(v.get("ts")),
                       "flip": flip, "delta": delta,
                       "label": ("RED->GREEN flip — " + ", ".join(f"{k} {d[0]}->{d[1]}" for k, d in list(delta.items())[:3]))
                                if flip else ("verification requested — " + snippet)})
    for b in burns_all[:20]:
        tok = f" / {b['tokens']:,} tok" if b["tokens"] else ""
        events.append({"type": "burn", "ts": b["ts"], "iso": b["iso"], "flip": False,
                       "label": f"burned {b['calls']} call{'' if b['calls'] == 1 else 's'}{tok} "
                                f"($0 free lane) -> {b['artifact'] or 'no artifact'}"})
    for m in mints[:20]:
        tag = {"verified": "VERIFIED", "contested": "CONTESTED", "legacy": "legacy"}[m["status"]]
        events.append({"type": "mint", "ts": m["_t"] or None, "iso": m["iso"],
                       "flip": False, "verified": m["status"] == "verified",
                       "label": f"minted {m['bananas']:g}\U0001F34C {m['card_id']} ({tag}"
                                f"{', by ' + m['verifier'] if m['verifier'] else ''}) -> {m['artifact'] or '?'}"})
    events.sort(key=lambda ev: _iso_to_ts(ev.get("ts")) or 0, reverse=True)

    # ---- CAPACITY gauges (brick-ledger thread contract vs live bricks) ----
    per_brick = []
    threads_budget = threads_live_cap = bricks_live = 0
    for bid, b in sorted((ledger.get("per_brick") or {}).items()):
        if not isinstance(b, dict):
            continue
        cap = int(b.get("capacity_threads") or 0)
        live = bool(b.get("live"))
        threads_budget += cap
        if live:
            threads_live_cap += cap
            bricks_live += 1
        per_brick.append({"id": str(bid)[:32], "role": str(b.get("role") or "?")[:28],
                          "cap": cap, "live": live,
                          "bananas": float(b.get("bananas_earned") or 0),
                          "mints": int(b.get("mints") or 0)})
    per_brick.sort(key=lambda x: (not x["live"], -x["cap"]))
    ovh = rt.get("ovh") or {}
    mem = ovh.get("mem") or {}
    queue = rt.get("queue") or {}
    payload = {
        "status": "ok",
        "generated_at": now_iso(),
        "sources": ["fleet-realtime.json", "receipts-ovh.jsonl", "wallet.jsonl",
                    "verify-queue.jsonl", "brick-ledger.json", "telemetry-live.json"],
        "burn": {
            "calls_1h": rt.get("burn_ovh", {}).get("last_1h"),
            "tokens_1h": rt.get("burn_ovh", {}).get("tokens_1h"),
            "total_burns": rt.get("burn_ovh", {}).get("total"),
            "receipts_calls_1h": calls_1h_rec,
            "receipts_tokens_1h": tokens_1h_rec,
            "cost_1h_usd": cost_1h,
            "free_lane_note": "all burn lanes on this box are free models — $0.00/hr metered cost",
            "recent": [{k: v for k, v in b.items() if k != "_t"} for b in burns_all[:10]],
        },
        "mints": {
            "bananas_total": round(bananas_total, 2), "mints_total": len(mints),
            "verified_count": n_verified, "contested_count": n_contested,
            "legacy_count": n_legacy,
            "timeline": [{k: v for k, v in m.items() if k != "_t"} for m in mints[:12]],
        },
        "evolution": {
            "events": events[:40],
            "flips_24h": flips_24h,
            "novel_docs_24h": novel_docs[-14:],
            "novel_docs_24h_count": len(novel_docs),
            "note": "RED->GREEN flip = verify probe whose post-state moved vs pre-state "
                    "(derived from verify-queue.jsonl). No fabricated flips — an honest "
                    "zero means none recorded in the window.",
        },
        "capacity": {
            "threads_budget": threads_budget or 75,
            "threads_live": threads_live_cap,
            "bricks_live": bricks_live,
            "bricks_total": len(per_brick),
            "threads_os_total": ovh.get("threads") or tel_live.get("total_threads"),
            "mem_used_mb": mem.get("used_mb"), "mem_total_mb": mem.get("total_mb"),
            "load_1m": (ovh.get("load") or [None])[0],
            "queue_pending": queue.get("pending"), "queue_total": queue.get("total"),
            "heartbeats_1h": rt.get("bricks_heartbeating_1h"),
            "per_brick": per_brick,
        },
    }
    with VELOCITY_LOCK:
        velocity_cache["ts"] = time.time()
        velocity_cache["out"] = payload
    return payload


def velocity_panel_html():
    """Self-contained dark gold/teal page for /panel/velocity. Static markup +
    vanilla JS fetching /api/velocity every 15s — no external assets, nothing paid."""
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ Velocity &amp; Evolution — BAWES Fleet</title>
<style>
:root{--bg:#0b0a06;--bg2:#14100a;--card:#171307;--line:#2b2310;--gold:#f5b942;--gold2:#ffd97a;
--teal:#3dd6a4;--red:#ff6b5e;--txt:#f3ead6;--dim:#b7ab90;--faint:#776c55;--mono:'SF Mono',ui-monospace,Menlo,monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(1200px 500px at 70% -10%,#1a1408,var(--bg));color:var(--txt);
font:15px/1.5 -apple-system,'Segoe UI',Roboto,sans-serif;padding:22px}
a{color:var(--teal);text-decoration:none}
header{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:18px}
h1{font-size:21px;font-weight:800;color:var(--gold);letter-spacing:.4px}
h1 .zap{filter:drop-shadow(0 0 8px rgba(245,185,66,.5))}
.sub{color:var(--faint);font-size:12.5px;width:100%}
.pill{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);background:var(--card);
border-radius:999px;padding:7px 13px;font-size:12.5px;font-weight:700;color:var(--dim)}
.dot{width:9px;height:9px;border-radius:50%;background:var(--teal);box-shadow:0 0 9px var(--teal)}
.dot.off{background:var(--red);box-shadow:0 0 9px var(--red)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:16px}
.stat{border:1px solid var(--line);background:linear-gradient(180deg,var(--card),var(--bg2));
border-radius:14px;padding:13px 15px}
.stat .v{font-size:27px;font-weight:800;color:var(--gold);font-family:var(--mono);line-height:1.15}
.stat .v.teal{color:var(--teal)} .stat .v small{font-size:13px;color:var(--dim);font-weight:700}
.stat .l{font-size:10.5px;color:var(--faint);letter-spacing:.9px;text-transform:uppercase;font-weight:800;margin-top:3px}
.free{display:inline-block;margin-top:5px;background:rgba(61,214,164,.12);border:1px solid rgba(61,214,164,.45);
color:var(--teal);border-radius:999px;font-size:11px;font-weight:800;padding:2px 10px}
section{border:1px solid rgba(245,185,66,.35);background:var(--card);border-radius:16px;padding:15px 17px;margin-bottom:16px}
section h2{font-size:13px;letter-spacing:1.4px;text-transform:uppercase;color:var(--gold);margin-bottom:12px}
.gauges{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.gauge .gt{display:flex;justify-content:space-between;font-size:12px;color:var(--dim);margin-bottom:5px}
.gauge .gt b{color:var(--txt);font-family:var(--mono)}
.bar{height:12px;border-radius:999px;background:var(--bg2);border:1px solid var(--line);overflow:hidden}
.bar i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#2e8f72,var(--teal));
transition:width .6s ease}
.bar.gold i{background:linear-gradient(90deg,#8a6a1e,var(--gold))}
.bar.warn i{background:linear-gradient(90deg,#8a4a1e,var(--red))}
.bricks{margin-top:13px;display:flex;flex-direction:column;gap:6px}
.brick{display:grid;grid-template-columns:150px 1fr 64px;gap:9px;align-items:center;font-size:12.5px}
.brick .bid{color:var(--dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.brick .bid b{color:var(--txt)} .brick.live .bid::before{content:'● ';color:var(--teal)}
.brick:not(.live){opacity:.55} .brick .cap{color:var(--faint);text-align:right;font-family:var(--mono)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:980px){.cols{grid-template-columns:1fr}}
.feed{max-height:430px;overflow-y:auto;display:flex;flex-direction:column;gap:7px}
.ev{display:flex;gap:9px;align-items:flex-start;border:1px solid var(--line);background:var(--bg2);
border-radius:11px;padding:8px 11px;font-size:13px}
.ev .t{flex-shrink:0;font-family:var(--mono);font-size:11px;color:var(--faint);width:78px;padding-top:2px}
.ev .tag{flex-shrink:0;font-size:9.5px;font-weight:800;letter-spacing:.8px;border-radius:6px;padding:2px 7px;margin-top:2px}
.tag.burn{background:rgba(245,185,66,.13);color:var(--gold);border:1px solid rgba(245,185,66,.4)}
.tag.verify{background:rgba(119,108,85,.15);color:var(--dim);border:1px solid var(--line)}
.tag.mint{background:rgba(61,214,164,.13);color:var(--teal);border:1px solid rgba(61,214,164,.4)}
.ev .lbl{color:var(--dim);word-break:break-word} .ev .lbl b{color:var(--txt)}
.flip{color:var(--teal);font-weight:800}
.badge{display:inline-block;font-size:9.5px;font-weight:800;letter-spacing:.7px;border-radius:6px;
padding:2px 7px;margin-left:7px;vertical-align:1px}
.badge.ok{background:rgba(61,214,164,.13);color:var(--teal);border:1px solid rgba(61,214,164,.4)}
.badge.bad{background:rgba(255,107,94,.13);color:var(--red);border:1px solid rgba(255,107,94,.4)}
.badge.old{background:rgba(119,108,85,.15);color:var(--faint);border:1px solid var(--line)}
.mintrow{border:1px solid var(--line);background:var(--bg2);border-radius:11px;padding:9px 12px;font-size:13px}
.mintrow .mt{font-family:var(--mono);font-size:11px;color:var(--faint)}
.mintrow .cid{color:var(--gold);font-weight:800;font-family:var(--mono)}
.mintrow .art{color:var(--dim);font-size:12px;word-break:break-all}
.note{font-size:11.5px;color:var(--faint);margin-top:10px;line-height:1.5}
footer{color:var(--faint);font-size:11.5px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
</style></head><body>
<header>
 <h1><span class="zap">⚡</span> VELOCITY &amp; EVOLUTION</h1>
 <span class="pill"><span class="dot" id="dot"></span><span id="beat">syncing…</span></span>
 <span class="pill">auto-refresh 15s</span>
 <a class="pill" href="/">← dashboard</a>
 <div class="sub">the loop, live: burn (free lanes) → verify → mint 🍌 — real ledgers only, nothing fabricated</div>
</header>

<div class="grid">
 <div class="stat"><div class="v" id="s-calls">—</div><div class="l">burn calls / hr</div></div>
 <div class="stat"><div class="v teal" id="s-tok">—</div><div class="l">tokens / hr</div></div>
 <div class="stat"><div class="v">$0.00</div><div class="l">metered cost / hr</div><span class="free">FREE LANES ONLY</span></div>
 <div class="stat"><div class="v" id="s-ban">—</div><div class="l">bananas minted · <span id="s-mints">—</span> mints</div></div>
</div>

<section>
 <h2>Capacity — 75-thread fleet budget</h2>
 <div class="gauges">
  <div class="gauge"><div class="gt"><span>thread capacity live</span><b id="g-thr-txt">—</b></div>
   <div class="bar gold"><i id="g-thr" style="width:0%"></i></div>
   <div class="note" id="g-os"></div></div>
  <div class="gauge"><div class="gt"><span>memory used</span><b id="g-mem-txt">—</b></div>
   <div class="bar"><i id="g-mem" style="width:0%"></i></div></div>
  <div class="gauge"><div class="gt"><span>work queue pending</span><b id="g-q-txt">—</b></div>
   <div class="bar warn"><i id="g-q" style="width:0%"></i></div></div>
  <div class="gauge"><div class="gt"><span>bricks heartbeating 1h</span><b id="g-hb-txt">—</b></div>
   <div class="bar"><i id="g-hb" style="width:0%"></i></div></div>
 </div>
 <div class="bricks" id="bricks"></div>
</section>

<div class="cols">
 <section>
  <h2>🧬 Evolution feed — burn → verify → mint</h2>
  <div class="feed" id="feed"></div>
  <div class="note" id="evo-note"></div>
 </section>
 <section>
  <h2>🍌 Mint timeline — latest earn rows</h2>
  <div class="feed" id="mints"></div>
  <div class="note" id="mint-note"></div>
 </section>
</div>

<footer>
 <div id="srcs"></div>
 <div id="genat"></div>
</footer>

<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const num=v=>{const n=typeof v==='number'?v:parseFloat(v);return isFinite(n)?n:null};
const fmtN=v=>num(v)==null?'—':Number(v).toLocaleString('en-US');
function bar(el,pct,warn){pct=Math.max(0,Math.min(100,pct||0));el.style.width=pct+'%';
 if(warn&&pct>=90)el.parentElement.classList.add('warn')}
async function tick(){
 try{
  const r=await fetch('/api/velocity',{cache:'no-store'});
  if(!r.ok)throw new Error('http '+r.status);
  const d=await r.json();
  $('dot').className='dot';$('beat').textContent='live · '+new Date().toLocaleTimeString();

  // stats
  $('s-calls').innerHTML=fmtN(d.burn.calls_1h)+' <small>calls</small>';
  $('s-tok').innerHTML=fmtN(d.burn.tokens_1h)+' <small>tok</small>';
  $('s-ban').textContent='🍌 '+fmtN(d.mints.bananas_total);
  $('s-mints').textContent=d.mints.mints_total;

  // capacity gauges
  const c=d.capacity,bud=c.threads_budget||75;
  $('g-thr-txt').textContent=c.threads_live+' / '+bud+' thr';
  bar($('g-thr'),100*c.threads_live/bud,true);
  $('g-os').textContent=c.bricks_live+' of '+c.bricks_total+' bricks live · OS threads on host: '+fmtN(c.threads_os_total)+' (info)';
  const mu=num(c.mem_used_mb),mt=num(c.mem_total_mb);
  $('g-mem-txt').textContent=(mu==null?'—':mu)+' / '+(mt==null?'—':mt)+' MB';
  bar($('g-mem'),100*mu/mt);
  const qp=num(c.queue_pending),qt=Math.max(num(c.queue_total)||0,qp||0)||1;
  $('g-q-txt').textContent=qp+' / '+qt;
  bar($('g-q'),100*qp/qt);
  $('g-hb-txt').textContent=c.heartbeats_1h+' heartbeats';
  bar($('g-hb'),Math.min(100,(c.heartbeats_1h||0)*25));

  // per-brick capacity bars
  $('bricks').innerHTML=(c.per_brick||[]).map(b=>{
   const p=bud?Math.round(100*b.cap/bud):0;
   return '<div class="brick'+(b.live?' live':'')+'">'+
    '<div class="bid"><b>'+esc(b.id)+'</b> · '+esc(b.role)+'</div>'+
    '<div class="bar gold" style="height:8px"><i style="width:'+p+'%"></i></div>'+
    '<div class="cap">'+b.cap+' thr'+(b.mints?' · '+b.mints+'🄼':'')+'</div></div>'}).join('');

  // evolution feed
  $('feed').innerHTML=(d.evolution.events||[]).map(e=>{
   const cls=e.type,tag=e.type.toUpperCase()+(e.flip?' ⚡':'');
   return '<div class="ev"><span class="t">'+esc(e.iso)+'</span><span class="tag '+cls+'">'+esc(tag)+
    '</span><span class="lbl">'+esc(e.label)+'</span></div>'}).join('')
   ||'<div class="ev"><span class="lbl">no events yet — the loop is warming up</span></div>';
  $('evo-note').textContent=d.evolution.note+' · RED→GREEN flips (24h): '+(d.evolution.flips_24h||0)+
   ' · novel docs written (24h): '+(d.evolution.novel_docs_24h_count||0);

  // mints timeline
  const bdg={verified:'<span class="badge ok">VERIFIED</span>',contested:'<span class="badge bad">CONTESTED</span>',legacy:'<span class="badge old">LEGACY</span>'};
  $('mints').innerHTML=(d.mints.timeline||[]).map(m=>
   '<div class="mintrow"><span class="mt">'+esc(m.iso)+'</span> · <span class="cid">'+esc(m.card_id)+
   '</span> <b>+'+m.bananas+'🍌</b>'+bdg[m.status]+'<div class="art">'+esc(m.artifact||'no artifact')+
   (m.verifier?' · verifier: '+esc(m.verifier):'')+'</div></div>').join('')
   ||'<div class="mintrow">no earn rows yet</div>';
  $('mint-note').textContent='verified '+d.mints.verified_count+' · contested '+d.mints.contested_count+
   ' (legacy self-mints, F-13 — history, not evidence) · legacy-unverified '+d.mints.legacy_count;

  $('srcs').textContent='sources: '+((d.sources||[]).join(' · ')||'—');
  $('genat').textContent='generated '+String(d.generated_at||'').slice(0,19)+'Z';
 }catch(e){
  $('dot').className='dot off';$('beat').textContent='offline — '+e.message;
 }
}
tick();setInterval(tick,15000);
</script>
</body></html>"""



def player_world_api():
    try:
        import json as _json
        return _json.load(open("/srv/bricks/orchestrator/player-world.json"))
    except Exception:
        return {"players": {}, "social": "world not ready"}


def observability_api():
    try:
        import json as _json
        return _json.load(open("/srv/bricks/orchestrator/observability.json"))
    except Exception:
        return {"agents": {}, "thought_chain": [], "note": "not ready"}

def public_data():
    """PUBLIC storefront aggregates — served at /api/public with NO auth, so this
    payload may ONLY carry fleet-level aggregates. Safe by construction: no keys,
    tokens, IPs, wallet contents, per-brick economics, or internal paths. Every
    number is computed by the same real-data readers as /api/data (wallet,
    heartbeat, registry, github, burn, ecosystem) — nothing invented."""
    w = wallet_data()
    hb = heartbeat_data()
    reg = registry_data()
    gh = github_data()
    burn = burn_data()
    eco = ecosystem_data()
    relay = relay_rows(6)
    ach = achievements_data()

    # PRs merged in the last 7 days (real merged_at dates from GitHub)
    merged_dates = gh.get("merged_dates") or []
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)
    prs_7d = 0
    for d in merged_dates:
        try:
            dd = datetime.date.fromisoformat(str(d)[:10])
        except Exception:
            continue
        if week_ago <= dd <= today:
            prs_7d += 1

    # canonical fleet events — aggregate, no sensitive detail (no keys, no paths)
    events = []
    sps = [r for r in (read_jsonl(SPAWNS) or []) if isinstance(r, dict)]
    for s in sps[-2:]:
        events.append({"type": "spawn", "ts": s.get("ts"),
                       "label": f"Brick {s.get('new_brick_id') or '?'} spawned into the fleet"})
    bots = [r for r in (read_jsonl(BOTTLENECKS) or []) if isinstance(r, dict)]
    for b in bots[-2:]:
        reason = str(b.get("reason") or "bottleneck detected").strip()[:70]
        events.append({"type": "flag", "ts": b.get("ts"),
                       "label": f"{b.get('brick_id') or 'a brick'} flagged — {reason}"})
    wal_rows = [r for r in (read_jsonl(WALLET) or []) if isinstance(r, dict)]
    for e in [r for r in wal_rows if (r.get("kind") or r.get("type")) == "earn"][-4:]:
        try:
            n = float(e.get("bananas", 0) or 0)
        except (TypeError, ValueError):
            n = 0.0
        if n <= 0:
            continue  # zero-banana rows are ledger noise, not mints
        events.append({"type": "earn", "ts": e.get("ts"),
                       "label": f"{e.get('brick_id') or 'a brick'} minted {n:g}🍌"})
    for a in [r for r in (read_jsonl(ACHIEVEMENTS) or []) if isinstance(r, dict)][-2:]:
        line = str(a.get("cv_line") or a.get("action") or "epic completed").strip()[:90]
        events.append({"type": "epic", "ts": a.get("iso") or a.get("ts"), "label": line})
    events.sort(key=lambda ev: str(ev.get("ts") or ""), reverse=True)

    # last activity across heartbeat / wallet / relay / achievements (real timestamps)
    cands = []
    if hb.get("status") == "ok":
        for rec in (hb.get("live") or []) + (hb.get("idle") or []) + (hb.get("silent") or []):
            cands.append(rec.get("last_ts"))
    t = _iso_to_ts(w.get("last_ts"))
    if t:
        cands.append(t)
    for m in (relay.get("messages") or []):
        t = _iso_to_ts(m.get("ts"))
        if t:
            cands.append(t)
    for r in (ach.get("rows") or []):
        t = _iso_to_ts(r.get("iso"))
        if t:
            cands.append(t)
    last_ts = max([c for c in cands if isinstance(c, (int, float))], default=None)
    last_activity = (datetime.datetime.fromtimestamp(last_ts, datetime.UTC)
                     .strftime("%Y-%m-%d %H:%MZ") if last_ts else None)

    # realtime telemetry + velocity (safe aggregates only)
    try:
        import json as _json
        _t = _json.load(open("/srv/bricks/orchestrator/fleet-realtime.json"))
        _ovh, _q, _b, _ban = _t.get("ovh", {}), _t.get("queue", {}), _t.get("burn_ovh", {}), _t.get("bananas", {})
    except Exception:
        _ovh = _q = _b = _ban = {}
    _rt = {
        "ts": int(time.time()),
        "load": _ovh.get("load"), "threads": _ovh.get("threads"),
        "mem_used_mb": (_ovh.get("mem") or {}).get("used_mb"),
        "mem_total_mb": (_ovh.get("mem") or {}).get("total_mb"),
        "cpu": _ovh.get("cpu"),
        "queue_pending": _q.get("pending"), "queue_total": _q.get("total"),
        "burn_calls_1h": _b.get("last_1h"), "burn_tokens_1h": _b.get("tokens_1h"),
        "bananas": _ban.get("total"), "mints": _ban.get("mints"),
        "heartbeats_1h": _t.get("bricks_heartbeating_1h"),
    }
    return {
        "realtime": _rt,
        "generated_at": now_iso(),
        "brand": {"name": "BAWES", "tagline": "People and AI Living Together", "url": "bawes.net"},
        "bricks_total": reg.get("registered_count") if reg.get("status") == "ok" else None,
        "bricks_active": hb.get("live_count") if hb.get("status") == "ok" else None,
        "bricks_known": hb.get("known_count") if hb.get("status") == "ok" else None,
        "bricks_verified": reg.get("verified_count") if reg.get("status") == "ok" else None,
        "earns_total": w.get("earned_bananas"),
        "earns_clean": w.get("clean_earned_bananas"),
        "spend_free": {"calls": burn.get("free", {}).get("calls"),
                       "pct": burn.get("free", {}).get("pct")},
        "spend_paid": {"calls": burn.get("paid", {}).get("calls"),
                       "pct": burn.get("paid", {}).get("pct")},
        "burn_usd_per_day": burn.get("per_day"),
        "prs_7d": prs_7d,
        "flags": eco.get("bottlenecks", {}).get("total"),
        "spawns": eco.get("spawns", {}).get("total"),
        "achievements_count": ach.get("count"),
        "last_events": events[:8],
        "last_activity": last_activity,
        "note": "public aggregates — safe by construction (no keys, IPs, wallet contents, or per-brick economics)",
    }


# ================================================================
# THE NET — per-brick realtime telemetry (CPU/RAM) + lineage graph
# ================================================================
# Collector: a daemon thread inside this process. Every 30s it reads `ps` +
# `free -m`, maps fleet processes to registered bricks where possible
# (--brick-id args, known script paths), and appends one row per brick/proc
# to telemetry.jsonl. The latest snapshot is cached in memory so /api/network
# serves it instantly (no ps parsing per request). Nothing is invented: bricks
# with no running process get cpu/ram null (frontend shows "—").
TELEMETRY_INTERVAL = 30

# script/arg patterns -> registered brick ids (real fleet processes on the box)
PROC_BRICK_PATTERNS = [
    ("orchestrator.py", "worker-001"),
    ("a2a_server.py", "ovh-server-001"),
    ("token_router.py", "router-001"),
    ("bridge.py", "bridge-001"),
    ("heartbeat.py", "ovh-server-001"),
]
FLEET_MARKERS = ("/srv/bricks", "/srv/door", "/srv/build", "orchestrator", "headless_worker",
                 "ox_worker", "bridge", "token_router", "a2a_server", "heartbeat",
                 "burn_server", "agi_self_loop", "hearth", "door_", "earn_loop")

telemetry_lock = threading.Lock()
telemetry_cache = {"ts": 0.0, "out": {"host": None, "procs": [], "by_brick": {}}}
_host_stat_prev = {"total": None, "idle": None}
_lineage_cache = {"ts": 0.0, "out": None}
_known_ids_cache = {"ts": 0.0, "ids": set()}


def _known_brick_ids():
    """Set of registered brick ids (refreshed from the registry every 2 min)."""
    now = time.time()
    if now - _known_ids_cache["ts"] > 120:
        lin = _lineage()
        _known_ids_cache.update(ts=now, ids=set(lin["latest"].keys()))
    return _known_ids_cache["ids"]


def _proc_name(args):
    """Human name for a process: basename of the script token, else basename
    of the executable (never the last argv token — that can be a port/pid)."""
    for tok in args.split():
        if ".py" in tok:
            return os.path.basename(tok)
    parts = args.split()
    return os.path.basename(parts[0]) if parts else "?"


def _proc_to_brick(cmd):
    """Map a process command line to a registered brick id where possible."""
    m = re.search(r"--brick-id[= ](\S+)", cmd)
    if m:
        return m.group(1)
    c = cmd.lower()
    for pat, bid in PROC_BRICK_PATTERNS:
        if pat in c:
            return bid
    # generic: /srv/bricks/<brick-id>/<script>.py — only when the dir is a
    # REGISTERED brick id (orchestrator/ is a dir, not a brick)
    m = re.search(r"/srv/bricks/([^/\s]+)/", c)
    if m and m.group(1) in _known_brick_ids():
        return m.group(1)
    return None


def _host_cpu_pct():
    """Machine-wide CPU% from /proc/stat deltas (percent of all cores)."""
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()[1:]
        vals = [int(x) for x in parts]
        total = sum(vals)
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        prev = _host_stat_prev
        if prev["total"] is not None and total > prev["total"]:
            dtotal = total - prev["total"]
            didle = idle - prev["idle"]
            pct = round(100.0 * (1.0 - didle / dtotal), 1) if dtotal else 0.0
        else:
            pct = None
        _host_stat_prev.update(total=total, idle=idle)
        return pct
    except Exception:
        return None


def _collect_telemetry_once():
    """One pass: ps + free -m -> {host, procs, by_brick}. Never raises."""
    out = {"host": None, "procs": [], "by_brick": {}}
    try:
        ps = subprocess.check_output(["ps", "-eo", "pid,pcpu,rss,args"], text=True, timeout=20)
    except Exception:
        return out
    by_brick = {}
    procs = []
    for line in ps.splitlines()[1:]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, pcpu, rss, args = parts
        if not any(k in args for k in FLEET_MARKERS):
            continue
        if "telemetry.py" in args or "fleet-dashboard/dashboard.py" in args:
            continue  # the collector itself + the dashboard are not bricks
        name = _proc_name(args)
        if name in ("sh", "bash", "dash", "zsh"):
            continue  # shell wrappers around fleet scripts are noise, not bricks
        try:
            cpu = float(pcpu)
            ram_mb = round(float(rss) / 1024.0, 1)
        except (TypeError, ValueError):
            continue
        bid = _proc_to_brick(args)
        if bid:
            b = by_brick.setdefault(bid, {"cpu": 0.0, "ram_mb": 0.0, "procs": []})
            b["cpu"] = round(b["cpu"] + cpu, 1)
            b["ram_mb"] = round(b["ram_mb"] + ram_mb, 1)
            b["procs"].append(name)
        else:
            procs.append({"proc": name, "cpu": cpu, "ram_mb": ram_mb})
    try:
        fm = subprocess.check_output(["free", "-m"], text=True, timeout=10)
        mem = {}
        for ln in fm.splitlines():
            if ln.startswith("Mem:"):
                p = ln.split()
                mem = {"total_mb": int(p[1]), "used_mb": int(p[2]), "free_mb": int(p[3])}
    except Exception:
        mem = {}
    out["host"] = {"cpu_pct": _host_cpu_pct(), "ram_mb": mem.get("used_mb"),
                   "total_mb": mem.get("total_mb"), "free_mb": mem.get("free_mb")}
    out["procs"] = sorted(procs, key=lambda p: -p["cpu"])[:40]
    out["by_brick"] = by_brick
    return out


def _lineage():
    """Registry lineage: latest row per brick + parent map + children map.
    Parents come from registry parent_brick_id/spawn_of (real rows) and are
    completed with spawns.jsonl (new_brick_id -> replaces). 60s cache."""
    now = time.time()
    if _lineage_cache["out"] is not None and now - _lineage_cache["ts"] < 60:
        return _lineage_cache["out"]
    reg_rows = [r for r in (read_jsonl(REGISTRY) or []) if isinstance(r, dict)]
    spawn_rows = [r for r in (read_jsonl(SPAWNS) or []) if isinstance(r, dict)]
    latest = {}
    for r in reg_rows:
        bid = r.get("brick_id")
        if bid:
            latest[str(bid)] = r
    parent = {}
    for bid, row in latest.items():
        p = row.get("parent_brick_id") or row.get("spawn_of")
        if p:
            parent[bid] = str(p)
    for s in spawn_rows:
        nb, rep = s.get("new_brick_id"), s.get("replaces")
        if nb and rep and str(nb) not in parent:
            parent[str(nb)] = str(rep)
    children = {}
    for bid, p in parent.items():
        children.setdefault(p, []).append(bid)
    out = {"latest": latest, "parent": parent, "children": children}
    _lineage_cache.update(ts=now, out=out)
    return out


def _telemetry_loop():
    """Daemon thread: collect every 30s, cache snapshot, append rows to
    telemetry.jsonl (append-only JSONL, one row per brick/proc/host)."""
    while True:
        try:
            snap = _collect_telemetry_once()
            with telemetry_lock:
                telemetry_cache["ts"] = time.time()
                telemetry_cache["out"] = snap
            lin = _lineage()
            rows = []
            ts = now_iso()
            if snap["host"]:
                rows.append({"ts": ts, "proc": "host", "cpu": snap["host"].get("cpu_pct"),
                             "ram_mb": snap["host"].get("ram_mb")})
            for bid, b in snap["by_brick"].items():
                rows.append({"ts": ts, "brick_id": bid, "cpu": b["cpu"], "ram_mb": b["ram_mb"],
                             "children_count": len(lin["children"].get(bid, []))})
            for p in snap["procs"]:
                rows.append({"ts": ts, "proc": p["proc"], "cpu": p["cpu"], "ram_mb": p["ram_mb"]})
            if rows:
                with open(TELEMETRY, "a") as f:
                    for r in rows:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except Exception:
            pass
        time.sleep(TELEMETRY_INTERVAL)


def _node_status(row):
    st = str(row.get("status") or "").lower()
    if row.get("kind") == "retired" or st == "retired":
        return "retired"
    if st == "retiring":
        return "retiring"
    act = row.get("active")
    if act is True or str(act).lower() == "true" or st in ("live", "active"):
        return "active"
    if row.get("quality") == "verified":
        return "verified"
    if st == "parked":
        return "parked"
    return "registered"


def _wallet_earns_by_brick(wal_rows):
    out = {}
    for r in wal_rows:
        if (r.get("kind") or r.get("type")) != "earn":
            continue
        bid = r.get("brick_id")
        if not bid:
            continue
        try:
            b = float(r.get("bananas", 0) or 0)
        except (TypeError, ValueError):
            b = 0.0
        e = out.setdefault(str(bid), {"earns": 0.0, "clean": 0.0})
        e["earns"] = round(e["earns"] + b, 2)
        if not r.get("contested"):
            e["clean"] = round(e["clean"] + b, 2)
    return out


def _last_activity_per_brick(latest, wal_rows, hb):
    """Latest real timestamp per brick across registry / wallet / heartbeats."""
    la = {}
    for bid, row in latest.items():
        t = _iso_to_ts(row.get("ts"))
        if t:
            la[bid] = t
    for r in wal_rows:
        bid = r.get("brick_id")
        t = _iso_to_ts(r.get("ts"))
        if bid and t and t > la.get(str(bid), 0):
            la[str(bid)] = t
    if hb.get("status") == "ok":
        for rec in (hb.get("live") or []) + (hb.get("idle") or []) + (hb.get("silent") or []):
            bid = rec.get("id")
            t = rec.get("last_ts")
            if bid and t and t > la.get(str(bid), 0):
                la[str(bid)] = t
    return la


def network_data():
    """THE NET — every registered brick as a node (lineage from registry
    parent_brick_id/spawn_of + spawns.jsonl), edges parent->child, plus live
    per-brick CPU/RAM from the in-process telemetry collector (real ps/free).
    Auth-gated (same session gate as /api/ecosystem). Per-brick economics are
    NOT exposed — only wallet earn totals already shown fleet-wide."""
    lin = _lineage()
    latest, parent, children = lin["latest"], lin["parent"], lin["children"]
    wal_rows = [r for r in (read_jsonl(WALLET) or []) if isinstance(r, dict)]
    hb = heartbeat_data()
    earns = _wallet_earns_by_brick(wal_rows)
    last_act = _last_activity_per_brick(latest, wal_rows, hb)

    with telemetry_lock:
        tel = dict(telemetry_cache["out"])
        tel_ts = telemetry_cache["ts"]

    nodes = []
    counts = {"active": 0, "verified": 0, "registered": 0, "parked": 0,
              "retiring": 0, "retired": 0, "with_telemetry": 0}
    for bid, row in latest.items():
        st = _node_status(row)
        counts[st] = counts.get(st, 0) + 1
        tb = tel.get("by_brick", {}).get(bid)
        if tb:
            counts["with_telemetry"] += 1
        e = earns.get(bid, {})
        nodes.append({
            "id": bid,
            "status": st,
            "quality": row.get("quality"),
            "role": row.get("role"),
            "origin": row.get("origin"),
            "skills": row.get("skills") or [],
            "parent": parent.get(bid),
            "children": sorted(children.get(bid, [])),
            "cpu": tb.get("cpu") if tb else None,
            "ram_mb": tb.get("ram_mb") if tb else None,
            "procs": (tb.get("procs") or []) if tb else [],
            "last_activity": last_act.get(bid),
            "earns": e.get("earns", 0.0),
            "earns_clean": e.get("clean", 0.0),
            "registry_ts": _iso_to_ts(row.get("ts")),
        })
    nodes.sort(key=lambda n: (n["status"] != "active", n["status"] != "verified", n["id"]))
    edges = [{"from": p, "to": c} for p, cl in children.items() for c in cl]
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "counts": counts,
        "nodes": nodes,
        "edges": edges,
        "telemetry": {
            "host": tel.get("host"),
            "procs": tel.get("procs") or [],
            "collected_at": (datetime.datetime.fromtimestamp(tel_ts, datetime.UTC).isoformat()
                             if tel_ts else None),
            "stale_sec": int(time.time() - tel_ts) if tel_ts else None,
            "note": "cpu/ram read from live ps/free on this box every 30s and mapped to bricks "
                    "by --brick-id / script path. Bricks with no process running show —.",
        },
        "note": "nodes = registered bricks (latest registry row wins). edges = spawn lineage from "
                "parent_brick_id/spawn_of in registry.jsonl + spawns.jsonl. cpu/ram are real ps "
                "values for that brick's processes; per-brick economics are not exposed.",
    }


# ---------------------------------------------------------------- portfolio + invest leg + time machine (v10, 2026-08-25)
def _wallet_append(row):
    """Append one row to wallet.jsonl with a cross-process flock (the earn-loop appends too)."""
    with WALLET_LOCK:
        try:
            fd = os.open(WALLET, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "a") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f, fcntl.LOCK_UN)
            return True
        except OSError as e:
            return str(e)


def invest_rows_raw():
    rows = read_jsonl(WALLET) or []
    return [r for r in rows if isinstance(r, dict) and r.get("kind") == "invest"]


def derived_balance(person, person_id=None):
    """F-19 derived balance: Σ earn + Σ credit + Σ founder-seed + Σ dock(neg) − Σ invest(pos).
    Invest rows are stored POSITIVE (a debit); reversal rows carry negative bananas and add back."""
    bal = 0.0
    for r in (read_jsonl(WALLET) or []):
        if not isinstance(r, dict):
            continue
        if r.get("person") != person and not (person_id and r.get("person_id") == person_id):
            continue
        k = r.get("kind")
        if k not in ("earn", "credit", "founder-seed", "dock", "invest"):
            continue
        try:
            b = float(r.get("bananas", 0) or 0)
        except (TypeError, ValueError):
            continue
        if k == "invest":
            bal -= b
        else:
            bal += b
    return round(bal, 2)


def projects_data():
    """Investable projects ledger (append-only, latest row per project_id wins).
    funded_bananas is DERIVED from wallet kind=invest rows (F-19) — never stored in the row."""
    rows = read_jsonl(PROJECTS)
    if rows is None:
        return {"status": "missing", "projects": [], "count": 0, "file": PROJECTS,
                "invest_rows": 0, "note": "projects.jsonl not created yet — epics become investable when seeded"}
    by_id = {}
    for r in rows:
        if isinstance(r, dict) and r.get("project_id"):
            by_id[str(r["project_id"])] = r
    invests = invest_rows_raw()
    funded, backers = {}, {}
    for inv in invests:
        pid = inv.get("project_id")
        if not pid:
            continue
        try:
            b = float(inv.get("bananas", 0) or 0)
        except (TypeError, ValueError):
            b = 0.0
        funded[str(pid)] = funded.get(str(pid), 0.0) + b
        if b > 0 and inv.get("person"):
            backers.setdefault(str(pid), set()).add(inv["person"])
    out = []
    for pid, p in by_id.items():
        p2 = dict(p)
        p2["funded_bananas"] = round(funded.get(pid, 0.0), 1)
        p2["investor_count"] = len(backers.get(pid, set()))
        out.append(p2)
    out.sort(key=lambda p: p.get("project_id") or "")
    return {"status": "ok" if by_id else "empty", "projects": out, "count": len(out),
            "file": PROJECTS, "invest_rows": len(invests),
            "terms_sha": INVEST_TERMS_SHA, "terms": INVEST_TERMS_V1,
            "note": "project accounts are derived per F-19: funded = Σ invest rows (reversals are negative rows)"}


def tokens_data():
    """BYOK / token visibility — per-key NAMES + MASKS only. Values live in /srv/vault (0600),
    never read here, never in git, never in chat. Usage = real router ledger calls by lane;
    work done = wallet earns + achievements per person."""
    keys = []
    try:
        for r in (read_jsonl(VAULT_STORE) or []):
            if isinstance(r, dict) and r.get("kind") == "key" and r.get("service"):
                keys.append({
                    "provider": str(r.get("service")),
                    "label": str(r.get("person") or "?"),
                    "masked": str(r.get("key") or "")[:16],
                    "key_sha": str(r.get("key_sha") or "")[:8],
                    "custody": str(r.get("custody") or "")[:8],
                    "ts": r.get("ts"),
                })
    except Exception:
        keys = []
    latest = {}
    for k in keys:
        latest[(k["provider"], k["label"])] = k
    keys = [latest[k] for k in sorted(latest)]
    tok_files = []
    try:
        tok_files = sorted(n for n in os.listdir(FLEET_TOKENS_DIR) if not n.startswith("."))
    except OSError:
        pass
    ingest_persons = []
    try:
        d = json.load(open(INGEST_TOKENS))
        if isinstance(d, dict):
            ingest_persons = sorted(d.keys())
    except Exception:
        pass
    # usage: real router ledger calls per lane (all-time)
    lane_usage = {}
    try:
        burn = burn_data()
        for group in ("free", "paid"):
            for rec in (burn.get(group, {}) or {}).get("lanes", []):
                lane_usage[rec["lane"]] = {"calls": rec.get("calls", 0), "cost": round(rec.get("cost", 0.0), 4)}
    except Exception:
        pass
    # work done: wallet earns per person + achievements per owner
    work = {}
    for r in (read_jsonl(WALLET) or []):
        if not isinstance(r, dict) or r.get("kind") != "earn":
            continue
        who = r.get("person_id") or r.get("person") or r.get("brick_id") or "?"
        try:
            b = float(r.get("bananas", 0) or 0)
        except (TypeError, ValueError):
            b = 0.0
        e = work.setdefault(str(who), {"earned": 0.0, "achievements": 0})
        e["earned"] += b
    for r in (read_jsonl(ACHIEVEMENTS) or []):
        if not isinstance(r, dict):
            continue
        who = r.get("owner") or "?"
        e = work.setdefault(str(who), {"earned": 0.0, "achievements": 0})
        e["achievements"] += 1
    return {
        "keys": keys,
        "token_files": tok_files,
        "ingest_persons": ingest_persons,
        "lane_usage": lane_usage,
        "work_done": {k: {"earned": round(v["earned"], 1), "achievements": v["achievements"]}
                      for k, v in sorted(work.items())},
        "note": "names and masks only — key values live in /srv/vault (0600), never in git, never in chat. Usage = real router ledger calls; work = wallet earns + achievements.",
    }


def portfolio_data(user):
    """/api/portfolio — YOUR investments, YOUR bricks, fleet accomplishments, token visibility.
    'your' = session username matched against wallet invest rows (person) and wallet person_ids /
    brick ids carrying the username (the registry itself has no owner field). Real reads only."""
    username = (user or {}).get("username")
    invests = invest_rows_raw()
    # this user's person ids: wallet rows whose person matches, or whose brick_id carries the username
    person_ids = set()
    for r in (read_jsonl(WALLET) or []):
        if not isinstance(r, dict):
            continue
        if r.get("person") == username:
            if r.get("person_id"):
                person_ids.add(str(r["person_id"]))
        bid = r.get("brick_id")
        if bid and username and username.lower() in str(bid).lower():
            if r.get("person_id"):
                person_ids.add(str(r["person_id"]))
            if r.get("person"):
                person_ids.add(str(r["person"]))
    my_invests = [i for i in invests
                  if i.get("person") == username or (i.get("person_id") and i.get("person_id") in person_ids)]
    # pending invest proposals (approval cards carrying an invest payload) — WRITE only via approvals
    pend = []
    for c in approvals_data().get("cards", []):
        if c.get("invest") and c.get("status") == "PENDING":
            pend.append({"id": c.get("id"), "title": c.get("title"),
                         "proposer": c.get("proposer"), "invest": c.get("invest"),
                         "created_ts": c.get("created_ts")})
    # my bricks: registry latest rows + wallet brick_ids containing the username
    reg = read_jsonl(REGISTRY) or []
    latest_reg = {}
    for r in reg:
        if isinstance(r, dict) and r.get("brick_id"):
            latest_reg[str(r["brick_id"])] = r
    wallet_bricks = {}
    for r in (read_jsonl(WALLET) or []):
        if not isinstance(r, dict) or not r.get("brick_id"):
            continue
        bid = str(r["brick_id"])
        wb = wallet_bricks.setdefault(bid, {"earned": 0.0, "rows": 0})
        wb["rows"] += 1
        if r.get("kind") == "earn":
            try:
                wb["earned"] += float(r.get("bananas", 0) or 0)
            except (TypeError, ValueError):
                pass
    mine, seen = [], set()
    ach_rows = achievements_data().get("rows") or []
    for bid in list(latest_reg.keys()) + list(wallet_bricks.keys()):
        if bid in seen or not (username and username.lower() in bid.lower()):
            continue
        seen.add(bid)
        regr = latest_reg.get(bid, {})
        wb = wallet_bricks.get(bid, {})
        mine.append({
            "brick_id": bid,
            "status": regr.get("quality") or regr.get("status") or "registered",
            "role": regr.get("role"),
            "skills": regr.get("skills") or [],
            "earns": round(wb.get("earned", 0.0), 1),
            "wallet_rows": wb.get("rows", 0),
            "accomplishments": [a for a in ach_rows if (a.get("owner") or "") == bid],
            "registry_ts": regr.get("ts"),
        })
    mine.sort(key=lambda b: b["brick_id"])
    # wallet snapshot for this user (F-19 derived)
    wsum = {"earned": 0.0, "credits": 0.0, "seeds": 0.0, "docks": 0.0, "invested": 0.0}
    for r in (read_jsonl(WALLET) or []):
        if not isinstance(r, dict):
            continue
        if r.get("person") != username and not (r.get("person_id") and r.get("person_id") in person_ids):
            continue
        k = r.get("kind")
        try:
            b = float(r.get("bananas", 0) or 0)
        except (TypeError, ValueError):
            continue
        if k == "earn":
            wsum["earned"] += b
        elif k == "credit":
            wsum["credits"] += b
        elif k == "founder-seed":
            wsum["seeds"] += b
        elif k == "dock":
            wsum["docks"] += b
        elif k == "invest":
            wsum["invested"] += b
    bal = round(wsum["earned"] + wsum["credits"] + wsum["seeds"] + wsum["docks"] - wsum["invested"], 2)
    return {
        "user": username,
        "wallet": {"derived_balance": bal,
                   "earned": round(wsum["earned"], 1), "credits": round(wsum["credits"], 1),
                   "seeds": round(wsum["seeds"], 1), "docks": round(wsum["docks"], 1),
                   "invested": round(wsum["invested"], 1),
                   "person_ids": sorted(person_ids),
                   "note": "F-19 derived: earns+credits+seeds+docks−invests — invest rows are real debits"},
        "investments": my_invests,
        "pending_invests": pend,
        "my_bricks": mine,
        "fleet_accomplishments": achievements_data(),
        "tokens": tokens_data(),
        "projects": projects_data(),
        "note": "your portfolio = real ledger reads matched to your session user; bricks match by id containing your username (registry has no owner field)",
    }


def _validate_invest(card):
    """Validate an invest payload before khalid's sign lands. Returns (ok, err).
    Positive bananas = funding an invest; negative bananas = a REVERSAL (DA rule:
    corrections as reversals — a reversal may only claw back what was actually invested)."""
    inv = card.get("invest") or {}
    person = inv.get("person") or card.get("proposer")
    project_id = inv.get("project_id")
    try:
        bananas = float(inv.get("bananas", 0) or 0)
    except (TypeError, ValueError):
        bananas = 0.0
    if not person:
        return False, "invest card missing person"
    if not project_id:
        return False, "invest card missing project_id"
    if bananas == 0:
        return False, "invest amount must be non-zero"
    proj = next((p for p in projects_data().get("projects", []) if p.get("project_id") == project_id), None)
    if proj is None:
        return False, f"project {project_id} not in projects.jsonl — seed it before investing"
    if bananas < 0:
        # reversal: may only claw back what this person actually has net-invested in the project
        net = 0.0
        for i in invest_rows_raw():
            if i.get("person") != person or i.get("project_id") != project_id:
                continue
            try:
                net += float(i.get("bananas", 0) or 0)
            except (TypeError, ValueError):
                pass
        if net + bananas < -1e-9:
            return False, (f"reversal declined — {person} has net-invested {net:g}🍌 in {project_id}, "
                           f"below the {abs(bananas):g}🍌 reversal. Corrections are reversals of what exists.")
        return True, None
    bal = derived_balance(person, inv.get("person_id"))
    if bal + 1e-9 < bananas:
        return False, (f"invest declined — {person}'s derived balance is {bal:g}🍌, "
                       f"below the {bananas:g}🍌 invest. Invest rows are real debits (F-19).")
    return True, None


def _write_invest_row(card, approved_row):
    """Append the kind=invest wallet row after khalid approves an invest card (real debit)."""
    inv = card.get("invest") or {}
    try:
        bananas = round(float(inv.get("bananas", 0) or 0), 2)
    except (TypeError, ValueError):
        bananas = 0.0
    row = {
        "kind": "invest",
        "person": inv.get("person") or card.get("proposer"),
        "person_id": inv.get("person_id"),
        "brick_id": inv.get("brick_id"),
        "project_id": inv.get("project_id"),
        "bananas": bananas,
        "terms_sha": inv.get("terms_sha") or INVEST_TERMS_SHA,
        "card_id": card.get("id"),
        "ts": time.time(),
        "status": "funded",
        "source": "fleet-dashboard /approvals (khalid sign)",
    }
    err = _wallet_append(row)
    if err is not True:
        return {"written": False, "error": f"wallet append failed: {err}"}
    return {"written": True, "row": row}


# ===================================================================== TIME ENGINE
# The Time Engine panel (/panel/time-engine) — khalid's "Time Machine" made real:
# per-brick VIB/BRK velocity bars, Switcher states (mode from burn receipts), and
# the public myth ledger (bananas / mints / ROI / artifacts). Canon vocabulary:
# VIB (Viral Influence Burst) = Butterfly point (spread/resonance); BRK (Build Rate
# Kinetics) = Monkey point (tasks cleared, systems built); states = butterfly |
# monkey | switcher (Yin-Yang). ADDITIVE + READ-ONLY: sources are brick-ledger.json
# and burn-receipt files carrying brk/vib/mode. Honest by construction — bricks
# with no instrumented receipts show zero bars, never invented numbers.

TE_LEDGER = "/srv/bricks/orchestrator/brick-ledger.json"
TE_RECEIPTS = [
    "/srv/bricks/orchestrator/receipts-ovh.jsonl",
    "/srv/bricks/orchestrator/receipts-control.jsonl",
]
TE_MODES = ("butterfly", "monkey", "switcher")
te_cache = {"ts": 0.0, "out": None}
TE_LOCK = threading.Lock()


def _te_mtime_iso(path):
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(path),
                                               datetime.UTC).isoformat()
    except OSError:
        return None


def _te_receipt_rows():
    """Every dict row from every receipt source, tagged with its source file."""
    rows = []
    for src in TE_RECEIPTS:
        for r in (read_jsonl(src) or []):
            if isinstance(r, dict):
                r2 = dict(r)
                r2["_src"] = os.path.basename(src)
                rows.append(r2)
    return rows


def timeengine_data():
    """TIME ENGINE payload — engine totals (BRK/VIB), Switcher mode tally from
    receipts, and myth-ledger rows from brick-ledger.json. Cached 30s."""
    with TE_LOCK:  # keep the cache write race-free
        if time.time() - te_cache["ts"] < 30 and te_cache["out"] is not None:
            return te_cache["out"]

    ledger = {}
    try:
        with open(TE_LEDGER) as f:
            ledger = json.load(f)
    except Exception:
        ledger = {}
    per = ledger.get("per_brick", {}) if isinstance(ledger, dict) else {}
    if not isinstance(per, dict):
        per = {}

    rows = _te_receipt_rows()
    modes = {m: 0 for m in TE_MODES}
    other_modes = {}
    latest_mode_ts = {}
    vib_brk = {}          # identity (brick_id/claimer) -> {"brk","vib","rows"}
    fleet_brk = fleet_vib = inst_rows = 0

    for r in rows:
        m = str(r.get("mode") or "").strip().lower()
        if m:
            if m in modes:
                modes[m] += 1
            else:
                other_modes[m] = other_modes.get(m, 0) + 1
            try:
                t = float(r.get("ts") or 0)
                if t > latest_mode_ts.get(m, 0):
                    latest_mode_ts[m] = t
            except (TypeError, ValueError):
                pass
        if ("brk" in r) or ("vib" in r):
            inst_rows += 1

            def _num(k, _r=r):
                try:
                    return max(0, int(_r.get(k) or 0))
                except (TypeError, ValueError):
                    return 0

            b, v = _num("brk"), _num("vib")
            fleet_brk += b
            fleet_vib += v
            who = str(r.get("brick_id") or r.get("claimer") or r.get("brick") or "").strip()
            if who:
                d = vib_brk.setdefault(who.lower(), {"brk": 0, "vib": 0, "rows": 0})
                d["brk"] += b
                d["vib"] += v
                d["rows"] += 1

    bricks = []
    lower_ledger_ids = {str(k).lower(): str(k) for k in per}
    for bid, s in sorted(per.items()):
        if not isinstance(s, dict):
            continue
        vb = vib_brk.get(str(bid).lower())
        acc = [str(a) for a in (s.get("accomplishments") or [])]
        hb = s.get("last_heartbeat")
        bricks.append({
            "brick": bid,
            "role": s.get("role"),
            "live": bool(s.get("live")),
            "last_heartbeat": hb,
            "threads": s.get("capacity_threads"),
            "bananas": s.get("bananas_earned", 0),
            "mints": s.get("mints", 0),
            "roi": s.get("roi", 0),
            "artifacts": acc[:12],
            "artifacts_count": len(acc),
            "brk": (vb or {}).get("brk", 0),
            "vib": (vb or {}).get("vib", 0),
        })
    # identities seen in instrumented receipts that don't map to a ledger brick
    orphan_ids = sorted(k for k in vib_brk if k not in lower_ledger_ids)

    out = {
        "generated_at": now_iso(),
        "ledger_generated": ledger.get("generated") if isinstance(ledger, dict) else None,
        "fleet_totals": ledger.get("fleet", {}) if isinstance(ledger, dict) else {},
        "engine": {"brk": fleet_brk, "vib": fleet_vib,
                   "receipt_rows": len(rows), "instrumented_rows": inst_rows},
        "switcher": {"modes": modes, "other_modes": other_modes,
                     "latest_ts": {m: latest_mode_ts[m] for m in latest_mode_ts}},
        "bricks": bricks,
        "attributed_identities": sorted(vib_brk.keys()),
        "orphan_identities": orphan_ids,
        "sources": [
            {"file": os.path.basename(p), "mtime_iso": _te_mtime_iso(p)}
            for p in TE_RECEIPTS + [TE_LEDGER]
        ],
        "note": ("VIB = Butterfly point (spread/resonance). BRK = Monkey point "
                 "(tasks cleared, systems built). Bars light up as burn receipts "
                 "carry brk/vib/mode + brick_id — zeros mean not-yet-instrumented, "
                 "never zero work."),
    }
    with TE_LOCK:
        te_cache["ts"] = time.time()
        te_cache["out"] = out
    return out


def timeengine_page(data):
    """Standalone dark gold/teal panel. Fresh payload embedded server-side;
    JS re-polls /api/time-engine every 20s and re-renders."""
    payload_js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BAWES &middot; Time Engine</title>
<style>
:root{--gold:#f5b942;--gold2:#ffd97a;--teal:#3dd6a4;--bg:#04060d;--bg2:#0a0e18;
--card:#10141c;--card2:#161d2b;--line:#263041;--txt:#e8ecf4;--dim:#8b94a7;
--mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);
font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
line-height:1.5;padding:26px 20px 70px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto}
header{display:flex;align-items:center;gap:14px}
.mark{width:40px;height:40px;border-radius:10px;flex-shrink:0;
background:radial-gradient(circle at 30% 25%,#2a2410,#14100a 70%);
border:1px solid #4d3d14;display:flex;align-items:center;justify-content:center;
font-weight:800;color:var(--gold);font-size:15px;
box-shadow:inset 0 0 18px rgba(245,185,66,.14)}
h1{font-size:21px;letter-spacing:.5px;font-weight:800}
h1 b{color:var(--gold)}
.updated{margin-left:auto;font-size:11px;color:var(--dim);font-family:var(--mono)}
.quote{color:var(--dim);font-size:12.5px;font-style:italic;margin:8px 0 22px}
.statrow{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:10px 16px;min-width:132px;flex:1}
.stat .v{font-family:var(--mono);font-size:20px;font-weight:700;color:var(--gold)}
.stat.t .v{color:var(--teal)}
.stat .k{font-size:10.5px;color:var(--dim);text-transform:uppercase;letter-spacing:1.2px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:16px 18px;margin-bottom:18px}
.card h2{font-size:12.5px;color:var(--gold);letter-spacing:2px;
text-transform:uppercase;margin-bottom:12px;font-weight:700}
.card h2 span{color:var(--dim);letter-spacing:.3px;text-transform:none;font-weight:400}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.chip{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);
border-radius:999px;padding:5px 13px;font-size:12.5px;background:var(--card2)}
.chip .n{font-family:var(--mono);font-weight:700}
.chip.butterfly{border-color:rgba(61,214,164,.45)}.chip.butterfly .n{color:var(--teal)}
.chip.monkey{border-color:rgba(245,185,66,.45)}.chip.monkey .n{color:var(--gold)}
.chip.switcher{border-color:rgba(232,236,244,.35)}.chip.switcher .n{color:var(--txt)}
.yinyang{height:10px;border-radius:999px;overflow:hidden;display:flex;
border:1px solid var(--line);background:var(--bg2)}
.yinyang i{display:block;height:100%}
.yinyang .yb{background:var(--teal)}.yinyang .ym{background:var(--gold)}
.yinyang .ys{background:#8b94a7}
.yylabels{display:flex;justify-content:space-between;font-size:10.5px;
color:var(--dim);margin-top:5px;font-family:var(--mono)}
.brickrow{padding:11px 0;border-bottom:1px solid rgba(38,48,65,.5)}
.brickrow:last-child{border-bottom:none}
.brickhead{display:flex;align-items:center;gap:9px;margin-bottom:6px;flex-wrap:wrap}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dot.live{background:var(--teal);box-shadow:0 0 8px rgba(61,214,164,.8)}
.dot.parked{background:#4a5568}
.bid{font-family:var(--mono);font-weight:700;font-size:13px}
.rolechip{font-size:10.5px;color:var(--dim);border:1px solid var(--line);
border-radius:999px;padding:1px 9px}
.modechip{font-size:10.5px;border-radius:999px;padding:1px 9px;border:1px solid var(--line)}
.modechip.butterfly{color:var(--teal);border-color:rgba(61,214,164,.4)}
.modechip.monkey{color:var(--gold);border-color:rgba(245,185,66,.4)}
.thr{margin-left:auto;font-size:11px;color:var(--dim);font-family:var(--mono)}
.barline{display:flex;align-items:center;gap:10px;margin:4px 0}
.blab{width:32px;font-size:10px;font-family:var(--mono);letter-spacing:1px;flex-shrink:0}
.blab.brk{color:var(--gold)}.blab.vib{color:var(--teal)}
.track{flex:1;height:12px;background:var(--bg2);border:1px solid var(--line);
border-radius:999px;overflow:hidden}
.fill{height:100%;border-radius:999px;transition:width .5s ease}
.fill.brk{background:linear-gradient(90deg,rgba(245,185,66,.25),var(--gold))}
.fill.vib{background:linear-gradient(90deg,rgba(61,214,164,.25),var(--teal))}
.bnum{width:44px;text-align:right;font-family:var(--mono);font-size:11.5px;
color:var(--dim);flex-shrink:0}
table.myth{width:100%;border-collapse:collapse;font-size:13px}
.myth th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:1.2px;
color:var(--dim);padding:8px 10px;border-bottom:1px solid var(--line);font-weight:600}
.myth td{padding:9px 10px;border-bottom:1px solid rgba(38,48,65,.45);vertical-align:top}
.myth tr:last-child td{border-bottom:none}
.myth td.num{font-family:var(--mono);color:var(--gold);white-space:nowrap}
.myth td.num.t{color:var(--teal)}
.myth .bid2{font-family:var(--mono);font-weight:700;font-size:12.5px}
.myth .rl{font-size:11px;color:var(--dim)}
.arts{color:var(--dim);font-size:11.5px;line-height:1.6}
.arts span{display:inline-block;border:1px solid var(--line);border-radius:7px;
padding:1px 7px;margin:2px 3px 2px 0;background:var(--card2)}
.empty{color:var(--dim);font-style:italic;font-size:12.5px}
.note{font-size:11.5px;color:var(--dim);margin-top:10px;line-height:1.6}
.srcs{font-family:var(--mono);font-size:10.5px;color:#5a6579;margin-top:6px}
.navback{display:inline-flex;gap:16px;margin-top:8px}
.navback a{color:var(--teal);text-decoration:none;font-size:12.5px;
border:1px solid var(--line);border-radius:999px;padding:6px 15px;background:var(--card)}
.navback a:hover{border-color:var(--teal)}
@media(max-width:720px){.stat{min-width:calc(50% - 5px)}}
</style></head><body>
<div class="wrap">
<header>
  <div class="mark">B</div>
  <h1>THE <b>TIME ENGINE</b></h1>
  <div class="updated" id="updated"></div>
</header>
<div class="quote">&ldquo;The Time Engine is not a clock. It records meaning.&rdquo; &mdash; VIB: Butterfly time (spread) &middot; BRK: Monkey time (build)</div>

<div class="statrow" id="statrow"></div>

<div class="card">
  <h2>Switcher States <span>&mdash; mode from burn receipts (yin-yang of the fleet)</span></h2>
  <div class="chips" id="chips"></div>
  <div class="yinyang" id="yy"></div>
  <div class="yylabels"><span id="yl">&nbsp;</span><span id="yr">&nbsp;</span></div>
</div>

<div class="card">
  <h2>Brick Velocity <span>&mdash; BRK (gold) vs VIB (teal), live bricks first</span></h2>
  <div id="bars"></div>
</div>

<div class="card">
  <h2>The Myth Ledger <span>&mdash; this ledger is public. It's your myth.</span></h2>
  <div style="overflow-x:auto">
  <table class="myth">
    <thead><tr><th>Brick</th><th>Bananas</th><th>Mints</th><th>ROI</th><th>Artifacts</th></tr></thead>
    <tbody id="myth"></tbody>
  </table>
  </div>
  <div class="note" id="note"></div>
  <div class="srcs" id="srcs"></div>
</div>

<nav class="navback">
  <a href="/">&larr; Ops Dashboard</a>
  <a href="/approvals">Approvals</a>
</nav>
</div>

<script id="te-payload" type="application/json">__PAYLOAD__</script>
<script>
var P = JSON.parse(document.getElementById('te-payload').textContent);
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function fmt(n){try{return Number(n||0).toLocaleString();}catch(e){return '0';}}
function ago(ts){if(!ts)return '';var d=(Date.now()/1000)-ts;if(d<90)return Math.round(d)+'s ago';
  if(d<5400)return Math.round(d/60)+'m ago';if(d<172800)return Math.round(d/3600)+'h ago';
  return Math.round(d/86400)+'d ago';}

function render(d){
  document.getElementById('updated').textContent = 'generated '+esc(d.generated_at||'');
  var ft=d.fleet_totals||{}, en=d.engine||{};
  document.getElementById('statrow').innerHTML =
    st(ft.bricks_live_1h,ft.bricks_total,'bricks live') +
    st(fmt(ft.threads_live),fmt(ft.threads_total)+' cap','threads') +
    st(fmt(en.brk),'monkey pts','total BRK') +
    st(fmt(en.vib),'butterfly pts','total VIB','t') +
    st(fmt(ft.bananas_total),fmt(ft.mints_total)+' mints','bananas');
  function st(v,sub,k,cls){return '<div class="stat'+(cls?' '+cls:'')+'"><div class="v">'+
    esc(v)+' </div><div class="k">'+esc(k)+(sub?' &middot; <span style="color:#5a6579">'+esc(sub)+'</span>':'')+'</div></div>';}

  // Switcher states
  var sw=d.switcher||{}, modes=sw.modes||{}, om=sw.other_modes||{};
  var chips='';
  ['butterfly','monkey','switcher'].forEach(function(m){
    chips+='<span class="chip '+m+'">'+m.charAt(0).toUpperCase()+m.slice(1)+
      ' <span class="n">'+fmt(modes[m]||0)+'</span>'+
      (sw.latest_ts&&sw.latest_ts[m]?' <small style="color:#5a6579">'+ago(sw.latest_ts[m])+'</small>':'')+
      '</span>';});
  Object.keys(om).forEach(function(m){
    chips+='<span class="chip">'+esc(m)+' <span class="n">'+fmt(om[m])+'</span></span>';});
  document.getElementById('chips').innerHTML=chips||
    '<span class="empty">no instrumented receipts yet</span>';
  var tot=('butterfly' in modes?modes.butterfly:0)+('monkey' in modes?modes.monkey:0)+('switcher' in modes?modes.switcher:0);
  var yy=document.getElementById('yy');
  if(tot>0){
    var pb=Math.round((modes.butterfly||0)/tot*100), pm=Math.round((modes.monkey||0)/tot*100);
    yy.innerHTML='<i class="yb" style="width:'+pb+'%"></i><i class="ys" style="width:'+(100-pb-pm)+'%"></i><i class="ym" style="width:'+pm+'%"></i>';
    document.getElementById('yl').textContent='butterfly '+pb+'%';
    document.getElementById('yr').textContent='monkey '+pm+'%';
  }else{
    yy.innerHTML='';document.getElementById('yl').textContent='awaiting instrumented receipts';
    document.getElementById('yr').textContent='';
  }

  // Per-brick VIB/BRK bars — live first, then by BRK+VIB+bananas desc
  var bricks=(d.bricks||[]).slice().sort(function(a,b){
    return (b.live-a.live)||((b.brk+b.vib+b.bananas)-(a.brk+a.vib+a.bananas));});
  var maxV=1;
  bricks.forEach(function(x){maxV=Math.max(maxV,x.brk||0,x.vib||0);});
  var bh='';
  bricks.forEach(function(x){
    var bw=Math.round((x.brk||0)/maxV*100), vw=Math.round((x.vib||0)/maxV*100);
    var mode='';
    bh+='<div class="brickrow"><div class="brickhead">'+
      '<span class="dot '+(x.live?'live':'parked')+'" title="'+(x.live?'live':'parked')+'"></span>'+
      '<span class="bid">'+esc(x.brick)+'</span>'+
      (x.role?'<span class="rolechip">'+esc(x.role)+'</span>':'')+
      '<span class="thr">'+fmt(x.threads||0)+' threads'+(x.last_heartbeat?' &middot; beat '+ago(x.last_heartbeat):'')+'</span>'+
      '</div>'+
      '<div class="barline"><span class="blab brk">BRK</span><div class="track">'+
      '<div class="fill brk" style="width:'+bw+'%"></div></div><span class="bnum">'+fmt(x.brk||0)+'</span></div>'+
      '<div class="barline"><span class="blab vib">VIB</span><div class="track">'+
      '<div class="fill vib" style="width:'+vw+'%"></div></div><span class="bnum">'+fmt(x.vib||0)+'</span></div>'+
      (((x.brk||0)==0&&(x.vib||0)==0)?'<div class="empty" style="font-size:10.5px">awaiting instrumented receipts (brk/vib/mode)</div>':'')+
      '</div>';});
  document.getElementById('bars').innerHTML=bh||'<span class="empty">brick ledger empty</span>';

  // Myth ledger table
  var rows='';
  bricks.forEach(function(x){
    var arts=(x.artifacts||[]);
    rows+='<tr><td><span class="bid2">'+esc(x.brick)+'</span>'+(x.live?' <span style="color:var(--teal);font-size:10px">&#9679;</span>':'')+
      '<div class="rl">'+esc(x.role||'')+'</div></td>'+
      '<td class="num">'+fmt(x.bananas)+'&#127820;</td>'+
      '<td class="num t">'+fmt(x.mints)+'</td>'+
      '<td class="num">'+(typeof x.roi==='number'?x.roi.toFixed(2):esc(x.roi))+'</td>'+
      '<td class="arts">'+(arts.length?arts.map(function(a){return '<span title="'+esc(a)+'">'+esc(a.length>42?a.slice(0,41)+'&hellip;':a)+'</span>';}).join('')
        :'<span class="empty">none logged</span>')+(x.artifacts_count>(x.artifacts||[]).length?
        ' <em style="color:#5a6579">+'+(x.artifacts_count-(x.artifacts||[]).length)+' more</em>':'')+'</td></tr>';});
  document.getElementById('myth').innerHTML=rows||'<tr><td colspan="5" class="empty">brick ledger empty</td></tr>';

  document.getElementById('note').textContent=d.note||'';
  document.getElementById('srcs').textContent=
    'sources: '+((d.sources||[]).map(function(s){
      return s.file+(s.mtime_iso?' @ '+s.mtime_iso:' (missing)');}).join(' | ')||'none');
}
render(P);
setInterval(function(){
  fetch('/api/time-engine',{cache:'no-store'}).then(function(r){
    if(r.ok)return r.json();
  }).then(function(d){if(d)render(d);}).catch(function(){});
},20000);
</script>
</body></html>""".replace("__PAYLOAD__", payload_js)


def timeflow_data(hours=24):
    """TIME MACHINE: per-second event rail for the last N hours. Sources: wallet.jsonl (mints,
    invests, docks, credits, seeds, wallets), dispatches, spawns, bottleneck flags, and the router
    ledger (every routed call). Events carry exact ts (second precision). Also returns non-empty 5s
    buckets + a full 60s histogram (1440 bars) for the playback scrubber. Cached 60s — the ledger
    is ~5k rows and burn_data already pays that cost on its own cache."""
    with TIMEFLOW_LOCK:  # keep the cache write race-free
        if time.time() - timeflow_cache["ts"] < 60 and timeflow_cache["out"] is not None:
            return timeflow_cache["out"]
    now = time.time()
    start = now - hours * 3600.0
    events = []

    def add(ts, etype, label, icon, sub=None):
        t = _iso_to_ts(ts) if isinstance(ts, str) else ts
        if t is None:
            return
        try:
            t = float(t)
        except (TypeError, ValueError):
            return
        if t < start or t > now + 600:
            return
        events.append({"ts": t, "type": etype, "label": str(label)[:150],
                       "icon": icon, "sub": str(sub or "")[:170]})

    for r in (read_jsonl(WALLET) or []):
        if not isinstance(r, dict):
            continue
        k = r.get("kind")
        who = r.get("person") or r.get("person_id") or r.get("brick_id") or "?"
        try:
            b = float(r.get("bananas", 0) or 0)
        except (TypeError, ValueError):
            b = 0.0
        if k == "earn":
            add(r.get("ts"), "mint", f"{b:g}🍌 minted by {who}", "🍌",
                f"card {r.get('card_id','')} · clean={not r.get('contested')}")
        elif k == "invest":
            add(r.get("ts"), "invest", f"{b:g}🍌 invested into {r.get('project_id','?')} by {who}", "💼",
                f"terms {str(r.get('terms_sha',''))[:8]} · card {r.get('card_id','')}")
        elif k == "dock":
            add(r.get("ts"), "dock", f"dock {b:g}🍌 {who}", "⚓", r.get("reason"))
        elif k == "credit":
            add(r.get("ts"), "credit", f"{b:g}🍌 credit to {who}", "🎁", r.get("purpose"))
        elif k == "founder-seed":
            add(r.get("ts"), "seed", f"{b:g}🍌 founder seed {who}", "🌰", r.get("purpose"))
        elif k == "wallet-open":
            add(r.get("ts"), "wallet", f"wallet opened for {who}", "👛")
        elif k == "module-complete":
            add(r.get("ts"), "module", f"module complete {who}", "✅")
    for r in (read_jsonl(DISPATCHES) or []):
        if not isinstance(r, dict):
            continue
        det = r.get("detail")
        if isinstance(det, str):
            try:
                det = json.loads(det)
            except Exception:
                det = {}
        if not isinstance(det, dict):
            det = {}
        brick = det.get("brick_id") or r.get("brick_id") or "?"
        card = det.get("card_id") or r.get("card_id") or ""
        add(r.get("ts"), "dispatch", f"dispatch → {brick}", "📦",
            f"{r.get('op','')} card {card} · {r.get('outcome','')}")
    for r in (read_jsonl(SPAWNS) or []):
        if isinstance(r, dict):
            add(r.get("ts"), "spawn", f"spawn {r.get('new_brick_id','?')}", "🌱",
                f"replaces {r.get('replaces','?')} — {r.get('reason','')}")
    for r in (read_jsonl(BOTTLENECKS) or []):
        if isinstance(r, dict):
            add(r.get("ts"), "flag", f"flag {r.get('brick_id','?')} · {r.get('reason','')}", "🚩",
                r.get("detail"))
    for r in (read_jsonl(LANE_LEDGER) or []):
        if isinstance(r, dict):
            add(r.get("ts"), "route", f"route {r.get('lane','?')}", "🔀",
                f"{r.get('model','')} · ${r.get('cost',0)}")
    events.sort(key=lambda e: e["ts"])
    capped = len(events) > 3000
    if capped:
        events = events[-3000:]
    buckets5, hist60, by_type = {}, {}, {}
    # full 24h minute range (zero-filled) so the rail renders as one continuous strip
    m0 = int(start // 60) * 60
    m1 = int(now // 60) * 60
    for m in range(m0, m1 + 1, 60):
        hist60[m] = 0
    for e in events:
        b5 = int(e["ts"] // 5) * 5
        buckets5[b5] = buckets5.get(b5, 0) + 1
        b60 = int(e["ts"] // 60) * 60
        hist60[b60] = hist60.get(b60, 0) + 1
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    out = {
        "generated_at": now_iso(),
        "window": {"hours": hours, "start": start, "end": now},
        "total_events": len(events),
        "capped": capped,
        "events": events,
        "buckets_5s": [{"t": t, "n": n} for t, n in sorted(buckets5.items())],
        "histogram_60s": [{"t": t, "n": n} for t, n in sorted(hist60.items())],
        "by_type": by_type,
        "note": "per-second events from wallet.jsonl + dispatches + spawns + bottleneck flags + router ledger — empty rail = genuinely quiet fleet, not missing data",
    }
    timeflow_cache["ts"] = time.time()
    timeflow_cache["out"] = out
    return out



# ------------------------------------------------- capacity board + epic tracker
CAPACITY_LEDGER = "/srv/bricks/orchestrator/brick-ledger.json"
CAPACITY_QUEUE = "/srv/bricks/orchestrator/queue.json"
CAPACITY_REALTIME = "/srv/bricks/orchestrator/fleet-realtime.json"

# Time Machine product family (time-machine canon) -> keyword matchers over
# queue prompts + merged PR titles. Progress = done / (done + pending) goals,
# plus merged-PR attribution where titles match.
TM_EPICS = [
    {"name": "Time Engine", "keys": ["time engine", "vib", "brk ", "switcher", "temporal"]},
    {"name": "Banana Bank", "keys": ["banana"]},
    {"name": "Tamr Time Machine", "keys": ["tamr", "time node", "myth ledger", "orbit"]},
    {"name": "Hearth SDK", "keys": ["hearth"]},
    {"name": "Payments SDK", "keys": ["payment", "stripe", "moyasar", "myfatoorah", "checkout"]},
]

IDLE_STALE_MIN = 60  # machine-time convention: >60 machine-minutes without a heartbeat = stale


def _cap_load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        return {"_error": str(e)}


def capacity_data():
    """CAPACITY BOARD payload: per-brick threads-vs-live, queue depth + recent
    done goals, Time Machine epic progress from queue goals + merged PRs.
    Read-only over the orchestrator files; tolerant to missing/corrupt inputs."""
    errors = {}
    ledger = _cap_load(CAPACITY_LEDGER)
    queue = _cap_load(CAPACITY_QUEUE)
    realtime = _cap_load(CAPACITY_REALTIME)
    for label, d in (("ledger", ledger), ("queue", queue), ("realtime", realtime)):
        if isinstance(d, dict) and d.get("_error"):
            errors[label] = d["_error"]

    now = time.time()

    # ---- per-brick capacity rows -------------------------------------------------
    bricks = []
    per = ledger.get("per_brick") or {}
    if isinstance(per, list):  # defensive: tolerate ledger shape drift
        per = {(b.get("brick_id") if isinstance(b, dict) else None) or f"brick-{i}": b
               for i, b in enumerate(per)}
    for name, b in sorted(per.items()):
        if not isinstance(b, dict):
            continue
        hb = b.get("last_heartbeat")
        age_min = round((now - hb) / 60.0) if isinstance(hb, (int, float)) and hb > 0 else None
        if not b.get("live"):
            status = "IDLE"
        elif age_min is not None and age_min > IDLE_STALE_MIN:
            status = "STALE"
        else:
            status = "LIVE"
        tel = b.get("telemetry") or {}
        bricks.append({
            "name": name,
            "role": b.get("role"),
            "cap": b.get("capacity_threads"),
            "threads_live": tel.get("threads") if isinstance(tel, dict) else None,
            "status": status,
            "hb_age_min": age_min,
            "bananas": b.get("bananas_earned", 0),
            "mints": b.get("mints", 0),
            "roi": b.get("roi", 0),
            "accomplishments_n": len(b.get("accomplishments") or []),
        })
    bricks.sort(key=lambda r: ({"LIVE": 0, "STALE": 1, "IDLE": 2}[r["status"]],
                               -(r["cap"] or 0), r["name"]))

    # ---- queue -------------------------------------------------------------------
    goals = []
    if isinstance(queue, dict) and isinstance(queue.get("goals"), list):
        goals = queue["goals"]
    elif isinstance(queue, list):
        goals = queue
    done_g = [g for g in goals if isinstance(g, dict) and g.get("status") == "done"]
    pend_g = [g for g in goals if isinstance(g, dict) and g.get("status") == "pending"]

    def short(g, n=170):
        p = re.sub(r"\s+", " ", str(g.get("prompt") or "")).strip()
        return p[:n] + ("…" if len(p) > n else "")

    queue_out = {
        "total": len(goals),
        "pending": len(pend_g),
        "done": len(done_g),
        "pending_goals": [{"id": g.get("id"), "short": short(g)} for g in reversed(pend_g[:12])],
        "recent_done": [{"id": g.get("id"), "short": short(g)} for g in reversed(done_g[-8:])],
    }

    # ---- epics: queue goals + merged PRs -----------------------------------------
    merged_titles = []
    gh_note = None
    try:
        gh = github_data(force=False) or {}
        merged_titles = [str(t).lower() for t in (gh.get("merged_titles") or [])]
    except Exception as e:
        gh_note = f"github merges unavailable: {e}"

    epics = []
    for e in TM_EPICS:
        keys = e["keys"]
        dn = pn = mg = 0
        for g in goals:
            if not isinstance(g, dict):
                continue
            p = str(g.get("prompt") or "").lower()
            st = g.get("status")
            if st == "done" and any(k in p for k in keys):
                dn += 1
            elif st == "pending" and any(k in p for k in keys):
                pn += 1
        for t in merged_titles:
            if any(k in t for k in keys):
                mg += 1
        tot = dn + pn
        epics.append({
            "name": e["name"],
            "done": dn, "pending": pn, "total": tot,
            "pct": round(100 * dn / tot) if tot else 0,
            "merges": mg,
        })

    rt_q = realtime.get("queue") if isinstance(realtime, dict) else None
    out = {
        "generated_at": now_iso(),
        "taxonomy": ledger.get("taxonomy") if isinstance(ledger, dict) else None,
        "fleet": ledger.get("fleet") if isinstance(ledger, dict) else {},
        "realtime": {
            "ts": realtime.get("ts") if isinstance(realtime, dict) else None,
            "ovh_threads": (realtime.get("ovh") or {}).get("threads") if isinstance(realtime, dict) else None,
            "queue_pending_rt": rt_q.get("pending") if isinstance(rt_q, dict) else None,
            "burn_last_1h": ((realtime.get("burn_ovh") or {}).get("last_1h")
                             if isinstance(realtime, dict) else None),
            "bricks_registered": realtime.get("bricks_registered") if isinstance(realtime, dict) else None,
            "bricks_heartbeating_1h": realtime.get("bricks_heartbeating_1h") if isinstance(realtime, dict) else None,
        },
        "bricks": bricks,
        "queue": queue_out,
        "epics": epics,
        "sources": {"ledger": CAPACITY_LEDGER, "queue": CAPACITY_QUEUE,
                    "realtime": CAPACITY_REALTIME},
        "errors": errors,
        "github_note": gh_note,
    }
    return out


def fleetlive_data():
    """LIVE FLEET STATUS: running bricks, current work, contributions, capacity."""
    import json as _j, os as _os, time as _time, sqlite3 as _sqlite
    reg_path = "/srv/bricks/register/registry.jsonl"
    rec_path = "/srv/bricks/orchestrator/receipts-ovh.jsonl"
    tel_path = "/srv/bricks/register/telemetry.jsonl"
    kanban = "/home/ubuntu/.hermes/kanban/boards/fleet/kanban.db"
    now = _time.time()

    bricks, status_counts = [], {}
    try:
        for line in open(reg_path):
            r = _j.loads(line)
            s = r.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1
            bricks.append({"id": r.get("brick_id"), "status": s,
                           "role": r.get("role"), "owner": r.get("owner")})
    except Exception:
        pass

    contrib = []
    try:
        for line in open(rec_path):
            r = _j.loads(line)
            if now - r.get("ts", 0) < 86400 and r.get("kind") in ("claim-run", "earn"):
                contrib.append({"task": r.get("task_id"), "lane": r.get("lane"),
                                "cost": r.get("cost"), "artifact": r.get("artifact"),
                                "ts": r.get("ts")})
    except Exception:
        pass

    tele = {}
    try:
        for line in open(tel_path):
            t = _j.loads(line)
            bid = t.get("brick_id")
            if bid:
                tele[bid] = {"cpu": t.get("cpu"), "ram_mb": t.get("ram_mb"), "ts": t.get("ts")}
    except Exception:
        pass

    working = []
    try:
        db = _sqlite.connect(kanban, timeout=3)
        cur = db.cursor()
        cur.execute("SELECT id,status,assignee,title FROM tasks WHERE status IN (?,?)",
                    ("in_progress", "done"))
        for row in cur.fetchall():
            working.append({"id": row[0], "status": row[1],
                            "assignee": row[2], "title": str(row[3])[:60]})
        db.close()
    except Exception:
        pass

    live_ids = set(t for t in tele if tele[t].get("cpu") is not None)
    live_bricks = [b for b in bricks if b["id"] in live_ids]
    capacity = max(0.0, 100.0 * len(live_bricks) / max(len(bricks), 1))

    return {
        "generated_at": now,
        "registry": {"total": len(bricks), "by_status": status_counts},
        "live_now": {"bricks": live_bricks[:20], "count": len(live_bricks)},
        "capacity_pct": round(capacity, 1),
        "working_on": working[:10],
        "contributions_24h": contrib[-15:],
        "contribution_count": len(contrib),
        "telemetry": {k: tele[k] for k in list(tele)[:10]},
        "note": "live_now = bricks with telemetry in last 24h; contributions = receipts 24h",
    }



# ================================================================ mission (2026-08-26)
# MISSION first-screen: NOW / GOALS / VELOCITY / BRICKS — khalid's exact questions,
# plain words, phone-first. Everything else stays behind the tabs.
_MISSION_AUDIT = "/srv/bricks/orchestrator/brick-actions-audit.jsonl"
_GOAL_PLAIN = (
    ("SEC-1", "Verify payment-key rotation"),
    ("GE-1", "Payments extraction plan"),
    ("GE-2", "Wallet service draft"),
    ("NET-1", "Fleet config cleanup"),
)


def _plain_title(task_id, raw):
    """Plain-word title for a kanban task / receipt. Maps known goal ids to the
    words khalid uses; strips task-id noise from everything else."""
    raw = (raw or "").strip()
    hay = " ".join(x for x in (str(task_id or ""), raw) if x)
    for key, plain in _GOAL_PLAIN:
        if key in hay:
            return plain
    t = re.sub(r"^[A-Za-z0-9_\-\.]+(?:\s|:)*", "", raw)
    t = re.sub(r"\s+", " ", t).strip()
    return t or (str(task_id or "") if task_id else "fleet task")


def _registry_append(row):
    """Append one row to registry.jsonl with a cross-process flock."""
    try:
        fd = os.open(REGISTRY, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f, fcntl.LOCK_UN)
        return True
    except OSError as e:
        return str(e)


def _brick_action_audit(action, brick_id, user, result, extra=None):
    """Append a row to the brick-actions audit ledger (append-only, flock)."""
    try:
        row = {"ts": time.time(), "action": action, "brick_id": brick_id,
               "by": (user or {}).get("username"), "result": result}
        if extra:
            row.update(extra)
        fd = os.open(_MISSION_AUDIT, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        pass


def brick_clone_api(src, user):
    """Clone one brick: copy its latest registry identity into a new brick id
    (clone-<src>-<hex>). Same logic as brick_clone.py, inlined (no subprocess)."""
    src = str(src or "").strip()
    if not src or not re.match(r"^[A-Za-z0-9._-]+$", src):
        return False, {"error": "bad brick id"}
    rows = read_jsonl(REGISTRY) or []
    src_row = None
    for r in reversed(rows):
        if r.get("brick_id") == src:
            src_row = r
            break
    if not src_row:
        return False, {"error": "brick %s is not in the registry" % src}
    new_id = "clone-" + src + "-" + secrets.token_hex(4)
    clone = dict(src_row)
    clone["brick_id"] = new_id
    clone["parent_brick_id"] = src
    clone["spawn_of"] = src
    clone["status"] = "registered"
    clone["role"] = src_row.get("role") or "worker"
    clone["owner"] = src_row.get("owner") or user.get("username") or "khalid"
    clone["skills"] = src_row.get("skills") or []
    clone["quality"] = src_row.get("quality") or "registered"
    clone["ts"] = time.time()
    clone["note"] = "cloned from dashboard (mission screen)"
    err = _registry_append(clone)
    if err is not True:
        return False, {"error": "registry write failed: %s" % err}
    _brick_action_audit("clone", src, user, "ok", {"new_id": new_id})
    return True, {"new_id": new_id, "parent": src, "role": clone["role"]}


def brick_wake_api(bid, user):
    """Wake one brick: mark its registry identity status=live (latest row wins).
    Honest note: registry 'live' is a registration claim — the brick picks up work
    when a worker claims tasks; it is not a running process yet."""
    bid = str(bid or "").strip()
    if not bid or not re.match(r"^[A-Za-z0-9._-]+$", bid):
        return False, {"error": "bad brick id"}
    rows = read_jsonl(REGISTRY) or []
    latest = None
    for r in reversed(rows):
        if r.get("brick_id") == bid:
            latest = r
            break
    if latest is None:
        return False, {"error": "brick %s is not in the registry" % bid}
    if (latest.get("status") or "").lower() == "live":
        _brick_action_audit("wake", bid, user, "already-live")
        return True, {"id": bid, "status": "live",
                      "note": "already marked live in the registry"}
    row = dict(latest)
    row["status"] = "live"
    row["ts"] = time.time()
    row["note"] = "wake request from dashboard (mission screen)"
    err = _registry_append(row)
    if err is not True:
        return False, {"error": "registry write failed: %s" % err}
    _brick_action_audit("wake", bid, user, "ok")
    return True, {"id": bid, "status": "live",
                  "note": "marked live in the registry — a worker will pick it up when work is claimed"}


def mission_data():
    """MISSION payload: NOW (last receipts), GOALS (ready kanban tasks), VELOCITY
    (1h vs 24h receipts), BRICKS (alive + idle with clone/wake). Real files only:
    receipts-ovh.jsonl, kanban.db, velocity-report.json, registry.jsonl, fleet-state.json."""
    import sqlite3 as _sqlite
    now = time.time()

    # ---- NOW: last 5 receipts, newest first, plain titles
    receipts = read_jsonl(RECEIPTS_OVH) or []
    kanban_titles = {}
    try:
        con = _sqlite.connect("file:%s?mode=ro" % KANBAN_BOARD_DB, uri=True, timeout=3)
        try:
            for row in con.execute("SELECT id, title FROM tasks"):
                kanban_titles[str(row[0])] = str(row[1])
        except Exception:
            pass
        con.close()
    except Exception:
        pass
    cands = []
    for r in receipts:
        if not isinstance(r, dict) or not r.get("ts"):
            continue
        task_id = r.get("task_id") or ""
        title = kanban_titles.get(str(task_id)) or r.get("goal") or ""
        cands.append({
            "ts": r.get("ts"),
            "age_s": max(0, now - float(r.get("ts"))),
            "task_id": str(task_id),
            "title": _plain_title(task_id, title),
            "who": r.get("claimer") or r.get("brick_id") or r.get("lane") or "fleet",
            "lane": r.get("lane"),
            "cost": r.get("cost"),
            "artifact": r.get("artifact") or r.get("output"),
            "kind": r.get("kind") or "work",
        })
    cands.sort(key=lambda x: -x["ts"])
    now_rows = cands[:5]

    # ---- GOALS: ready kanban tasks + done count + in_progress
    goals, in_progress = [], []
    done_count = 0
    try:
        con = _sqlite.connect("file:%s?mode=ro" % KANBAN_BOARD_DB, uri=True, timeout=3)
        for row in con.execute("SELECT id, title, assignee, status, created_at "
                               "FROM tasks ORDER BY created_at DESC"):
            tid, title, assignee, status, created_at = row
            if status == "ready":
                goals.append({"id": str(tid), "title": _plain_title(tid, title),
                              "owner": assignee or "", "status": "ready",
                              "created_at": created_at, "artifact": None})
            elif status == "in_progress":
                in_progress.append({"id": str(tid), "title": _plain_title(tid, title),
                                    "owner": assignee or "", "status": "in_progress"})
            elif status == "done":
                done_count += 1
        con.close()
    except Exception:
        pass

    # ---- VELOCITY: one bar — receipts this hour vs the last 24h
    velocity = {"receipts_1h": None, "receipts_24h": None, "verdict": None,
                "stalled": None, "minutes_since_activity": None, "pct_1h": None,
                "moving": False, "generated_at": None}
    try:
        vf = "/srv/bricks/orchestrator/velocity-report.json"
        if os.path.exists(vf):
            v = json.load(open(vf))
            vv = v.get("velocity") or {}
            vb = v.get("board") or {}
            vs = v.get("stall") or {}
            r1 = vv.get("receipts_1h")
            r24 = vv.get("receipts_24h")
            r24avg = (float(r24) / 24.0) if r24 else None
            pct = None
            if r1 is not None and r24avg:
                pct = int(min(100.0, round(100.0 * float(r1) / max(r24avg, 0.001))))
            moving = str(v.get("verdict") or "").upper() == "MOVING" or vs.get("stalled") is False
            velocity = {"receipts_1h": r1, "receipts_24h": r24,
                        "verdict": v.get("verdict"), "stalled": vs.get("stalled"),
                        "minutes_since_activity": vs.get("minutes_since_activity"),
                        "pct_1h": pct, "moving": bool(moving),
                        "generated_at": v.get("generated_at"),
                        "done": vb.get("done"), "ready": vb.get("ready")}
    except Exception:
        pass

    # ---- BRICKS: registry identities (latest row per id) + live from telemetry
    reg_rows = read_jsonl(REGISTRY) or []
    latest = {}
    for r in reg_rows:
        bid = r.get("brick_id")
        if bid:
            latest[str(bid)] = r
    fs = {}
    try:
        fs = json.load(open("/srv/bricks/orchestrator/fleet-state.json"))
    except Exception:
        pass
    pb = fs.get("per_brick") or {}
    bricks = []
    for bid, row in latest.items():
        cap = (pb.get(bid) or {}).get("capacity") or {}
        bricks.append({
            "id": bid,
            "status": row.get("status"),
            "quality": row.get("quality"),
            "role": row.get("role"),
            "owner": row.get("owner"),
            "earned": (pb.get(bid) or {}).get("earned_bananas", 0),
            "skills": row.get("skills") or [],
            "parent": row.get("parent_brick_id") or row.get("spawn_of"),
            "live": bool(cap.get("live")),
            "cpu": cap.get("cpu"),
            "ram_mb": cap.get("ram_mb"),
        })
    bricks.sort(key=lambda b: (not b["live"], b["id"]))
    alive = [b for b in bricks if b["live"]]
    idle = [b for b in bricks if not b["live"]]

    return {
        "now": now_rows,
        "goals": goals,
        "in_progress": in_progress,
        "done_count": done_count,
        "velocity": velocity,
        "bricks": {
            "alive": alive,
            "idle": idle,
            "badges": len(bricks),
            "live_count": len(alive),
            "idle_count": len(idle),
            "registry_rows": len(reg_rows),
            "capacity_pct": (fs.get("fleet") or {}).get("capacity_pct"),
        },
        "generated_at": now,
        "note": "MISSION: real files only — receipts-ovh.jsonl, fleet kanban, velocity-report.json, registry.jsonl, fleet-state.json",
    }


# ================================================================ THE FLOOR (2026-08-26)
# /floor — the 2D universe view khalid plays (the munder-difflin office floor, web-rendered,
# BORROW-SELECTIVELY per the fleet ruling). Every brick is an avatar positioned by role and
# lineage. HONESTY RULE (binding, per the rebel dissent A-3/A-5/A-10/A-11): an avatar MOVES
# only when a REAL receipt exists in the last 10 minutes — idle bricks stand still. No fake
# activity, no idle quips, no simulated busyness, no clone-boss. If the fleet is quiet, the
# floor is quiet (velocity-agent + claimer keep it moving with real work).
# Data = fleet-state.json + receipts-ovh.jsonl + registry.jsonl + brick-cvs.json +
# agent-relay.jsonl + kanban.db + player-profile.json — all real files, nothing invented.
_FLOOR_WINDOW_S = 600          # honesty window: a receipt inside this window = moving
_FLOOR_CACHE = {"t": 0.0, "data": None}


def _floor_player():
    """khalid's player block — canonical player-profile.json (player_profile.py, 1-min cron)."""
    try:
        d = json.load(open("/srv/bricks/orchestrator/player-profile.json"))
        return {
            "id": d.get("player") or "khalid",
            "level": d.get("level"),
            "xp": d.get("xp"),
            "xp_to_next": d.get("xp_to_next"),
            "bananas": d.get("my_earned_bananas"),
            "rank_vs_fleet": d.get("rank_vs_fleet"),
            "verified_artifacts": d.get("verified_artifacts"),
            "cv_line": d.get("cv_line"),
            "next_quest_hint": d.get("next_quest_hint"),
            "generated_at": d.get("generated_at"),
        }
    except Exception:
        return None


def floor_data():
    """THE FLOOR payload: every brick as an avatar (role/lineage positions are computed
    client-side from role + parent), live events = REAL receipts from the last 10 min with
    the task name in plain words, the player (khalid) with level/XP, and an honesty block
    stating the window + moving count. Cached 10s."""
    import sqlite3 as _sqlite
    now = time.time()
    if _FLOOR_CACHE["data"] is not None and now - _FLOOR_CACHE["t"] < 10:
        return _FLOOR_CACHE["data"]

    fs = {}
    try:
        fs = json.load(open("/srv/bricks/orchestrator/fleet-state.json"))
    except Exception:
        pass
    fleet = fs.get("fleet") or {}
    pb = fs.get("per_brick") or {}

    # registry: latest row per brick (role / owner / status / lineage)
    reg_rows = read_jsonl(REGISTRY) or []
    latest = {}
    for r in reg_rows:
        bid = r.get("brick_id")
        if bid:
            latest[str(bid)] = r

    # CV layer: skills / tasks / artifacts / standing / cv_line
    cvs = {}
    try:
        cvs = json.load(open("/srv/bricks/orchestrator/brick-cvs.json"))
    except Exception:
        pass

    # receipts: last receipt per brick + the honesty window (last 10 min)
    receipts = read_jsonl(RECEIPTS_OVH) or []
    last_receipt = {}
    last_lane = {}
    last_task = {}
    window_events = []
    for r in receipts:
        if not isinstance(r, dict):
            continue
        ts = r.get("ts")
        try:
            ts_e = float(ts) if isinstance(ts, (int, float)) else _iso_to_ts(ts)
        except Exception:
            ts_e = None
        bid = str(r.get("brick_id") or r.get("claimer") or "")
        if not bid or ts_e is None:
            continue
        if bid not in last_receipt or ts_e > last_receipt[bid]:
            last_receipt[bid] = ts_e
            last_lane[bid] = r.get("lane")
            last_task[bid] = str(r.get("task_id") or r.get("goal") or "")
        if now - ts_e <= _FLOOR_WINDOW_S:
            window_events.append({
                "ts": ts_e, "brick_id": bid,
                "task_id": str(r.get("task_id") or r.get("goal") or ""),
                "lane": r.get("lane"), "cost": r.get("cost"),
                "artifact": r.get("artifact") or r.get("output"),
                "kind": r.get("kind") or "work",
            })
    window_events.sort(key=lambda e: -e["ts"])

    # kanban titles -> plain words for event labels
    kanban_titles = {}
    try:
        con = _sqlite.connect("file:%s?mode=ro" % KANBAN_BOARD_DB, uri=True, timeout=3)
        try:
            for row in con.execute("SELECT id, title FROM tasks"):
                kanban_titles[str(row[0])] = str(row[1])
        except Exception:
            pass
        con.close()
    except Exception:
        pass
    for e in window_events:
        e["title"] = _plain_title(e["task_id"], kanban_titles.get(e["task_id"]) or "")

    # bricks: one avatar per registry identity, honest state per brick
    bricks = []
    for bid, row in latest.items():
        p = pb.get(bid) or {}
        cap = p.get("capacity") or {}
        cv = cvs.get(bid) or {}
        lr = last_receipt.get(bid)
        art = cv.get("artifacts") or []
        bricks.append({
            "id": bid,
            "role": row.get("role") or cv.get("role") or "?",
            "owner": row.get("owner") or cv.get("owner"),
            "status": row.get("status") or cv.get("status") or "?",
            "quality": row.get("quality"),
            "live": bool(cap.get("live")),
            "earned_bananas": p.get("earned_bananas", cv.get("earned_bananas", 0)),
            "clean_earned_bananas": p.get("clean_earned_bananas", cv.get("clean_earned_bananas", 0)),
            "value_usd": p.get("value_usd"),
            "roi_ratio": p.get("roi_ratio", cv.get("roi")),
            "skills": row.get("skills") or cv.get("skills") or [],
            "tasks_done": cv.get("tasks_done", 0),
            "artifacts_count": len(art) if isinstance(art, list) else (cv.get("artifacts_count") or 0),
            "cv_line": cv.get("cv_line"),
            "standing": cv.get("standing"),
            "parent": row.get("parent_brick_id") or row.get("spawn_of"),
            "last_receipt_ts": lr,
            "last_receipt_age_s": (now - lr) if lr else None,
            "last_lane": last_lane.get(bid),
            "last_task_title": (_plain_title(last_task.get(bid) or "",
                                             kanban_titles.get(last_task.get(bid) or "") or "")
                                if last_task.get(bid) else None),
            "moving": bool(lr and now - lr <= _FLOOR_WINDOW_S),
        })
    bricks.sort(key=lambda b: (not b["moving"], not b["live"], b["id"]))

    # relay tail: the live thought/event stream the floor's ticker renders
    relay = []
    try:
        rows = read_jsonl(RELAY) or []
        for r in rows[-10:]:
            if isinstance(r, dict):
                relay.append({"ts": r.get("ts"), "from": r.get("from"), "to": r.get("to"),
                              "kind": r.get("kind"), "body": (r.get("body") or "")[:240]})
    except Exception:
        pass

    moving = [b for b in bricks if b["moving"]]
    live = [b for b in bricks if b["live"]]
    parked = [b for b in bricks if not b["live"]]

    out = {
        "generated_at": now,
        "honesty": {
            "window_s": _FLOOR_WINDOW_S,
            "moving": len(moving),
            "live": len(live),
            "parked": len(parked),
            "total": len(bricks),
            "note": ("avatars move ONLY on real receipts inside the last %d min — "
                     "idle bricks stand still; a quiet fleet renders quiet") % (_FLOOR_WINDOW_S // 60),
        },
        "fleet": {
            "bricks_total": fleet.get("bricks_total"),
            "bricks_live": fleet.get("bricks_live"),
            "capacity_pct": fleet.get("capacity_pct"),
            "total_earned_bananas": fleet.get("total_earned_bananas"),
            "total_clean_bananas": fleet.get("total_clean_bananas"),
            "generated_at": fs.get("generated_at"),
        },
        "bricks": bricks,
        "events": window_events[:30],
        "relay": relay,
        "player": _floor_player(),
        "note": "FLOOR: real files only — fleet-state.json, receipts-ovh.jsonl, registry.jsonl, brick-cvs.json, agent-relay.jsonl, kanban.db, player-profile.json",
    }
    _FLOOR_CACHE["t"] = now
    _FLOOR_CACHE["data"] = out
    return out


# ================================================================ deep-dive (2026-08-26)
# BRICK + TASK DEEP-DIVE + TICKETED FLEET MESSAGES
# GET /api/brick/<id> — profile, relay thought-thread, receipts, artifacts, current task, stats
# GET /api/task/<id>  — status, owner, lifecycle timestamps, artifact, receipt, relay thread
# GET /api/artifact   — session-gated text view of a brick/task's OWN artifacts (basename whitelist)
# POST /api/comms     — gained optional `to` (targeted); a broadcast ALSO mints a kanban ticket
_ARTIFACT_ROOTS = ("/srv/bricks/orchestrator/out", "/srv/bricks/orchestrator/outputs", "/srv/research")
_ARTIFACT_MAX_BYTES = 65536


def _brick_stem(bid):
    """worker-001 -> worker ; scientist-001 -> scientist ; machine-time-pool -> machine-time."""
    s = str(bid or "").strip()
    return s.split("-")[0] if s else ""


def _brick_artifact_map(brick_id):
    """{basename: fullpath} of files that provably belong to a brick: its receipts'
    artifact/output paths (if they exist) + stem-matched files under the artifact roots."""
    m = {}
    stem = _brick_stem(brick_id)
    for r in (read_jsonl(RECEIPTS_OVH) or []):
        if not isinstance(r, dict):
            continue
        claimer = str(r.get("claimer") or r.get("brick_id") or "")
        if claimer and (claimer == brick_id or claimer == stem
                        or str(r.get("brick_id") or "") == brick_id):
            for key in ("artifact", "output"):
                p = r.get(key)
                if p and os.path.isfile(str(p)):
                    m[os.path.basename(str(p))] = str(p)
    if stem:
        for root in _ARTIFACT_ROOTS:
            try:
                for fn in os.listdir(root):
                    if fn.startswith(stem):
                        p = os.path.join(root, fn)
                        if os.path.isfile(p):
                            m[fn] = p
            except OSError:
                pass
    return m


def _brick_artifacts(brick_id):
    now = time.time()
    out = []
    for name, path in _brick_artifact_map(brick_id).items():
        try:
            st = os.stat(path)
            size, mtime = st.st_size, st.st_mtime
        except OSError:
            size, mtime = None, None
        out.append({"name": name, "path": path, "size": size, "ts": mtime,
                    "age_s": (now - mtime) if mtime else None,
                    "url": "/api/artifact?brick=%s&file=%s"
                           % (urllib.parse.quote(brick_id), urllib.parse.quote(name))})
    out.sort(key=lambda a: -(a["ts"] or 0))
    return out


def _task_artifact_map(task_id):
    """{basename: fullpath} for a task: receipt artifacts/outputs + the path named in the task result."""
    m = {}
    for r in (read_jsonl(RECEIPTS_OVH) or []):
        if not isinstance(r, dict):
            continue
        if str(r.get("task_id") or r.get("goal") or "") != task_id:
            continue
        for key in ("artifact", "output"):
            p = r.get(key)
            if p and os.path.isfile(str(p)):
                m[os.path.basename(str(p))] = str(p)
    try:
        import sqlite3 as _sqlite
        con = _sqlite.connect("file:%s?mode=ro" % KANBAN_BOARD_DB, uri=True, timeout=3)
        row = con.execute("SELECT result FROM tasks WHERE id=?", (task_id,)).fetchone()
        con.close()
        if row and row[0]:
            mm = re.search(r"(/srv/[^\s\)\.,]+)", str(row[0]))
            if mm and os.path.isfile(mm.group(1)):
                m[os.path.basename(mm.group(1))] = mm.group(1)
    except Exception:
        pass
    return m


def brick_data(brick_id):
    """Deep-dive payload for one brick: who it is, its thought thread on the relay,
    the work it receipted, its artifacts, its current kanban task, and honest stats."""
    import sqlite3 as _sqlite
    brick_id = str(brick_id or "").strip()
    now = time.time()
    profile = None
    for r in (read_jsonl(REGISTRY) or []):
        if isinstance(r, dict) and str(r.get("brick_id") or "") == brick_id:
            profile = r
    if profile is None:
        return {"found": False, "brick_id": brick_id,
                "note": "no registry row for this brick id — it may have been retired or renamed"}
    fs = {}
    try:
        fs = json.load(open("/srv/bricks/orchestrator/fleet-state.json"))
    except Exception:
        pass
    pb = (fs.get("per_brick") or {}).get(brick_id) or {}
    cap = pb.get("capacity") or {}
    thread = []
    for r in (read_jsonl(RELAY) or []):
        if not isinstance(r, dict):
            continue
        frm = str(r.get("from") or "")
        to = str(r.get("to") or "")
        if frm == brick_id or to == brick_id or brick_id in [x.strip() for x in to.split(",")]:
            thread.append({"ts": r.get("ts"), "ts_epoch": _iso_to_ts(r.get("ts")),
                           "from": frm, "to": to, "kind": r.get("kind"),
                           "body": r.get("body"), "receipt": r.get("receipt") or r.get("ticket")})
    thread.sort(key=lambda x: x["ts_epoch"] or 0)
    receipts = []
    stem = _brick_stem(brick_id)
    for r in (read_jsonl(RECEIPTS_OVH) or []):
        if not isinstance(r, dict):
            continue
        claimer = str(r.get("claimer") or r.get("brick_id") or "")
        if claimer and (claimer == brick_id or claimer == stem
                        or str(r.get("brick_id") or "") == brick_id):
            receipts.append({"ts": r.get("ts"), "ts_epoch": _iso_to_ts(r.get("ts")),
                             "task_id": r.get("task_id") or r.get("goal"), "claimer": claimer,
                             "lane": r.get("lane"), "cost": r.get("cost"),
                             "artifact": r.get("artifact") or r.get("output"),
                             "kind": r.get("kind") or "work"})
    receipts.sort(key=lambda x: -(x["ts_epoch"] or 0))
    current_task = None
    try:
        con = _sqlite.connect("file:%s?mode=ro" % KANBAN_BOARD_DB, uri=True, timeout=3)
        rows = con.execute("SELECT id, title, status, assignee FROM tasks "
                           "WHERE assignee=? AND status IN ('ready','in_progress') "
                           "ORDER BY created_at DESC", (brick_id,)).fetchall()
        con.close()
        if rows:
            current_task = {"id": str(rows[0][0]), "title": str(rows[0][1]),
                            "status": rows[0][2], "assignee": rows[0][3]}
    except Exception:
        pass
    h1 = [r for r in receipts if r["ts_epoch"] and now - r["ts_epoch"] < 3600]
    h24 = [r for r in receipts if r["ts_epoch"] and now - r["ts_epoch"] < 86400]
    cost24 = sum(float(r.get("cost") or 0) for r in h24)
    last_act = None
    if thread and thread[-1].get("ts_epoch"):
        last_act = thread[-1]["ts_epoch"]
    elif receipts and receipts[0].get("ts_epoch"):
        last_act = receipts[0]["ts_epoch"]
    return {
        "found": True,
        "brick_id": brick_id,
        "profile": {
            "id": brick_id, "status": profile.get("status"), "role": profile.get("role"),
            "owner": profile.get("owner"), "quality": profile.get("quality"),
            "skills": profile.get("skills") or [],
            "parent": profile.get("parent_brick_id") or profile.get("spawn_of"),
            "earned": pb.get("earned_bananas", 0), "value_usd": pb.get("value_usd"),
            "cost_usd": pb.get("cost_usd"), "roi_ratio": pb.get("roi_ratio"),
            "live": bool(cap.get("live")), "cpu": cap.get("cpu"), "ram_mb": cap.get("ram_mb"),
            "accomplishments": pb.get("accomplishments") or [],
        },
        "relay_thread": thread[-80:],
        "receipts": receipts[:20],
        "artifacts": _brick_artifacts(brick_id),
        "current_task": current_task,
        "stats": {"receipts_1h": len(h1), "receipts_24h": len(h24),
                  "cost_24h": cost24, "last_activity_ts": last_act,
                  "last_activity_age_s": (now - last_act) if last_act else None},
        "generated_at": now,
        "note": "thought thread = this brick's own relay messages (the shared bus it reads and writes); receipts = work it receipted; artifacts = files that provably belong to it.",
    }


def task_data(task_id):
    """Deep-dive payload for one kanban task: status, owner, lifecycle timestamps,
    artifact, receipt, and the relay thread that mentioned it."""
    import sqlite3 as _sqlite
    task_id = str(task_id or "").strip()
    row, comments = None, []
    try:
        con = _sqlite.connect("file:%s?mode=ro" % KANBAN_BOARD_DB, uri=True, timeout=3)
        row = con.execute("SELECT id,title,body,assignee,status,priority,created_by,created_at,"
                          "started_at,completed_at,result FROM tasks WHERE id=?",
                          (task_id,)).fetchone()
        for c in con.execute("SELECT author,body,created_at FROM task_comments "
                             "WHERE task_id=? ORDER BY created_at", (task_id,)):
            comments.append({"author": c[0], "body": c[1], "created_at": c[2]})
        con.close()
    except Exception:
        pass
    if row is None:
        return {"found": False, "task_id": task_id,
                "note": "no kanban task with this id on the fleet board"}
    cols = ["id", "title", "body", "assignee", "status", "priority", "created_by",
            "created_at", "started_at", "completed_at", "result"]
    t = dict(zip(cols, row))
    art_map = _task_artifact_map(task_id)
    artifact = None
    if art_map:
        name = sorted(art_map, key=lambda n: -os.path.getmtime(art_map[n]))[0]
        artifact = {"name": name, "path": art_map[name],
                    "url": "/api/artifact?task=%s&file=%s"
                           % (urllib.parse.quote(task_id), urllib.parse.quote(name))}
    receipt = None
    for r in reversed(read_jsonl(RECEIPTS_OVH) or []):
        if not isinstance(r, dict):
            continue
        if str(r.get("task_id") or r.get("goal") or "") == task_id:
            receipt = {"ts": r.get("ts"), "ts_epoch": _iso_to_ts(r.get("ts")),
                       "task_id": r.get("task_id") or r.get("goal"),
                       "claimer": r.get("claimer") or r.get("brick_id") or r.get("lane"),
                       "lane": r.get("lane"), "cost": r.get("cost"),
                       "artifact": r.get("artifact") or r.get("output"),
                       "kind": r.get("kind") or "work"}
            break
    thread = []
    for r in (read_jsonl(RELAY) or []):
        if not isinstance(r, dict):
            continue
        hay = " ".join(str(x) for x in (r.get("body"), r.get("receipt"),
                                        r.get("kind"), r.get("from"), r.get("to")))
        if task_id in hay:
            thread.append({"ts": r.get("ts"), "ts_epoch": _iso_to_ts(r.get("ts")),
                           "from": r.get("from"), "to": r.get("to"), "kind": r.get("kind"),
                           "body": r.get("body"), "receipt": r.get("receipt") or r.get("ticket")})
    thread.sort(key=lambda x: x["ts_epoch"] or 0)
    return {
        "found": True,
        "task": {k: t[k] for k in cols},
        "artifact": artifact,
        "artifact_names": sorted(art_map.keys()),
        "receipt": receipt,
        "thread": thread[-60:],
        "comments": comments[-20:],
        "generated_at": time.time(),
        "note": "artifact = the file the worker wrote (from the receipt or the task result); thread = relay messages that mentioned this task id.",
    }


def fleet_message_ticket(body, username):
    """A broadcast fleet message becomes a real kanban ticket (status=ready) in the SAME
    queue the claimer pool drains: claim -> work -> artifact -> receipt. Direct sqlite
    insert — the same mechanism backlog_seeder.py uses for its cards."""
    import sqlite3 as _sqlite
    ts = int(time.time())
    tid = "fleet-message-%d" % ts
    try:
        db = _sqlite.connect(KANBAN_BOARD_DB, timeout=5)
        cur = db.cursor()
        cur.execute("SELECT 1 FROM tasks WHERE id=?", (tid,))
        if cur.fetchone():
            tid = "fleet-message-%d-%d" % (ts, int(time.time() * 1000) % 10000)
        cur.execute(
            "INSERT INTO tasks (id, title, body, status, created_by, created_at, "
            "workspace_kind, max_retries, priority) VALUES (?,?,?,?,?,?,?,?,?)",
            (tid, body[:400],
             "FLEET MESSAGE from %s at %s — process it like any task: claim it, do the "
             "work, write an artifact, post a receipt.\n\n%s" % (username, now_iso(), body),
             "ready", username, ts, "scratch", 2, 0))
        db.commit()
        db.close()
        return {"id": tid, "status": "ready", "title": body[:400], "created_at": ts,
                "created_by": username}
    except Exception as e:
        return {"id": None, "status": "error", "error": str(e)}


def _artifact_read(path):
    try:
        with open(path, "r", errors="replace") as f:
            return f.read(_ARTIFACT_MAX_BYTES).encode("utf-8", "replace")
    except Exception:
        return None


def universe_data():
    """UNIVERSE API — feedstock for the game screen (/universe). Read-only
    aggregation of existing orchestrator ledgers: discoveries, role-lane
    findings, artifact-backed wallet mints, burn pulse and fleet-comms
    threads. Honest zeros when a ledger is missing — nothing invented."""
    orch = "/srv/bricks/orchestrator"
    out = {"ts": time.time(), "discoveries": [], "findings": [], "mints": [],
           "burn_1h": None, "threads_live": None, "queue_pending": None,
           "comms_threads": [], "latest_discovery": None}
    disc = read_jsonl(os.path.join(orch, "discoveries.jsonl"))
    if isinstance(disc, list):
        rows = [r for r in disc if isinstance(r, dict)]
        rows.sort(key=lambda r: r.get("ts") or 0, reverse=True)
        out["discoveries"] = rows[:12]
        if rows:
            out["latest_discovery"] = rows[0]
    find = read_jsonl(os.path.join(orch, "findings.jsonl"))
    if isinstance(find, list):
        rows = [r for r in find if isinstance(r, dict)]
        rows.sort(key=lambda r: r.get("ts") or 0, reverse=True)
        out["findings"] = rows[:10]
    try:
        wrows = read_jsonl(WALLET) or []
        mints = []
        for r in wrows:
            if not isinstance(r, dict):
                continue
            try:
                bf = float(r.get("bananas"))
            except (TypeError, ValueError):
                continue
            if not r.get("artifact_sha") or bf == 0:
                continue
            mints.append({"ts": r.get("ts"), "iso": r.get("iso"),
                          "person": r.get("person") or r.get("person_id"),
                          "bananas": bf,
                          "artifact_sha": str(r.get("artifact_sha"))[:16]})
        mints.sort(key=lambda m: m.get("ts") or 0, reverse=True)
        out["mints"] = mints[:8]
    except Exception:
        pass
    try:
        with open(os.path.join(orch, "fleet-realtime.json")) as f:
            rt = json.load(f)
        out["burn_1h"] = ((rt.get("burn_ovh") or {}).get("last_1h"))
        out["threads_live"] = (rt.get("ovh") or {}).get("threads")
        out["queue_pending"] = (rt.get("queue") or {}).get("pending")
    except Exception:
        pass
    ct = read_jsonl(os.path.join(orch, "comms.jsonl"))
    if isinstance(ct, list):
        rows = [r for r in ct if isinstance(r, dict)]
        rows.sort(key=lambda r: r.get("ts") or 0, reverse=True)
        out["comms_threads"] = rows[:8]
    return out

def now_data():
    """NOW STRIP — one cheap honest payload for the hero: alive-vs-registered counts,
    top live activities (agent + task), queue velocity, per-brick detail rows.
    Sources: brick-ledger.json + fleet-realtime.json + queue.json. Fast-poll target (<10s)."""
    import re as _re
    now = time.time()
    ledger = _cap_load(CAPACITY_LEDGER)
    realtime = _cap_load(CAPACITY_REALTIME)
    queue = _cap_load(CAPACITY_QUEUE)

    per = (ledger.get("per_brick") if isinstance(ledger, dict) else None) or {}
    if isinstance(per, list):
        per = {(b.get("brick_id") if isinstance(b, dict) else None) or ("brick-%d" % i): b
               for i, b in enumerate(per)}

    bricks, live_n, activities = {}, 0, []
    for name, b in sorted(per.items()):
        if not isinstance(b, dict):
            continue
        hb = b.get("last_heartbeat")
        age_min = (now - hb) / 60.0 if isinstance(hb, (int, float)) and hb > 0 else None
        is_live = bool(b.get("live")) and (age_min is None or age_min <= IDLE_STALE_MIN)
        acc = b.get("accomplishments") or []
        row = {
            "role": b.get("role"),
            "live": is_live,
            "hb_age_min": round(age_min) if age_min is not None else None,
            "capacity_threads": b.get("capacity_threads"),
            "bananas": b.get("bananas_earned", 0),
            "mints": b.get("mints", 0),
            "roi": b.get("roi", 0),
            "accomplishments_n": len(acc),
            "last_activity": str(acc[-1])[:140] if acc else None,
        }
        bricks[str(name)] = row
        if is_live:
            live_n += 1
            activities.append({
                "agent": str(name),
                "kind": "live",
                "task": row["last_activity"] or ("alive — role %s, no task claimed" % (b.get("role") or "?")),
                "age_s": round(age_min * 60) if age_min is not None else None,
            })

    goals = queue.get("goals") if isinstance(queue, dict) else None
    goals = goals if isinstance(goals, list) else []
    done_g = [g for g in goals if isinstance(g, dict) and g.get("status") == "done"]
    pend_g = [g for g in goals if isinstance(g, dict) and g.get("status") == "pending"]

    def _short(g, n=110):
        p = _re.sub(r"\s+", " ", str(g.get("prompt") or "")).strip()
        return (p[:n] + "…") if len(p) > n else p

    nxt = pend_g[-1] if pend_g else None
    if nxt is not None:
        activities.append({"agent": "fleet queue", "kind": "next",
                           "task": "next up: %s — %s" % (nxt.get("id"), _short(nxt, 90)),
                           "age_s": None})
    for g in reversed(done_g[-2:]):
        activities.append({"agent": "fleet queue", "kind": "done",
                           "task": "just shipped: %s" % g.get("id"), "age_s": None})
    activities.sort(key=lambda a: 0 if a["kind"] == "live" else 1)

    rt = realtime if isinstance(realtime, dict) else {}
    registry_rows = rt.get("bricks_registered")
    if registry_rows:
        note = ("%d bricks are real agents in the live ledger; the %s rows in the old registry "
                "are history (Discord era) — not agents." % (len(bricks), registry_rows))
    else:
        note = "%d bricks are real agents in the live ledger." % len(bricks)

    return {
        "ts": now,
        "fleet": {
            "agents": len(bricks),
            "live": live_n,
            "registry_rows": registry_rows,
            "threads_capacity": sum((b.get("capacity_threads") or 0) for b in bricks.values()),
            "note": note,
        },
        "activities": activities[:6],
        "queue": {"total": len(goals), "pending": len(pend_g), "done": len(done_g),
                  "recent_done": [{"id": g.get("id")} for g in reversed(done_g[-3:])]},
        "velocity": {
            "calls_1h": (rt.get("burn_ovh") or {}).get("last_1h"),
            "tokens_1h": (rt.get("burn_ovh") or {}).get("tokens_1h"),
            "threads": (rt.get("ovh") or {}).get("threads"),
            "load": (rt.get("ovh") or {}).get("load"),
        },
        "bricks": bricks,
        "sources": {"ledger": CAPACITY_LEDGER, "queue": CAPACITY_QUEUE, "realtime": CAPACITY_REALTIME},
    }


def moneylive_data():
    """MONEY LIVE — per-minute spend rail (last 60 min, ZERO-FILLED) + 24h free/paid
    split + ROI ticker + burn $/hr + projected daily. Real rows only: measurements.jsonl
    (per-call spend ledger) with router-ledger fallback. Cached 30s (matches the beat's
    auto-refresh). Sparse rows = genuinely quiet fleet — the rail stays continuous."""
    with MONEYLIVE_LOCK:
        if time.time() - moneylive_cache["ts"] < 30 and moneylive_cache["out"] is not None:
            return moneylive_cache["out"]
    now = time.time()
    rows = read_jsonl(MEASUREMENTS)
    source = MEASUREMENTS
    if not rows:
        rows = read_jsonl(LANE_LEDGER)
        source = LANE_LEDGER
    spend_rows = []
    for r in (rows or []):
        if not isinstance(r, dict):
            continue
        ts = r.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        cost = _num(r.get("cost_usd"))
        if cost is None:
            cost = _num(r.get("cost"))
        if cost is None:
            cost = 0.0
        lane = str(r.get("lane") or r.get("lane_id") or "?")
        spend_rows.append({"ts": float(ts), "cost": cost, "lane": lane})

    # --- 60-minute zero-filled rail (oldest -> newest) ---
    rail = []
    m_now = int(now // 60) * 60
    for k in range(59, -1, -1):
        m = m_now - k * 60
        rail.append({"ts": m, "usd": 0.0, "free_usd": 0.0, "paid_usd": 0.0,
                     "calls": 0, "lane": None, "free_or_paid": None})
    by_min = {}
    for s in spend_rows:
        if now - 3600 <= s["ts"] <= m_now + 60:
            by_min.setdefault(int(s["ts"] // 60) * 60, []).append(s)
    for m, sl in by_min.items():
        bucket = next((b for b in rail if b["ts"] == m), None)
        if bucket is None:
            continue
        paid = sum(s["cost"] for s in sl if s["cost"] > 0)
        free = sum(s["cost"] for s in sl if s["cost"] <= 0)
        bucket["usd"] = round(paid + free, 6)
        bucket["paid_usd"] = round(paid, 6)
        bucket["free_usd"] = round(free, 6)
        bucket["calls"] = len(sl)
        dom = max(sl, key=lambda s: s["cost"])
        bucket["lane"] = dom["lane"]
        bucket["free_or_paid"] = "paid" if dom["cost"] > 0 else "free"

    # --- 24h free/paid split (dollars + calls) ---
    d1 = [s for s in spend_rows if s["ts"] >= now - 86400]
    paid_rows = [s for s in d1 if s["cost"] > 0]
    free_rows = [s for s in d1 if s["cost"] <= 0]
    paid_usd = sum(s["cost"] for s in paid_rows)
    free_usd = sum(s["cost"] for s in free_rows)
    total_calls = len(d1)
    free_pct = round(len(free_rows) * 100.0 / total_calls, 1) if total_calls else 0.0

    # --- burn rate ($/hr from last 60 min of real rows; projected daily) ---
    h1 = [s for s in spend_rows if s["ts"] >= now - 3600]
    usd_per_hr = round(sum(s["cost"] for s in h1), 6)
    projected_daily = round(usd_per_hr * 24, 4)

    # --- ROI ticker: clean bananas × peg vs paid spend ---
    w = wallet_data()
    clean = float(w.get("clean_earned_bananas") or 0.0)
    bananas_value = round(clean * MONEY_PEG_USD, 4)
    lifetime_paid = round(sum(s["cost"] for s in spend_rows if s["cost"] > 0), 4)
    ratio = round(bananas_value / paid_usd, 3) if paid_usd > 0 else None
    ltratio = round(bananas_value / lifetime_paid, 3) if lifetime_paid > 0 else None
    if ratio is None:
        label = "no paid spend yet"
    elif ratio > 1.05:
        label = "ROI positive"
    elif ratio < 0.95:
        label = "ROI negative"
    else:
        label = "break-even"

    spend_ts = max((s["ts"] for s in spend_rows), default=None)
    earn_ts = _iso_to_ts(w.get("last_ts"))
    out = {
        "generated_at": now_iso(),
        "window": {"start": now - 3600, "end": now, "minutes": 60, "zero_filled": True},
        "spend_per_min": rail,
        "spend_24h": {
            "free_usd": round(free_usd, 6),
            "paid_usd": round(paid_usd, 6),
            "total_usd": round(paid_usd + free_usd, 6),
            "calls": total_calls, "calls_free": len(free_rows), "calls_paid": len(paid_rows),
            "free_pct": free_pct,
            "paid_pct": round(100.0 - free_pct, 1) if total_calls else 0.0,
        },
        "roi": {
            "bananas_clean": clean,
            "bananas_value_usd": bananas_value,
            "peg_usd_per_banana": MONEY_PEG_USD,
            "paid_spend_usd": round(paid_usd, 6),
            "roi_ratio": ratio,
            "roi_label": label,
            "lifetime_paid_usd": lifetime_paid,
            "lifetime_roi_ratio": ltratio,
            "note": ("banana value = clean-earned bananas × peg. MONEY LIVE peg $0.01 "
                     "(2026-08-25 spec); /api/data roi uses the v1.1 rate-card peg $0.012. "
                     "roi_ratio = value vs paid spend last 24h (live window); "
                     "lifetime_roi_ratio = value vs ALL paid spend since the ledger started."),
        },
        "burn_rate": {
            "usd_per_hr": usd_per_hr,
            "usd_per_hr_calls": len(h1),
            "projected_daily": projected_daily,
            "projected_daily_note": ("last-60-min spend × 24 — projection at the current "
                                     "rate; actual 24h = spend_24h.total_usd"),
            "actual_24h_usd": round(paid_usd + free_usd, 6),
        },
        "last_activity": {
            "spend_ts": spend_ts,
            "spend_age_s": round(now - spend_ts, 1) if spend_ts else None,
            "earn_ts": earn_ts,
            "earn_age_s": round(now - earn_ts, 1) if earn_ts else None,
        },
        "coverage": {
            "source": source,
            "rows_total": len(spend_rows),
            "rows_used_24h": len(d1),
            "rows_used_60m": len(h1),
            "note": ("sparse rows = genuinely quiet fleet, not missing data; the 60-min "
                     "rail is zero-filled so it renders as one continuous strip"),
        },
        "note": ("MONEY LIVE — every $ is a real billed row from the per-call spend "
                 "ledger (measurements.jsonl, router-ledger fallback). Nothing invented."),
    }
    moneylive_cache["ts"] = time.time()
    moneylive_cache["out"] = out
    return out


# ---------------------------------------------------------------- fleet comms (v11, 2026-08-25)
# khalid 2026-08-25 (verbatim): "Still I don't see you communicating with fleet and 0 transparency
# between you all. We talked about shared mcp and shared data and toolings. I see nothing."
# /api/fleetcomms — the LIVE machine-to-machine conversation layer, made visible:
#   relay     — agent-relay.jsonl stream (who said what to whom, when) — the shared bus
#   mcp       — fleet-data MCP live probe: /health + JSON-RPC tools/list (no tokens exposed)
#   agents    — per-agent last-seen derived from the relay + heartbeat + /proc (real signals)
#   ox        — the two cloud ox instances (ox-alpha, OxBaby) via the peer-actions channel
#   dropbox   — relay_sync git drop-box mirror state (last pull commit / push count)
# Real data only; nothing invented; tokens/keys/IPs never leave the box.
PEER_LOG = "/srv/vault/drops/peer-actions.log"   # channel-level ox activity (peer=verb; receipts carry oxa/oxb)
MCP_HEALTH_URL = "http://127.0.0.1:8004/health"
MCP_URL = "http://127.0.0.1:8004/mcp"
MCP_TIMEOUT = 3
RELAY_SYNC_STATE = "/srv/bricks/orchestrator/.relay-sync-state.json"
_fc_cache = {"ts": 0, "out": None}
FC_LOCK = threading.Lock()

AGENT_META = {
    "brick": {"name": "Brick", "color": "brick"},
    "cloud-agent": {"name": "Cloud agent", "color": "cloud"},
    "agi": {"name": "AGI", "color": "agi"},
    "ox-alpha": {"name": "ox-alpha", "color": "cloud"},
    "oxalpha": {"name": "ox-alpha", "color": "cloud"},
    "oxbaby": {"name": "OxBaby", "color": "cloud"},
    "da": {"name": "DA", "color": "agi"},
    "rebel": {"name": "Rebel", "color": "agi"},
    "hermes-local": {"name": "hermes-local", "color": "cloud"},
    "brock": {"name": "Brock", "color": "cloud"},
    "khalid": {"name": "khalid", "color": "human"},
    "system": {"name": "system", "color": "system"},
}


def _mcp_token():
    """Fleet-data MCP bearer token — read from the watchdog script env line; never logged."""
    try:
        with open("/srv/build/fleet-dashboard/fleet_mcp_watchdog.sh") as f:
            for line in f:
                m = re.search(r'FLEET_MCP_TOKEN="([^"]+)"', line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return ""


def mcp_probe():
    """Live fleet-data MCP probe: GET /health (no auth) + JSON-RPC tools/list (Bearer).
    stateless_http server -> no session id round-trip needed. Never returns the token."""
    out = {"status": "down", "health": None, "tools": [], "tool_count": 0, "error": None}
    try:
        with urllib.request.urlopen(MCP_HEALTH_URL, timeout=MCP_TIMEOUT) as r:
            if r.status == 200:
                try:
                    out["health"] = json.loads(r.read().decode())
                except Exception:
                    out["health"] = {"raw": "ok"}
            else:
                out["error"] = f"health http {r.status}"
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    tok = _mcp_token()
    if tok:
        try:
            for mid, method in (("1", "initialize"), ("2", "tools/list")):
                payload = {"jsonrpc": "2.0", "id": mid, "method": method,
                           "params": ({"protocolVersion": "2025-03-26", "capabilities": {},
                                       "clientInfo": {"name": "fleet-dashboard", "version": "1"}}
                                      if method == "initialize" else {})}
                req = urllib.request.Request(MCP_URL, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("Accept", "application/json, text/event-stream")  # MCP requires both
                req.add_header("Authorization", "Bearer " + tok)
                with urllib.request.urlopen(req, data=json.dumps(payload).encode(), timeout=MCP_TIMEOUT) as r:
                    raw = r.read().decode()
                # FastMCP answers SSE (event: message\ndata: {...}) even when JSON is accepted
                data = None
                if raw.lstrip().startswith("event:") or "\ndata:" in raw:
                    for line in raw.splitlines():
                        if line.startswith("data:"):
                            data = json.loads(line[5:].strip())
                            break
                else:
                    data = json.loads(raw)
                if data is None:
                    raise ValueError("empty MCP response")
            tools = ((data.get("result") or {}).get("tools") or []) if isinstance(data, dict) else []
            out["tools"] = [t.get("name") for t in tools if t.get("name")]
            out["tool_count"] = len(out["tools"])
        except Exception as e:
            out["tools_error"] = f"{type(e).__name__}: {e}"
    healthy = bool(out["health"] and out["health"].get("status") == "ok")
    if healthy and out["tool_count"] and not out.get("tools_error"):
        out["status"] = "healthy"
    elif healthy:
        out["status"] = "degraded"  # health ok but tools listing failed
    return out


def _relay_participants(rows):
    """Per-agent last-seen from the relay: latest OUTGOING message (own voice) and latest
    DIRECT incoming (addressed by name). Broadcasts to 'all' prove the sender spoke, not that
    anyone answered, so they never count as a per-agent signal."""
    by = {}
    for r in (rows or []):
        if not isinstance(r, dict):
            continue
        f = str(r.get("from") or "").lower()
        t = str(r.get("to") or "").lower()
        ts = _iso_to_ts(r.get("ts"))
        if ts is None:
            continue
        for p in (f, t):
            if not p or p == "all":
                continue
            a = by.setdefault(p, {"out_ts": None, "in_ts": None, "last_body": None})
            if p == f:
                if a["out_ts"] is None or ts > a["out_ts"]:
                    a["out_ts"] = ts
                    a["last_body"] = str(r.get("body") or "")
            elif a["in_ts"] is None or ts > a["in_ts"]:
                a["in_ts"] = ts
    return by


def fleetcomms_agents(rows, hb_last):
    """agents strip: real last-seen per agent, honest status. Sources: relay (all agents),
    heartbeat registry (ox-alpha as hermes-local), /proc (Brick's orchestrator process)."""
    now = time.time()
    running = {p.lower() for p in fleet_processes().get("processes", [])}
    by = _relay_participants(rows)
    out = []
    for pid in sorted(by.keys()):
        a = by[pid]
        meta = AGENT_META.get(pid, {"name": pid, "color": "cloud"})
        last_ts = a["out_ts"] or a["in_ts"]
        src = "relay"
        if pid == "hermes-local" and hb_last.get("hermes-local"):
            hb_ts = hb_last["hermes-local"]
            if last_ts is None or hb_ts > last_ts:
                last_ts = hb_ts
                src = "heartbeat"
        if pid == "brick" and "orchestrator.py" in running:
            last_ts = now
            src = "process"
        age = (now - last_ts) if last_ts else None
        if age is None:
            status = "unknown"
        elif age <= FRESH_SEC:
            status = "active"
        elif age <= SEEN7D_SEC:
            status = "idle"
        else:
            status = "unknown"
        body = a["last_body"] or ""
        if body:
            last_msg = strip_md(body)[:130]
        elif a["in_ts"]:
            last_msg = "(addressed, no outgoing message yet)"
        else:
            last_msg = "(no messages)"
        out.append({
            "id": pid, "name": meta["name"], "color": meta["color"],
            "last_seen": (datetime.datetime.fromtimestamp(last_ts, datetime.UTC).isoformat()
                          if last_ts else None),
            "last_seen_ts": last_ts, "age_s": int(age) if age is not None else None,
            "status": status, "signal": src, "last_message": last_msg,
        })
    out.sort(key=lambda a: -(a["last_seen_ts"] or 0))
    return out


def ox_instances():
    """The two cloud ox instances (ox-alpha, OxBaby) run on Nous cloud — no process on this box.
    They reach the fleet through the git drop-box + the peer-actions channel; receipts in that
    log carry oxa/oxb markers. Last sync = their most recent peer action. Honest: channel-level
    signal (their own posted actions), not a live heartbeat."""
    try:
        with open(PEER_LOG) as f:
            lines = f.readlines()
    except OSError:
        return [{"name": "ox-alpha", "state": "unknown", "last_sync": None,
                 "last_action": None, "signal": "peer-actions.log missing"}]
    now = time.time()
    out = []
    for name, rec_marker, name_hay in (("ox-alpha", "receipt-oxa-", "ox-alpha"),
                                       ("OxBaby", "receipt-oxb-", "oxbaby")):
        r_ts, r_label = None, None   # explicit receipt marker = their own signed action
        n_ts, n_label = None, None   # name mention fallback
        for line in lines:
            head, _, rest = line.partition(" peer=")
            verb = rest.split(" ", 1)[0].strip() if rest else ""
            body = rest.split(" ", 1)[1] if " " in rest else ""
            hay = line.lower()
            if not head.strip():
                continue
            if rec_marker in hay and (r_ts is None or head.strip() > r_ts):
                r_ts = head.strip()
                r_label = (verb + (": " + strip_md(body)[:80] if body else "")).strip()
            if name_hay in hay and (n_ts is None or head.strip() > n_ts):
                n_ts = head.strip()
                n_label = (verb + (": " + strip_md(body)[:80] if body else "")).strip()
        last_s = r_ts or n_ts
        label = r_label or n_label
        ts = _iso_to_ts(last_s.replace("Z", "+00:00")) if last_s else None
        age = (now - ts) if ts else None
        if age is None:
            state = "unknown"
        elif age <= 600:
            state = "active"
        elif age <= 86400:
            state = "idle"
        else:
            state = "silent"
        out.append({"name": name, "state": state, "last_sync": last_s,
                    "last_sync_ts": ts, "age_s": int(age) if age is not None else None,
                    "last_action": label, "signal": "peer-actions.log"})
    return out


def fleetcomms_data():
    """/api/fleetcomms payload — the shared comms/data/tooling layer, made visible. Cached 15s
    (matches the 20s beat refresh + the 30s main refresh without hammering the MCP probe)."""
    with FC_LOCK:
        if time.time() - _fc_cache["ts"] < 15 and _fc_cache["out"] is not None:
            return _fc_cache["out"]
    now = time.time()
    rows = read_jsonl(RELAY) or []
    hb = heartbeat_data()
    hb_last = {r["id"]: r["last_ts"] for r in
               (hb.get("live", []) + hb.get("idle", []) + hb.get("silent", []))} if hb.get("status") == "ok" else {}
    msgs = []
    for m in reversed(rows[-40:]):
        body = str(m.get("body") or "")
        msgs.append({
            "ts": m.get("ts"),
            "ts_epoch": _iso_to_ts(m.get("ts")),
            "from": str(m.get("from") or "?"),
            "to": str(m.get("to") or "?"),
            "kind": str(m.get("kind") or "msg"),
            "body_preview": strip_md(body)[:160],
            "body_len": len(body),
            "receipt": str(m.get("receipt") or "")[:24],
        })
    last_ex = max((_iso_to_ts(m.get("ts")) for m in rows if _iso_to_ts(m.get("ts"))), default=None)
    last60 = [m for m in rows if _iso_to_ts(m.get("ts")) and now - _iso_to_ts(m.get("ts")) <= 60]
    drop = {}
    try:
        with open(RELAY_SYNC_STATE) as f:
            st = json.load(f)
        drop = {"status": "ok",
                "last_pull_commit": str(st.get("last_pull_commit") or "")[:10] or None,
                "last_push_count": st.get("last_push_count"),
                "state_age_min": round((now - os.path.getmtime(RELAY_SYNC_STATE)) / 60.0, 1),
                "note": "relay_sync.py mirrors agent-relay.jsonl <-> bawes-fleet repo drop-box every 60s (cloud agents see it <=60s)"}
    except Exception:
        drop = {"status": "missing"}
    out = {
        "generated_at": now_iso(),
        "relay": {"status": "ok" if rows else "missing", "total": len(rows),
                  "messages": msgs,
                  "note": "agent-relay.jsonl — the shared machine-to-machine bus. Every row is one real exchange."},
        "mcp": mcp_probe(),
        "agents": fleetcomms_agents(rows, hb_last),
        "ox_instances": ox_instances(),
        "dropbox": drop,
        "pulse": {
            "last_60s": len(last60),
            "last_exchange_ts": last_ex,
            "last_exchange_age_s": round(now - last_ex, 1) if last_ex else None,
            "last_exchange_iso": (datetime.datetime.fromtimestamp(last_ex, datetime.UTC).isoformat()
                                  if last_ex else None),
        },
        "note": ("FLEET COMMS — the shared layer, live: agent relay stream + fleet-data MCP "
                 "health/tools + per-agent last-seen + ox instance state. Real data only; "
                 "tokens and keys never leave the box."),
    }
    _fc_cache["ts"] = now
    _fc_cache["out"] = out
    return out


def build_payload(user=None):
    w = wallet_data()
    money = money_data(w)
    hb = heartbeat_data()
    gh = github_data()
    return {
        "generated_at": now_iso(),
        "brand": {"name": "BAWES", "tagline": "People and AI Living Together", "url": "bawes.net"},
        "session": {"user": user.get("username") if user else None,
                    "role": user.get("role") if user else None,
                    "lanes": user_lanes(user) if user else []},
        "roles": roles_data(),
        "money": money,
        "bricks": {"heartbeat": hb, "registry": registry_data()},
        "roi": roi_data(w, money),
        "evolution": {
            "vector": vector_series(),
            "wallet": wallet_series(w),
            "prs": pr_series(gh),
            "spend": spend_series(money),
            "door_cost": money.get("door_cost", {}),
            "note": "no historical snapshots predate these files — history accrues from now for anything not already derivable",
        },
        "threads": threads_data(),
        "fleets": fleet_status(),
        "wallet": w,
        "rate_card": {"status": "n/a"},
        "velocity": gh,
        "epics": epics_data(),
        "vector_store": vector_data(),
        "approvals": approvals_data(),
        "who": who_data(),
        "burn": burn_data(),
        "lanes": lane_state(),
        "lane_control": {"can_control": bool(user and user.get("role") == "owner"),
                         "file": LANE_CONTROL,
                         "last_control": lane_control_rows()[-1] if lane_control_rows() else None,
                         "note": "owner-only kill switch — contributor toggles get 403"},
        "achievements": achievements_data(),
        "dispatches": {"count": len(read_jsonl(DISPATCHES) or []), "file": DISPATCHES},
        "sources": {
            "wallet": WALLET, "heartbeat": HEARTBEAT, "registry": REGISTRY,
            "vector": VECTOR, "door_cost": DOOR_COST, "spend": SPEND,
            "queue": QUEUE_FALLBACKS[0], "github": f"api.github.com/repos/{REPO}/pulls",
            "door_db": DOOR_DB, "users": USERS_FILE,
            "approvals": APPROVALS, "decisions_ledger": DECISIONS_LEDGER,
            "lanes": LANES, "lane_ledger": LANE_LEDGER, "lane_control": LANE_CONTROL,
            "kanban_board_db": KANBAN_BOARD_DB,
        },
    }


# ---------------------------------------------------------------- http
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    @staticmethod
    def _hdr_items(extra):
        """Extra headers may be a dict OR a list of (name, value) tuples (two
        Set-Cookie headers are needed on the OAuth callback success path)."""
        if isinstance(extra, dict):
            return list(extra.items())
        return list(extra or [])

    def _send(self, code, body, ctype, extra_headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-BAWES-Dashboard", "v5")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        for k, v in self._hdr_items(extra_headers):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location, extra_headers=None):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        for k, v in self._hdr_items(extra_headers):
            self.send_header(k, v)
        self.end_headers()

    def _login_url(self):
        q = urllib.parse.urlparse(self.path)
        nxt = safe_next(q.query and dict(urllib.parse.parse_qsl(q.query)).get("next"))
        return f"/login?next={urllib.parse.quote(nxt)}" if nxt != "/" else "/login"

    def _cookie_value(self, name):
        """Extract a single cookie value from the raw Cookie header."""
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return ""

    def _require_session(self):
        """Returns (user, None) or (None, response-needed). Fleet agents authenticate
        with `Authorization: Bearer <agent-api.token>` on /api/* (machine identity —
        contributor/read-only role, audited in agent-api.usage.log)."""
        user = verify_session(self._cookie_value(SESSION_COOKIE))
        if not user and self.path.startswith("/api/"):
            user = self._agent_bearer_user()
        if user:
            return user, None
        if self.path.startswith("/api/"):
            self._send(401, json.dumps({"ok": False, "error": "authentication required — sign in at /login"}).encode(),
                       "application/json")
        else:
            self._redirect(self._login_url())
        return None, True

    def _agent_bearer_user(self):
        """Bearer == agent-api.token -> synthetic contributor user (machine identity)."""
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        presented = auth[len("Bearer "):].strip()
        if not presented or not hmac.compare_digest(presented, agent_token()):
            return None
        agent = re.sub(r"[^A-Za-z0-9_-]", "", self.headers.get("X-Agent-Id") or "")[:32]
        agent_usage_log(self.path.split("?")[0], agent or AGENT_SESSION_USER)
        return {"username": AGENT_SESSION_USER, "role": "contributor", "auth": "agent-token"}

    # ------------------------------------------------------------ GET
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return

        if path == "/healthz":
            self._send(200, b"ok", "text/plain")
            return

        if path == "/api/fleet-answer":
            # PUBLIC canonical fleet answer — the single truth endpoint any brick
            # can curl from anywhere (same pattern as Vast/OpenRouter APIs).
            try:
                import json as _j
                with open("/srv/bricks/orchestrator/fleet-answer.json") as _f:
                    _d = _j.load(_f)
                _d["canonical_rule"] = "Every brick answers from this endpoint ONLY. Divergence = broken brick."
                self._send(200, _j.dumps(_d, default=str).encode(), "application/json")
                return
            except Exception as _e:
                self._send(500, _j.dumps({"error": f"fleet-answer unavailable: {_e}"}).encode(), "application/json")
                return

        if path == "/api/fleet-realtime":
            # PUBLIC realtime fleet snapshot — who's alive, box state, queue.
            try:
                import json as _jr
                with open("/srv/bricks/orchestrator/fleet-realtime.json") as _fr:
                    _rt = _jr.load(_fr)
                self._send(200, _jr.dumps(_rt, default=str).encode(), "application/json")
                return
            except Exception as _er:
                self._send(500, _jr.dumps({"error": f"fleet-realtime unavailable: {_er}"}).encode(), "application/json")
                return

        if path == "/api/webhook" and self.command == "POST":
            import json as _jw
            try:
                _len = int(self.headers.get("Content-Length", 0))
                _body = json.loads(self.rfile.read(_len).decode()) if _len else {}
                _tok = self.headers.get("Authorization", "").replace("Bearer ", "")
                _good = False
                try:
                    _good = _tok == open("/srv/vault/fleet-tokens/agent-api.token").read().strip()
                except Exception:
                    pass
                if not _good:
                    self._send(401, json.dumps({"ok": False, "error": "bad token"}).encode(), "application/json")
                    return
                _row = dict(_body)
                _row["received"] = int(time.time())
                with open("/srv/bricks/orchestrator/webhook-events.jsonl", "a") as _f:
                    _f.write(json.dumps(_row) + "\n")
                self._send(200, json.dumps({"ok": True, "event": _row.get("event"), "received": _row["received"]}).encode(), "application/json")
            except Exception as _ew:
                self._send(500, json.dumps({"ok": False, "error": str(_ew)}).encode(), "application/json")
            return

        if path == "/api/fleet/report":
            # PUBLIC canonical fleet report (Vast-API style): one URL, one truth.
            import json as _j2, subprocess as _sp2
            try:
                _out = _sp2.run(["/usr/bin/python3", "/srv/bricks/orchestrator/fleet_report_rt.py"],
                                capture_output=True, text=True, timeout=15)
                self._send(200, json.dumps({"realtime": True, "report": _out.stdout}).encode(), "application/json")
            except Exception as _e2:
                self._send(200, json.dumps({"realtime": False, "error": str(_e2)}).encode(), "application/json")
            return

        if path == "/api/public":
            # PUBLIC storefront endpoint — no auth. Aggregates only (public_data
            # is safe by construction); every other /api/* route stays behind the
            # session gate below.
            self._send(200, json.dumps(public_data(), ensure_ascii=False).encode(),
                       "application/json")
            return

        if path == "/api/observability":
            self._send(200, json.dumps(observability_api(), ensure_ascii=False).encode(), "application/json")
            return

        if path == "/api/events":
            # REAL TIME — SSE stream: pushes player/state/trust/feed on change.
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                import time as _t
                _last = {}
                _files = {
                    "player": "/srv/bricks/orchestrator/player-profile.json",
                    "state": "/srv/bricks/orchestrator/fleet-state.json",
                    "trust": "/srv/bricks/orchestrator/fleet-trust.json",
                    "digest": "/srv/bricks/orchestrator/morning-digest.json",
                }
                _deadline = _t.time() + 55
                while _t.time() < _deadline:
                    for _k, _p in _files.items():
                        try:
                            _m = int(__import__("os").path.getmtime(_p))
                            if _last.get(_k) != _m:
                                _last[_k] = _m
                                _d = json.load(open(_p))
                                self.wfile.write(f"event: {_k}\ndata: {json.dumps(_d)}\n\n".encode())
                                self.wfile.flush()
                        except Exception:
                            pass
                    _t.sleep(1.5)
                self.wfile.write(b"event: keepalive\ndata: {}\n\n")
                self.wfile.flush()
            except Exception:
                pass
            return
        if path == "/api/player-card":
            try:
                import os as _os
                _data = {}
                for _f in ("/srv/bricks/orchestrator/player-profile.json",
                           "/srv/bricks/orchestrator/fleet-trust.json",
                           "/srv/bricks/orchestrator/morning-digest.json"):
                    if _os.path.exists(_f):
                        _data[_os.path.basename(_f).replace(".json", "")] = json.load(open(_f))
            except Exception as _e:
                _data = {"error": str(_e)}
            self._send(200, json.dumps(_data, ensure_ascii=False).encode(), "application/json")
        if path == "/api/player-world":
            # PUBLIC player world — characters/leaderboard/social, no secrets.
            self._send(200, json.dumps(player_world_api(), ensure_ascii=False).encode(),
                       "application/json")
            return

        if path == "/panel/velocity":
            # VELOCITY + EVOLUTION panel — public like the storefront: the page is
            # static markup with zero secrets, and its data source (/api/velocity)
            # serves sanitised aggregates only (basenames, no keys/tokens/IPs/person
            # ids/absolute paths). khalid wants the burn->verify->mint loop visible
            # on arrival. To gate it later, move these two branches below the
            # _require_session() call — nothing else changes.
            self._send(200, velocity_panel_html().encode(), "text/html; charset=utf-8")
            return

        if path == "/api/velocity":
            self._send(200, json.dumps(velocity_data(), ensure_ascii=False).encode(),
                       "application/json")
            return

        if path == "/login":
            try:
                html = open(os.path.join(BASE, "login.html"), "rb").read()
                self._send(200, html, "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(500, b"login.html missing", "text/plain")
            return

        if path == "/logout":
            # clear the session cookie and go back to the login page
            self._redirect("/login", {"Set-Cookie": clear_cookie_header()})
            return

        # Discord OAuth2 login (public routes — no session needed to START).
        if path == "/oauth/discord":
            self._do_oauth_start()
            return

        if path == "/oauth/discord/callback":
            self._do_oauth_callback()
            return

        # ROOT: the public storefront (public.html) when not signed in; the full
        # dashboard (index.html) when a valid session exists. No more 302 → /login
        # for anonymous visitors — the fleet website is now impressive on arrival.
        if path == "/" or path == "/index.html":
            user = verify_session(self._cookie_value(SESSION_COOKIE))
            fname = "universe.html" if user else "public.html"
            try:
                html = open(os.path.join(BASE, fname), "rb").read()
                self._send(200, html, "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(500, f"{fname} missing".encode(), "text/plain")
            return

        user, denied = self._require_session()
        if denied:
            return

        if path == "/approvals":
            try:
                html = open(os.path.join(BASE, "approvals.html"), "rb").read()
                self._send(200, html, "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(500, b"approvals.html missing", "text/plain")
        elif path == "/api/approvals":
            payload = approvals_data()
            for c in payload.get("cards", []):
                c["can_act"] = can_decide(user, c)
            payload["session"] = {"user": user.get("username"), "role": user.get("role"),
                                  "lanes": user_lanes(user)}
            payload["my_pending"] = sum(1 for c in payload.get("cards", [])
                                        if c.get("status") == "PENDING" and can_decide(user, c))
            self._send(200, json.dumps(payload).encode(), "application/json")
        elif path == "/comms":
            try:
                html = open(os.path.join(BASE, "comms.html"), "rb").read()
                self._send(200, html, "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(500, b"comms.html missing", "text/plain")
        elif path == "/api/comms":
            payload = relay_rows(20)
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            payload["rate"] = {"owner_per_min": RATE_OWNER_PER_MIN,
                               "other_per_hour": RATE_OTHER_PER_HOUR}
            self._send(200, json.dumps(payload).encode(), "application/json")
        elif path == "/api/data":
            payload = json.dumps(build_payload(user)).encode()
            self._send(200, payload, "application/json")
        elif path == "/api/lane-state":
            payload = lane_state()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            payload["can_control"] = user.get("role") == "owner"
            payload["burn"] = burn_data()
            payload["last_control"] = lane_control_rows()[-1] if lane_control_rows() else None
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/ecosystem":
            payload = ecosystem_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/network":
            payload = network_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/portfolio":
            payload = portfolio_data(user)
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/timeflow":
            payload = timeflow_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/moneylive":
            payload = moneylive_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/fleetlive":
            payload = fleetlive_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/now":
            # NOW STRIP API — cheap hero payload (honest counts + activities). Fast-poll target.
            payload = now_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/fleetcomms":
            # FLEET COMMS — the shared layer, visible: relay stream + MCP health/tools +
            # per-agent last-seen + ox instance state. Same session gate as every /api/*.
            payload = fleetcomms_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/time-engine":
            # TIME ENGINE API — VIB/BRK accounting + Switcher states + myth ledger.
            payload = timeengine_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/panel/time-engine":
            # TIME ENGINE PANEL — standalone dark gold/teal page (ops-gated like
            # /approvals + /comms). Fresh payload embedded server-side; JS re-polls.
            self._send(200, timeengine_page(timeengine_data()).encode(),
                       "text/html; charset=utf-8")
        elif path == "/api/roles":
            # ROLES & PEOPLE — owner-only (grant/revoke is the owner's call). 403 for
            # everyone else; the read-only roster rides in /api/data -> roles instead.
            if user.get("role") != "owner":
                self._send(403, json.dumps({"ok": False,
                                            "error": "owner role required — only the owner grants roles"}).encode(),
                           "application/json")
            else:
                payload = roles_data()
                payload["session"] = {"user": user.get("username"), "role": user.get("role"),
                                      "lanes": user_lanes(user)}
                self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/panel/capacity":
            # CAPACITY BOARD + epic tracker panel (session-gated like /approvals).
            try:
                html = open(os.path.join(BASE, "capacity.html"), "rb").read()
        elif path == "/fleet-live":
            try:
                html = open(os.path.join(BASE, "fleet-live.html"), "rb").read()
                self._send(200, html, "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(500, b"fleet-live.html missing", "text/plain")
                self._send(200, html, "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(500, b"capacity.html missing", "text/plain")
        elif path == "/api/capacity":
            payload = capacity_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/universe":
            # UNIVERSE — the game screen: living floor, play, ticker, talk,
            # multiplayer, discover. Session-gated like /approvals; static page;
            # data via /api/* endpoints (now/player-card/player-world/approvals/
            # comms/universe).
            try:
                html = open(os.path.join(BASE, "universe.html"), "rb").read()
                self._send(200, html, "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(500, b"universe.html missing", "text/plain")
        elif path == "/api/universe":
            # UNIVERSE API — discoveries/findings/mints/burn pulse/comms
            # threads for the game screen. Read-only aggregation.
            payload = universe_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/mission":
            # MISSION first-screen payload — NOW / GOALS / VELOCITY / BRICKS.
            payload = mission_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/floor":
            # THE FLOOR — the 2D universe view (auth-gated like every dashboard page).
            try:
                html = open(os.path.join(BASE, "floor.html"), "rb").read()
                self._send(200, html, "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(500, b"floor.html missing", "text/plain")
        elif path == "/api/floor":
            # THE FLOOR payload — every brick as an avatar, live events from REAL receipts
            # (last 10 min), the player (khalid) with level/XP, honesty block. Auth-gated
            # like every /api/* route; no secrets, no fake activity.
            payload = floor_data()
            payload["session"] = {"user": user.get("username"), "role": user.get("role")}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif path == "/api/brick/clone":
            # Clone a brick: /api/brick/clone?id=<source> — appends a new registry
            # identity copied from the source (owner-only; audit-logged).
            if user.get("role") != "owner":
                self._send(403, json.dumps({"ok": False,
                                            "error": "owner role required — only the owner spawns bricks"}).encode(),
                           "application/json")
            else:
                q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
                src = (q.get("id") or [""])[0]
                ok, payload = brick_clone_api(src, user)
                payload["ok"] = ok
                self._send(200 if ok else 400, json.dumps(payload, ensure_ascii=False).encode(),
                           "application/json")
        elif path == "/api/brick/wake":
            # Wake a brick: /api/brick/wake?id=<brick> — marks its registry identity
            # live (owner-only; audit-logged). Registry live = registration claim,
            # not a running process yet.
            if user.get("role") != "owner":
                self._send(403, json.dumps({"ok": False,
                                            "error": "owner role required — only the owner wakes bricks"}).encode(),
                           "application/json")
            else:
                q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
                bid = (q.get("id") or [""])[0]
                ok, payload = brick_wake_api(bid, user)
                payload["ok"] = ok
                self._send(200 if ok else 400, json.dumps(payload, ensure_ascii=False).encode(),
                           "application/json")
        elif path.startswith("/api/brick/"):
            # BRICK DEEP-DIVE — one brick's whole story: profile, thought thread
            # (its relay messages), receipts, artifacts, current task, stats.
            bid = urllib.parse.unquote(path[len("/api/brick/"):])
            if bid and "/" not in bid:
                payload = brick_data(bid)
                if not payload.get("found"):
                    self._send(404, json.dumps({"ok": False, "error": "brick not found",
                                                "brick_id": bid}, ensure_ascii=False).encode(),
                               "application/json")
                else:
                    payload["session"] = {"user": user.get("username"), "role": user.get("role")}
                    self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
            else:
                self._send(404, b"not found", "text/plain")
        elif path.startswith("/api/task/"):
            # TASK DEEP-DIVE — status, owner, timestamps, artifact, receipt, relay thread.
            tid = urllib.parse.unquote(path[len("/api/task/"):])
            if tid and "/" not in tid:
                payload = task_data(tid)
                if not payload.get("found"):
                    self._send(404, json.dumps({"ok": False, "error": "task not found",
                                                "task_id": tid}, ensure_ascii=False).encode(),
                               "application/json")
                else:
                    payload["session"] = {"user": user.get("username"), "role": user.get("role")}
                    self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
            else:
                self._send(404, b"not found", "text/plain")
        elif path == "/api/artifact":
            # Session-gated text view of a brick/task's OWN artifacts. Basename whitelist —
            # only files the resolver provably attributes to that brick/task are servable.
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            fname = (q.get("file") or [""])[0]
            brick = (q.get("brick") or [""])[0]
            task = (q.get("task") or [""])[0]
            m = {}
            if brick:
                m = _brick_artifact_map(brick)
            elif task:
                m = _task_artifact_map(task)
            if (not fname or "/" in fname or "\\" in fname or ".." in fname
                    or fname not in m or not os.path.isfile(m[fname])):
                self._send(404, b"artifact not found", "text/plain")
                return
            data = _artifact_read(m[fname])
            if data is None:
                self._send(500, b"artifact unreadable", "text/plain")
                return
            ctype = "text/markdown; charset=utf-8" if fname.endswith((".md", ".markdown")) else "text/plain; charset=utf-8"
            self._send(200, data, ctype)
        else:
            self._send(404, b"not found", "text/plain")

    # ------------------------------------------------------------ POST
    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/api/invite":
            import json as _ji, uuid as _ui
            try:
                _len = int(self.headers.get("Content-Length", 0))
                _body = json.loads(self.rfile.read(_len).decode()) if _len else {}
                _name = str(_body.get("name", "")).strip()
                _role = str(_body.get("role", "Builder")).strip()
                if not _name:
                    self._send(400, json.dumps({"ok": False, "error": "name required"}).encode(), "application/json")
                    return
                _bid = _name.lower().replace(" ", "-") + "-brick-001"
                _now = int(time.time())
                # 1. wallet namespace
                _wpath = "/srv/bricks/register/wallet.jsonl"
                _rows = []
                try:
                    _s = open(_wpath).read().strip()
                    if _s.startswith("["):
                        _rows = json.loads(_s)
                    else:
                        _rows = [json.loads(l) for l in _s.splitlines() if l.strip()]
                except Exception:
                    pass
                if not any(r.get("person_id") == _bid for r in _rows):
                    _rows.append({"kind": "brick-issue", "person_id": _bid, "owner": _name,
                                  "bananas": 0, "note": f"brick born via app invite for {_name}", "ts": _now})
                    with open(_wpath, "w") as _f:
                        for r in _rows:
                            _f.write(json.dumps(r) + "\n")
                # 2. player-world character
                _pw = {}
                try:
                    _pw = json.load(open("/srv/bricks/orchestrator/player-world.json"))
                except Exception:
                    pass
                _chars = _pw.get("characters", [])
                if not any(c.get("id") == _bid for c in _chars):
                    _chars.append({"id": _bid, "name": _name, "role": _role, "level": 1, "xp": 0,
                                   "bananas": 0, "rank": 0, "status": "ONBOARDING", "invite_ready": True})
                    _pw["characters"] = _chars
                    _pw["updated"] = _now
                    with open("/srv/bricks/orchestrator/player-world.json", "w") as _f:
                        json.dump(_pw, _f, indent=1)
                self._send(200, json.dumps({"ok": True, "brick": _bid, "name": _name,
                                            "invite_link": f"https://fleet.bawes.net/join?brick={_bid}"}).encode(), "application/json")
            except Exception as _ei:
                self._send(500, json.dumps({"ok": False, "error": str(_ei)}).encode(), "application/json")
            return

        if path == "/api/webhook":
            import json as _jw
            try:
                _len = int(self.headers.get("Content-Length", 0))
                _body = json.loads(self.rfile.read(_len).decode()) if _len else {}
                _tok = self.headers.get("Authorization", "").replace("Bearer ", "")
                _good = False
                try:
                    _good = _tok == open("/srv/vault/fleet-tokens/agent-api.token").read().strip()
                except Exception:
                    pass
                if not _good:
                    self._send(401, json.dumps({"ok": False, "error": "bad token"}).encode(), "application/json")
                    return
                _row = dict(_body)
                _row["received"] = int(time.time())
                with open("/srv/bricks/orchestrator/webhook-events.jsonl", "a") as _f:
                    _f.write(json.dumps(_row) + "\n")
                self._send(200, json.dumps({"ok": True, "event": _row.get("event"), "received": _row["received"]}).encode(), "application/json")
            except Exception as _ew:
                self._send(500, json.dumps({"ok": False, "error": str(_ew)}).encode(), "application/json")
            return

        if path == "/login":
            self._do_login()
            return

        user, denied = self._require_session()
        if denied:
            return

        if path == "/api/comms":
            self._do_comms(user)
            return

        if path == "/api/lane-control":
            self._do_lane_control(user)
            return

        if path == "/api/roles":
            self._do_roles(user)
            return

        if path == "/api/approvals/request":
            self._do_approval_request(user)
            return

        if path != "/api/approvals/action":
            self._send(404, b"not found", "text/plain")
            return

        # Role gate is PER CARD (approval_action): owner decides everything (final authority),
        # decision_maker decides cards routed to their lanes, contributor -> denied.
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else b"{}"
            data = json.loads(body.decode() or "{}")
        except Exception:
            self._send(400, b"bad json body", "application/json")
            return
        card_id = str(data.get("id") or "").strip()
        action = str(data.get("action") or "").strip().lower()
        feedback = data.get("feedback")
        if not card_id or action not in ("approve", "reject", "feedback"):
            self._send(400, json.dumps({"ok": False, "error": "id + action (approve|reject|feedback) required"}).encode(),
                       "application/json")
            return
        ok, payload = approval_action(card_id, action, feedback, actor=user)
        if ok:
            payload["ok"] = True
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        elif payload.get("forbidden"):
            self._send(403, json.dumps({"ok": False, **payload}, ensure_ascii=False).encode(),
                       "application/json")
        else:
            self._send(409, json.dumps({"ok": False, **payload}, ensure_ascii=False).encode(),
                       "application/json")

    def _do_roles(self, user):
        """POST /api/roles — owner-only grant/revoke with full audit.
        grant: {person, role, lanes?}   revoke: {person, role, revoke: true}."""
        if user.get("role") != "owner":
            self._send(403, json.dumps({"ok": False,
                                        "error": "owner role required — only the owner grants roles"}).encode(),
                       "application/json")
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode() or "{}") if n else {}
        except Exception:
            self._send(400, json.dumps({"ok": False, "error": "bad json body"}).encode(),
                       "application/json")
            return
        person = str(data.get("person") or "").strip()
        role = str(data.get("role") or "").strip().lower()
        lanes = data.get("lanes")
        revoke = bool(data.get("revoke"))
        if not person:
            self._send(400, json.dumps({"ok": False, "error": "person required"}).encode(),
                       "application/json")
            return
        if not role and not revoke:
            self._send(400, json.dumps({"ok": False,
                                        "error": "role required for grant, or revoke=true"}).encode(),
                       "application/json")
            return
        if lanes is not None and not isinstance(lanes, list):
            self._send(400, json.dumps({"ok": False,
                                        "error": "lanes must be a list (studenthub, plugn, fleet)"}).encode(),
                       "application/json")
            return
        ok, payload = apply_role_change(person, role, lanes, user.get("username"), revoke=revoke)
        if ok:
            payload["ok"] = True
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
        else:
            self._send(409, json.dumps({"ok": False, **payload}, ensure_ascii=False).encode(),
                       "application/json")

    def _do_approval_request(self, user):
        """POST /api/approvals/request — any session/agent can ask for a decision on a card.
        Notifies the card's DECIDER by name via a relay row (agent-relay.jsonl, kind=approval);
        the approvals badge reflects the routed card automatically. Discord DM via brick_gateway
        is NOT wired (brick-gateway.py is out of scope by instruction) — the relay row + the
        approvals badge are the notification. Body: {id or card_id, message?}."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode() or "{}") if n else {}
        except Exception:
            self._send(400, json.dumps({"ok": False, "error": "bad json body"}).encode(),
                       "application/json")
            return
        card_id = str(data.get("id") or data.get("card_id") or "").strip()
        msg = str(data.get("message") or "").strip()[:400]
        if not card_id:
            self._send(400, json.dumps({"ok": False, "error": "id (card id) required"}).encode(),
                       "application/json")
            return
        rows = read_jsonl(APPROVALS) or []
        card = None
        for r in reversed(rows):
            if isinstance(r, dict) and r.get("id") == card_id:
                card = r
                break
        if card is None:
            self._send(404, json.dumps({"ok": False, "error": "card not found"}).encode(),
                       "application/json")
            return
        if card.get("status") != "PENDING":
            self._send(409, json.dumps({"ok": False,
                                        "error": f"card already {card.get('status')} — no decision needed"}).encode(),
                       "application/json")
            return
        decider = card_decider(card)
        title = str(card.get("title") or card_id)
        body = (f"{msg} — " if msg else "") + f"{decider}, your call on '{title}' — approve or reject?"
        row = {"ts": now_iso(), "from": user.get("username", "?"), "to": decider,
               "kind": "approval", "body": body, "receipt": None}
        relay_append(row)
        self._send(200, json.dumps({"ok": True, "notified": decider, "card_id": card_id,
                                    "lane": card_lane(card), "via": "agent-relay row",
                                    "row": row,
                                    "note": "notification = relay row (agents see it); Discord DM via "
                                            "brick_gateway not wired — out of scope"},
                                   ensure_ascii=False).encode(), "application/json")

    def _do_lane_control(self, user):
        """POST /api/lane-control — owner-only lane pause/resume (khalid's CUT BURN
        kill switch). Appends to lane-control.jsonl + comments the fleet kanban board.
        Contributor (read-only) accounts get 403 — the tap is the owner's call."""
        if user.get("role") != "owner":
            self._send(403, json.dumps({"ok": False,
                                        "error": "owner role required — lane cuts are the owner's call, "
                                                 "contributor accounts are read-only"}).encode(),
                       "application/json")
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode() or "{}") if n else {}
        except Exception:
            self._send(400, json.dumps({"ok": False, "error": "bad json body"}).encode(),
                       "application/json")
            return
        lane = str(data.get("lane") or "").strip()
        action = str(data.get("action") or "").strip().lower()
        if lane not in TOGGLE_LANES:
            self._send(400, json.dumps({"ok": False,
                                        "error": f"unknown lane '{lane}' — toggles: {', '.join(TOGGLE_LANES)}"}).encode(),
                       "application/json")
            return
        if action not in ("pause", "resume"):
            self._send(400, json.dumps({"ok": False, "error": "action must be 'pause' or 'resume'"}).encode(),
                       "application/json")
            return
        row, kanban = lane_control_append(lane, action, user.get("username"))
        self._send(200, json.dumps({"ok": True, "row": row, "kanban": kanban,
                                    "lanes": lane_state(), "burn": burn_data()},
                                   ensure_ascii=False).encode(), "application/json")

    def _do_comms(self, user):
        """POST /api/comms — post to the fleet (append to agent-relay.jsonl).
        Two modes:
          {body, to: <brick_id>}   -> TARGETED: lands on the relay addressed to that
                                      brick; it reads it on its next cycle and the
                                      reply appears in that brick's thread.
          {body}                   -> BROADCAST: lands on the relay to=all AND mints a
                                      real kanban ticket ('fleet-message-<ts>',
                                      status=ready) in the SAME queue the claimer pool
                                      drains — claim -> work -> artifact -> receipt.
        Rate limit: owner 1 msg/min, others 5/hr (in-memory — deliberate simplicity)."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode() or "{}") if n else {}
        except Exception:
            self._send(400, json.dumps({"ok": False, "error": "bad json body"}).encode(),
                       "application/json")
            return
        body = str(data.get("body") or "").strip()
        if not body:
            self._send(400, json.dumps({"ok": False, "error": "body required"}).encode(),
                       "application/json")
            return
        if len(body) > 4000:
            self._send(400, json.dumps({"ok": False, "error": "message too long (max 4000 chars)"}).encode(),
                       "application/json")
            return
        to = str(data.get("to") or "").strip()
        if len(to) > 128:
            self._send(400, json.dumps({"ok": False, "error": "recipient too long"}).encode(),
                       "application/json")
            return
        ok, retry = relay_rate_check(user)
        if not ok:
            self._send(429, json.dumps({"ok": False, "error": f"rate limited — retry in ~{retry}s",
                                        "retry_after": retry}).encode(), "application/json")
            return
        who = user.get("username")
        if to:
            # ---- TARGETED: one brick hears it, its thread shows it
            row = {"ts": now_iso(), "from": who, "to": to,
                   "kind": str(data.get("kind") or "msg").strip() or "msg",
                   "body": body, "receipt": None}
            relay_append(row)
            self._send(200, json.dumps({
                "ok": True, "row": row, "targeted": True, "to": to,
                "note": f"delivered to {to} on the relay — it reads the bus on its next cycle and the reply lands in its thread",
                "rate": {"retry_after": 60 if user.get("role") == "owner" else 3600},
            }, ensure_ascii=False).encode(), "application/json")
            return
        # ---- BROADCAST: relay to all AND a real kanban ticket
        card = fleet_message_ticket(body, who)
        row = {"ts": now_iso(), "from": who, "to": "all",
               "kind": "msg", "body": body, "receipt": None}
        if card.get("id"):
            row["ticket"] = card["id"]
        relay_append(row)
        self._send(200, json.dumps({
            "ok": True, "row": row, "card": card,
            "routing": "goes to all bricks as a ticket — the one whose lane matches picks it up",
            "lifecycle": ["claim", "work", "artifact", "receipt"],
            "rate": {"retry_after": 60 if user.get("role") == "owner" else 3600},
        }, ensure_ascii=False).encode(), "application/json")

    def _do_login(self):
        """POST /login — verify creds, set session cookie, redirect (302)."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            form = parse_form(self.rfile.read(n) if n else b"")
        except Exception:
            form = {}
        username = str(form.get("username") or "").strip()
        password = str(form.get("password") or "")
        nxt = safe_next(form.get("next"))
        user = verify_user(username, password) if username and password else None
        if user:
            self._redirect(nxt, {"Set-Cookie": session_cookie_header(user)})
        else:
            self._redirect(f"/login?error=1&next={urllib.parse.quote(nxt)}")

    # ------------------------------------------------------------ discord oauth (2026-08-25)
    def _do_oauth_start(self):
        """GET /oauth/discord — 302 to Discord authorize (scope=identify, HMAC-signed state
        bound to this browser via a one-time cookie). Requires the OAuth2 Client Secret."""
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
        cfg, err = discord_oauth_env()
        if err:
            self._send(503, oauth_page("Discord login not configured", err),
                       "text/html; charset=utf-8")
            return
        state = oauth_state_make(q.get("next"))
        nonce = json.loads(base64.urlsafe_b64decode(state.partition(".")[0] + "=="))["n"]
        url = (f"{DISCORD_AUTHORIZE_URL}?client_id={urllib.parse.quote(cfg['client_id'])}"
               f"&redirect_uri={urllib.parse.quote(cfg['redirect_uri'])}"
               f"&response_type=code&scope={urllib.parse.quote('identify')}"
               f"&state={urllib.parse.quote(state)}")
        self._redirect(url, {"Set-Cookie":
            f"{OAUTH_STATE_COOKIE}={nonce}; Path=/; HttpOnly; SameSite=Lax; Max-Age={OAUTH_STATE_TTL}"})

    def _do_oauth_callback(self):
        """GET /oauth/discord/callback?code&state — verify state (constant-time + cookie),
        exchange code, /users/@me, map Discord ID -> fleet account (invite-only), then mint
        the SAME bawes_session cookie the password login uses. Unknown Discord users get an
        honest NOT-FOUND page and NO session."""
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
        clear = f"{OAUTH_STATE_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
        if q.get("error"):
            self._send(400, oauth_page("Discord sign-in cancelled",
                        f"Discord returned: {html.escape(q.get('error_description') or q.get('error'))}. "
                        "No session was created."), "text/html; charset=utf-8")
            return
        st = oauth_state_verify(q.get("state", ""), self._cookie_value(OAUTH_STATE_COOKIE))
        if not st:
            self._send(400, oauth_page("Sign-in link expired",
                        "The sign-in link was stale or the state did not match this browser. "
                        "Go back and tap the Discord button again."),
                       "text/html; charset=utf-8", {"Set-Cookie": clear})
            return
        cfg, err = discord_oauth_env()
        if err:
            self._send(503, oauth_page("Discord login not configured", err),
                       "text/html; charset=utf-8", {"Set-Cookie": clear})
            return
        code = q.get("code", "")
        if not code:
            self._send(400, oauth_page("Missing code",
                        "Discord did not return an authorization code."),
                       "text/html; charset=utf-8", {"Set-Cookie": clear})
            return
        try:
            tok = discord_exchange_code(code, cfg)
            me = discord_me(tok["access_token"])
        except Exception as e:
            print(f"discord oauth callback error: {e}", flush=True)
            self._send(502, oauth_page("Discord OAuth failed",
                        "The code exchange or identity fetch failed at Discord's side. "
                        "Please try again — no session was created."),
                       "text/html; charset=utf-8", {"Set-Cookie": clear})
            return
        did = str(me.get("id", ""))
        user = discord_map_user(did)
        if not user:
            name = str(me.get("global_name") or me.get("username") or did)
            self._send(403, oauth_page("You're not on the fleet list yet",
                        f"Discord account \"{name}\" (id {did}) is not on the fleet's invite "
                        "list. Access is by invitation — ask khalid to add you."),
                       "text/html; charset=utf-8", {"Set-Cookie": clear})
            return
        print(f"discord login ok: {user.get('username')} via discord id {did}", flush=True)
        nxt = safe_next(st.get("nxt", "/"))
        self._redirect(nxt, [("Set-Cookie", session_cookie_header(user)),
                             ("Set-Cookie", clear)])


if __name__ == "__main__":
    threading.Thread(target=_telemetry_loop, daemon=True, name="net-telemetry").start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"fleet-dashboard v5 serving http://{HOST}:{PORT}/ (login + session auth + discord oauth + agent bearer) — /approvals + /comms + who/burn/cut-burn + The Net + Portfolio + Time Machine + Money Live + Fleet Comms + Velocity live", flush=True)
    srv.serve_forever()
