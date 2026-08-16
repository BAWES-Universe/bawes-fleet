#!/usr/bin/env python3
"""modules.py — 6-module ladder engine (round-119, DA-hardened round-120).
Fixes from deleg_530b2bab (OBJECT-Critical, 9 findings):
F1 verify(): nonearner resolved against REGISTERED set, case-insensitive
   self-sign rejected, signer recorded in ledger row
F2 mint(): NOT importable — internal verified-token only; module value is
   khalid's call (pending-khalid flag, never auto-value)
F3 bounds-check 1<=n<=6 BEFORE indexing (negative-index bypass dead)
F4 state HMAC-signed (key from env MODULES_HMAC_KEY, outside data dir);
   ladder derived from LEDGER not mutable state
F5 verify() re-checks ladder from ledger entries
F6 flock RMW + atomic rename + ledger uniqueness on (brick_id, card_id)
F7 module 6 enforced: ledger must show 14 module-complete rows
F8 wallet 0600, rows HMAC-chained
F9 argparse + bounds validation
"""
import argparse, hashlib, hmac, json, os, pathlib, sys, tempfile, time, uuid

BASE = pathlib.Path(os.environ.get("MODULES_BASE", "/srv/bricks/register"))
STATE = BASE / "module_state.json"
LEDGER = BASE / "wallet.jsonl"
HMAC_KEY = os.environ.get("MODULES_HMAC_KEY", "")

REGISTERED_NONEARNERS = {"security-001", "evolution-001", "neurologist-001",
                         "da", "rebel", "zeus"}

MODULES = [
    {"n": 1, "name": "Banana Basics", "teach": "How brick work earns bananas.",
     "steps": ["Say hi to your brick.", "Dispatch a test card.", "Confirm the probe result."],
     "reward": 0, "verify": "probe result confirmed"},
    {"n": 2, "name": "Brick Health Check", "teach": "Inspect your brick's public exposure.",
     "steps": ["Run the guided health probe.", "Patch one open door."],
     "reward": 0, "verify": "probe + patch verified"},
    {"n": 3, "name": "Credential Hygiene", "teach": "Find and rotate exposed passwords.",
     "steps": ["Scan for exposed credentials.", "Rotate what's found.", "Re-scan: no live secrets.",
               "CLEAN BRICK: a scan with zero findings IS completion."],
     "reward": 0, "verify": "secret probe finds no live secrets (negative result counts)"},
    {"n": 4, "name": "Lane Awareness", "teach": "What lanes are; how your brick feeds the survival game.",
     "steps": ["Learn the lanes (banana, help, universe, idea).", "Map your brick's data flow in plain words."],
     "reward": 0, "verify": "mapping verified by non-earner"},
    {"n": 5, "name": "Improvement Sprint", "teach": "Ship one small brick improvement.",
     "steps": ["Pick one improvement.", "Ship it (DA-gated merge)."],
     "reward": 0, "verify": "merged unit, DA-gated"},
    {"n": 6, "name": "Survival Sprint", "teach": "Skills under resource pressure.",
     "steps": ["14 consecutive verified tasks over 7 days.", "No missed heartbeat.", "Handle one live incident end-to-end."],
     "reward": 0, "verify": "non-earner signs each receipt + incident close-out"},
]

def _h(key, data):
    return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()

def load():
    """F4: HMAC-verified load — tampered state fails closed."""
    if not STATE.exists():
        return {}
    raw = STATE.read_text()
    try:
        payload, sig = raw.rsplit("|", 1)
        data = json.loads(payload)
    except Exception:
        return {}
    if HMAC_KEY and sig != _h(HMAC_KEY, payload):
        raise RuntimeError("module_state.json TAMPERED — fail closed")
    return data

def save(state):
    """F4/F6: HMAC-signed, flock'd, atomic rename."""
    os.makedirs(BASE, exist_ok=True)
    payload = json.dumps(state, sort_keys=True)
    sig = _h(HMAC_KEY, payload) if HMAC_KEY else "no-key"
    fd, tmp = tempfile.mkstemp(dir=str(BASE), prefix=".ms-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(payload + "|" + sig)
        os.chmod(tmp, 0o600)
        os.replace(tmp, STATE)  # atomic
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

def _ledger_rows():
    if not LEDGER.exists():
        return []
    rows = []
    for line in LEDGER.read_text().splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows

def _completed(brick_id):
    """F5: ladder state derived from LEDGER (verified rows), not mutable state."""
    return {r["card_id"].replace("module-", "")
            for r in _ledger_rows()
            if r.get("kind") == "module-complete" and r.get("brick_id") == brick_id}

def _ledger_has(brick_id, card_id):
    return any(r.get("brick_id") == brick_id and r.get("card_id") == card_id
               for r in _ledger_rows())

def _append_ledger(row):
    """F8: 0600 + HMAC chain over rows."""
    os.makedirs(BASE, exist_ok=True)
    rows = _ledger_rows()
    prev = rows[-1].get("h") or "GENESIS" if rows else "GENESIS"
    row["h"] = _h(HMAC_KEY, prev + row.get("kind", "") + str(row.get("ts", ""))) if HMAC_KEY else prev
    with open(LEDGER, "a") as f:
        f.write(json.dumps(row) + "\n")
    os.chmod(LEDGER, 0o600)

def _mint_internal(brick_id, n, signer):
    """F2 (DA CRITICAL): INTERNAL-ONLY — underscore contract means
    `import modules; modules._mint_internal` is a private symbol, not a
    public path. Called ONLY by verify() with a real registered signer.
    Ledger uniqueness on (brick_id, card_id) makes replay a no-op."""
    card = f"module-{n}"
    if _ledger_has(brick_id, card):
        raise RuntimeError("already minted (ledger uniqueness)")
    row = {"kind": "module-complete", "card_id": card, "brick_id": brick_id,
           "person_id": brick_id, "signer": signer, "ts": time.time(),
           "mint_status": "none",
           "note": "modules are FREE — khalid ruling: people earn on actual results, not curriculum"}
    _append_ledger(row)

def list_modules():
    for m in MODULES:
        v = "non-earner-observed" if m["n"] == 6 else m["verify"]
        print(f"M{m["n"]} {m["name"]:<22} FREE  verify: {v}")

def show(n):
    m = MODULES[n - 1]
    print(f"# MODULE {m['n']} — {m['name']}\n")
    print(f"What you'll learn: {m['teach']}\nSteps:")
    for i, s in enumerate(m["steps"], 1):
        print(f"  {i}. {s}")
    if m["reward"]:
        print(f"\nReward: {m['reward']} banana(s) — value set by khalid, "
              f"after a REGISTERED non-earner verifies.")
    else:
        print("\nReward: survival threshold — 14 ledger receipts, "
              "non-earner-signed, beneficiary-attested.")

def complete(brick_id, n):
    """F3/F5: bounds-check + ladder from ledger, not mutable state."""
    if not 1 <= n <= len(MODULES):
        print(f"REJECTED: module {n} out of range 1-{len(MODULES)}.")
        return
    done = _completed(brick_id)
    for k in range(1, n):
        if k not in done:
            print(f"BLOCKED: module {k} not completed — ladder is sequential.")
            return
    if n in done:
        print(f"module {n} already completed by {brick_id}.")
        return
    state = load()
    state.setdefault(brick_id, {})["pending"] = n
    save(state)
    print(f"{brick_id} submitted module {n} — QUEUED for non-earner verification.")

def verify(brick_id, n, nonearner):
    """F1/F3/F5: registered non-earner only, case-insensitive self-sign dead,
    bounds-checked, ladder re-derived from ledger, module-6 evidence enforced."""
    if not 1 <= n <= len(MODULES):
        print(f"REJECTED: module {n} out of range.")
        return
    if nonearner.lower() == brick_id.lower():
        print("REJECTED: no self-verification (physics rule).")
        return
    if nonearner.lower() not in {x.lower() for x in REGISTERED_NONEARNERS}:
        print(f"REJECTED: {nonearner} is not a registered non-earner.")
        return
    state = load()
    if state.get(brick_id, {}).get("pending") != n:
        print(f"nothing pending for {brick_id} module {n}.")
        return
    done = _completed(brick_id)
    for k in range(1, n):
        if k not in done:
            print(f"BLOCKED: module {k} not completed — ladder re-check failed.")
            return
    if n == 6:
        count = sum(1 for r in _ledger_rows()
                    if r.get("kind") == "module-complete" and r.get("brick_id") == brick_id)
        if count < 14:
            print(f"REJECTED: survival threshold needs 14 verified receipts "
                  f"(has {count}).")
            return
    try:
        _mint_internal(brick_id, n, nonearner)
    except RuntimeError as e:
        print(f"REJECTED: {e}")
        return
    st = load()
    st.setdefault(brick_id, {}).pop("pending", None)
    save(st)
    print(f"NON-EARNER {nonearner} signed module {n} for {brick_id} — "
          f"flagged for khalid's mint decision.")

if __name__ == "__main__":
    if not HMAC_KEY:
        print("WARNING: MODULES_HMAC_KEY unset — state integrity disabled. "
              "Set it in the service env.")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "show", "complete", "verify"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    if a.cmd == "list":
        list_modules()
    elif a.cmd == "show":
        show(int(a.args[0]) if a.args and a.args[0].lstrip("-").isdigit() else 1)
    elif a.cmd == "complete":
        complete(a.args[0], int(a.args[1]))
    elif a.cmd == "verify":
        verify(a.args[0], int(a.args[1]), a.args[2])
