#!/usr/bin/env python3
"""allowance_meter.py — round-144 R1/R2/R5 + round-146 items 3&4 meter core.

The ALLOWANCE METER: append-only /srv/bricks/register/allowances.jsonl (0600),
flock-atomic debits, HMAC-SHA256 integrity (ALLOWANCES_INTEGRITY_KEY from env,
else a generated 0600 key file — vault-round-3 pattern; a caller-supplied
string is never auth). Derived balances, never mutated:
  free_usage(person, month) = sum(usage_debit.tasks) - sum(usage_refund.tasks)
                              over rows with payer in (absent,'sponsored')
  paid_usage(person, month)  = same over rows with payer='user-bananas'
  allowance(person, month)   = 50 + sum(allowance-gift.tasks) state=open, same month
  stop when free_usage >= allowance. Month window = calendar month (UTC, YYYY-MM).
  Gifts credit ONLY the window they are granted in; no rollover.

Ladder rungs (dedup: at most ONE row per rung per person per month):
  rung 80: free_usage first reaches ceil(0.80*allowance)  (40/50 base)
  rung 95: free_usage first reaches ceil(0.95*allowance)  (47/50 base)
  rung 100: free_usage reaches allowance -> alert row (the stop transaction)
State transitions are append-only: kind=warning-status / kind=alert-status rows
carry {ref, state} — the EFFECTIVE state is derived from the last status row.

Exact user-facing lines (AGI-ruled, round-144 R2/R4 + round-146 card):
  80% : "Heads up — you've used 40 of your 50 free tasks this month — just so you know."
  95% : "You're at 47 of 50 — when you hit 50 the team decides what happens next, and you'll hear from me right away."
  100%: "That was your 50th free task. You're not blocked — this is the switch to retrieval-only mode: ..."
"""
from __future__ import annotations
import fcntl, hashlib, json, os, pathlib, secrets, time

REGISTER = pathlib.Path("/srv/bricks/register")
ALLOWANCES = REGISTER / "allowances.jsonl"
LOCK = REGISTER / "allowances.jsonl.lock"
KEY_FILE = REGISTER / ".allowances_key"
LEDGER = pathlib.Path("/srv/bricks/router/state/ledger.jsonl")
REGISTRY = REGISTER / "registry.jsonl"

BASE_ALLOWANCE = 50
OWNER_UID = {  # registry owner name -> door person_id (mirrors door_v4 KNOWN)
    "khalid": "189055515819638794",
    "mishari": "231861753082937346",
    "chahd": "690554066815811625",
}
UID_NAME = {v: k for k, v in OWNER_UID.items()}
FLEET_OWNERS = {"bawes", "bawes-fleet"}
KHALID_UID = OWNER_UID["khalid"]

# ---- the AGI's exact lines (round-146 card; numbers parameterized) ----
def line_80(usage: int, allowance: int) -> str:
    return (f"Heads up — you've used {usage} of your {allowance} free tasks "
            f"this month — just so you know.")

def line_95(usage: int, allowance: int) -> str:
    return (f"You're at {usage} of {allowance} — when you hit {allowance} the "
            f"team decides what happens next, and you'll hear from me right away.")

def line_100(usage: int, allowance: int) -> str:
    return (f"That was your {allowance}th free task. You're not blocked — this "
            f"is the switch to retrieval-only mode: I can't run more paid tasks "
            f"until khalid says yes, and I've already told him. Check back later, okay?")

def degraded_reply(person_name: str, usage: int, allowance: int, banana_balance: float,
                   banana_price: float) -> str:
    """Deterministic degraded-mode reply: R4 line + the 3 escape options."""
    return (f"{line_100(usage, allowance)}\n\n"
            f"While you wait, three ways forward:\n"
            f"1 — Wait: the team may gift you more tasks (khalid's been told).\n"
            f"2 — Bring your own key: paste it once at the key safe — it stays "
            f"yours, never through chat.\n"
            f"3 — Spend bananas: cost+20% — your balance 🍌{banana_balance:.2f}, "
            f"this task ≈ 🍌{banana_price:.2f}.")

KHALID_ALERT_TPL = ("🍌 ALLOWANCE — {name} ({brick_id}) hit their {allowance} "
                    "free tasks\nUsed: {usage}/{allowance} this month · Cost so "
                    "far: ${cost:.2f} (real ledger)\nReply with one number:\n"
                    "1 — Gift {gift} more (this month only, free)\n"
                    "2 — Bill them (mark the overage pending — no gateway yet)\n"
                    "3 — Cheaper model (switch them to the cheap lane)")

KHALID_HEADS_UP_TPL = ("🍌 Heads-up: {name} at {usage}/{allowance} free tasks "
                       "this month (cost so far ${cost:.2f}). They stop at "
                       "{allowance} — reply then: 1 gift / 2 bill / 3 cheaper model.")

# ---- integrity ----
def _key() -> str:
    env = os.environ.get("ALLOWANCES_INTEGRITY_KEY", "")
    if env:
        return env
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    k = secrets.token_hex(32)
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(k + "\n")
    os.chmod(KEY_FILE, 0o600)
    return k

def _sig(row: dict) -> str:
    payload = {k: v for k, v in row.items() if k != "hmac"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()
                          + b"|" + _key().encode()).hexdigest()

def _sign(row: dict) -> dict:
    row = dict(row)
    row["hmac"] = _sig(row)
    return row

def _verify(row: dict) -> bool:
    return row.get("hmac") == _sig(row)

# ---- storage ----
def _append(row: dict):
    row = _sign(row)
    with open(ALLOWANCES, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f, fcntl.LOCK_UN)
    os.chmod(ALLOWANCES, 0o600)
    return row

def _lock():
    lf = open(LOCK, "w")
    fcntl.flock(lf, fcntl.LOCK_EX)
    return lf

def read() -> list[dict]:
    """All rows with HMAC verified; tamper raises ValueError (C6)."""
    if not ALLOWANCES.exists():
        return []
    rows = []
    for line in ALLOWANCES.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            raise ValueError("allowances.jsonl corrupt line (not JSON)")
        if not _verify(r):
            raise ValueError(f"allowances.jsonl tampered row: {line[:80]}")
        rows.append(r)
    return rows

def _statuses(rows: list[dict], kind: str):
    out = {}
    for r in rows:
        if r.get("kind") == kind and r.get("ref"):
            out[r["ref"]] = r  # last status row wins (append order)
    return out

# ---- time ----
def month(ts: float | None = None) -> str:
    return time.strftime("%Y-%m", time.gmtime(ts or time.time()))

def next_window_ts(m: str) -> int:
    y, mo = m.split("-")
    return int(time.mktime((int(y) + (int(mo) == 12), (int(mo) % 12) + 1,
                            1, 0, 0, 0, 0, 0, 0)))

# ---- derivations ----
def _usage_rows(rows: list[dict], person_id: str, m: str):
    return [r for r in rows if r.get("person_id") == person_id
            and r.get("month") == m]

def usage(person_id: str, m: str | None = None) -> dict:
    """{free, paid} task counts. Free = sponsored rows; paid = user-bananas."""
    m = m or month()
    rows = read()
    free, paid = 0, 0
    for r in _usage_rows(rows, person_id, m):
        if r.get("kind") == "usage_debit":
            payer = r.get("payer") or "sponsored"
            if payer == "user-bananas":
                paid += int(r.get("tasks", 0))
            else:
                free += int(r.get("tasks", 0))
        elif r.get("kind") == "usage_refund":
            # refunds only apply to free (sponsored) reservations
            free -= int(r.get("tasks", 0))
    return {"free": max(free, 0), "paid": paid}

def allowance(person_id: str, m: str | None = None) -> int:
    m = m or month()
    rows = read()
    gifts = sum(int(r.get("tasks", 0)) for r in rows
                if r.get("kind") == "allowance-gift"
                and r.get("person_id") == person_id and r.get("month") == m
                and r.get("state") == "open")
    return BASE_ALLOWANCE + gifts

def bucket(person_id: str, m: str | None = None) -> dict:
    m = m or month()
    u = usage(person_id, m)
    a = allowance(person_id, m)
    return {"month": m, "usage": u["free"], "paid": u["paid"],
            "allowance": a, "exhausted": u["free"] >= a,
            "pct": round(u["free"] / a * 100, 1) if a else 0.0}

# ---- debit / refund (R1.3: flock-atomic reservation at task start) ----
def debit(person_id: str, brick_id: str, lane: str, card_id: str,
          invoke_ts: int | None = None, lane_cost: float = 0.0,
          payer: str = "sponsored") -> dict:
    m = month()
    invoke_ts = invoke_ts or int(time.time())
    lf = _lock()
    try:
        rows = read()
        u = usage(person_id, m)
        a = allowance(person_id, m)
        if payer != "user-bananas" and u["free"] >= a:
            # paid overage never consumes the free allowance; free rows stop
            return {"ok": False, "month": m, "usage": u["free"],
                    "allowance": a, "exhausted": True}
        row = _append({"kind": "usage_debit", "person_id": person_id,
                       "brick_id": brick_id, "month": m, "tasks": 1,
                       "lane": lane, "invoke_ts": invoke_ts,
                       "card_id": card_id, "lane_cost": lane_cost,
                       "payer": payer})
        return {"ok": True, "ref": row, "month": m, "usage_after": u["free"] + 1,
                "allowance": a}
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN); lf.close()

def refund(person_id: str, brick_id: str, lane: str, ref: dict) -> dict | None:
    """Compensating row for a failed (non-billed) reservation: keeps the
    derived free-usage == billed sponsored invokes (R1.4)."""
    if not ref or not ref.get("hmac"):
        return None
    return _append({"kind": "usage_refund", "person_id": person_id,
                    "brick_id": brick_id, "month": month(), "tasks": 1,
                    "lane": lane, "ref_of": ref.get("hmac"),
                    "invoke_ts": int(time.time())})

# ---- ladder rows (R2) ----
def _rung_thresholds(allow: int) -> tuple[int, int, int]:
    import math
    if allow == BASE_ALLOWANCE:
        return 40, 47, allow
    return math.ceil(0.80 * allow), math.ceil(0.95 * allow), allow

def maybe_warning(person_id: str, brick_id: str, m: str | None = None) -> dict | None:
    """Post-invoke evaluator: writes warning rows (80/95) with per-rung/per-
    person/per-month dedup. Returns the new row or None."""
    m = m or month()
    b = bucket(person_id, m)
    t80, t95, t100 = _rung_thresholds(b["allowance"])
    rung = None
    if b["usage"] >= t100:
        return None  # 100% handled by open_alert (the stop transaction)
    if b["usage"] >= t95:
        rung = "95"
    elif b["usage"] >= t80:
        rung = "80"
    if rung is None:
        return None
    rows = read()
    for r in rows:
        if (r.get("kind") == "warning" and r.get("rung") == rung
                and r.get("person_id") == person_id and r.get("month") == m):
            return None  # dedup: one row per rung/person/month
    return _append({"kind": "warning", "rung": rung, "person_id": person_id,
                    "brick_id": brick_id, "month": m,
                    "usage": b["usage"], "allowance": b["allowance"],
                    "state": "open", "ts": int(time.time())})

def pending_warnings(person_id: str, m: str | None = None) -> list[dict]:
    m = m or month()
    rows = read()
    statuses = _statuses(rows, "warning-status")
    out = []
    for r in rows:
        if (r.get("kind") == "warning" and r.get("person_id") == person_id
                and r.get("month") == m):
            st = statuses.get(r.get("hmac"), {}).get("state", "open")
            if st == "open":
                out.append(r)
    return out

def mark_warning_delivered(warning_row: dict, channel: str):
    _append({"kind": "warning-status", "ref": warning_row.get("hmac"),
             "state": "delivered", "channel": channel,
             "ts": int(time.time())})

# ---- alerts (R4/R6: durable row FIRST, delivery second, stop third) ----
def open_alert(person_id: str, brick_id: str, m: str | None = None,
               name: str = "", cost_usd: float = 0.0,
               rung: str = "100") -> dict:
    """Durable alert row FIRST (fsync via _append), dedup per
    (person, month, rung): the 95% heads-up and the 100% stop are TWO rows —
    khalid gets the lead-time notice AND the actionable alert (R2), never
    duplicates of the same rung."""
    m = m or month()
    b = bucket(person_id, m)
    rows = read()
    statuses = _statuses(rows, "alert-status")
    for r in rows:
        if (r.get("kind") == "alert" and r.get("person_id") == person_id
                and r.get("month") == m and r.get("rung") == rung):
            st = statuses.get(r.get("hmac"), {}).get("state", "open")
            if st != "closed":
                return {"alert_id": r.get("alert_id"), "new": False,
                        "row": r, "state": st, "rung": rung}
    aid = f"alt-{int(time.time())}-{person_id[:16]}"
    row = _append({"kind": "alert", "alert_id": aid, "person_id": person_id,
                   "brick_id": brick_id, "month": m, "usage": b["usage"],
                   "allowance": b["allowance"], "cost_usd": round(cost_usd, 4),
                   "name": name, "rung": rung, "state": "open",
                   "ts": int(time.time())})
    return {"alert_id": aid, "new": True, "row": row, "state": "open",
            "rung": rung}

def alert_status(alert_id: str) -> dict:
    """Effective state: closed beats delivered beats undelivered beats open."""
    rows = read()
    statuses = [r for r in rows if r.get("kind") == "alert-status"
                and r.get("alert_id") == alert_id]
    if not statuses:
        return {"state": "open"}
    last = statuses[-1]
    return {"state": last.get("state"), "channel": last.get("channel"),
            "action": last.get("action"), "ts": last.get("ts")}

def open_alert_rows() -> list[dict]:
    rows = read()
    statuses = _statuses(rows, "alert-status")
    out = []
    for r in rows:
        if r.get("kind") == "alert":
            st = statuses.get(r.get("hmac"), {}).get("state", "open")
            if st != "closed":
                out.append(r)
    return out

def mark_alert_status(alert_id: str, state: str, channel: str = "",
                      action: str = "", response_row: str = ""):
    _append({"kind": "alert-status", "alert_id": alert_id, "state": state,
             "channel": channel, "action": action, "response_row": response_row,
             "ts": int(time.time())})

def alert_response(alert_id: str, reply: str, person_id: str = KHALID_UID):
    """Khalid's verbatim reply row — the audit-chain middle link."""
    return _append({"kind": "alert-response", "alert_id": alert_id,
                    "person_id": person_id, "reply": reply,
                    "channel": "discord-dm", "ts": int(time.time())})

# ---- escape paths (R5) ----
def gift(person_id: str, brick_id: str, tasks: int = BASE_ALLOWANCE,
         alert_id: str = "", response_row: str = "") -> dict:
    """Owner-gated signed ledger row crediting the bucket (sponsor_id=khalid).
    IDEMPOTENT: an open gift for (person, month) is never duplicated."""
    m = month()
    rows = read()
    for r in rows:
        if (r.get("kind") == "allowance-gift" and r.get("person_id") == person_id
                and r.get("month") == m and r.get("state") == "open"):
            return {"ok": True, "existing": True, "row": r}
    row = _append({"kind": "allowance-gift", "person_id": person_id,
                   "brick_id": brick_id, "month": m, "tasks": tasks,
                   "sponsor_id": "khalid", "sponsor_kind": "owner",
                   "granted_by": "khalid",
                   "authorization_channel": "discord-dm",
                   "alert_id": alert_id, "response_row": response_row,
                   "state": "open", "ts": int(time.time())})
    return {"ok": True, "existing": False, "row": row}

def billing_pending(person_id: str, brick_id: str, tasks_over: int,
                    rate_usd_per_task: float, amount_usd_pending: float,
                    alert_id: str = "", response_row: str = "") -> dict:
    """Billing is DEFERRED (no gateway): marker row only, unblocks (R5.2)."""
    return _append({"kind": "billing-pending", "person_id": person_id,
                    "brick_id": brick_id, "month": month(),
                    "tasks_over": tasks_over,
                    "rate_usd_per_task": rate_usd_per_task,
                    "amount_usd_pending": round(amount_usd_pending, 6),
                    "rate_note": "cost+20% doctrine (round-65); per-task cost "
                                 "ledger-anchored, provisional",
                    "marker": "billing-pending", "gateway": None,
                    "sponsor_id": "khalid", "alert_id": alert_id,
                    "response_row": response_row, "state": "pending",
                    "ts": int(time.time())})

# ---- identity ----
def person_of_brick(brick_id: str) -> str | None:
    """Registry owner row -> person_id (door uid). Fleet bricks/roles exempt.
    Registry is the ONLY truth (round-137 F-7); a door-profile claim is not."""
    if not REGISTRY.exists():
        return None
    owner = None
    for line in REGISTRY.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("brick_id") == brick_id and r.get("owner"):
            owner = r["owner"]
    if not owner or owner in FLEET_OWNERS:
        return None
    return OWNER_UID.get(owner)

def person_name(person_id: str) -> str:
    return UID_NAME.get(person_id, person_id)

def cost_so_far(brick_id: str) -> float:
    """Ledger-anchored spend for the brick this month (machine-time rule)."""
    m = month()
    total = 0.0
    if not LEDGER.exists():
        return 0.0
    for line in LEDGER.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if (r.get("consumer") == brick_id
                and time.strftime("%Y-%m", time.gmtime(r.get("ts", 0))) == m):
            total += float(r.get("cost", 0.0) or 0.0)
    return total

def status_line() -> str:
    """One-line meter status for the dashboard/watchdog."""
    rows = read()
    alerts = [r for r in rows if r.get("kind") == "alert"]
    warnings = [r for r in rows if r.get("kind") == "warning"]
    gifts = [r for r in rows if r.get("kind") == "allowance-gift"]
    return (f"allowances.jsonl: {len(rows)} rows, {len(alerts)} alerts, "
            f"{len(warnings)} warnings, {len(gifts)} gifts")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(status_line())
    else:
        print("allowance_meter.py loaded — use from router/notifier/watchdog/door")
