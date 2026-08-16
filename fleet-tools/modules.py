#!/usr/bin/env python3
"""modules.py — The 6-module curriculum as a VERIFIABLE system (round-119).
Module pages live as plain-language docs; this engine tracks completion,
enforces the ladder (N+1 needs N), and routes every completion to a
non-earner for verification. No self-mint, no self-report (module 6 rule).

Usage:
  modules.py list                 — show the ladder
  modules.py show <n>             — plain-language module page
  modules.py complete <brick> <n> — submit completion (non-earner review queue)
  modules.py verify <brick> <n> <nonearner> — non-earner signs it (V-5 words)
"""
import json, os, pathlib, sys, time

BASE = pathlib.Path("/srv/bricks/register")
STATE = BASE / "module_state.json"
LEDGER = BASE / "wallet.jsonl"

MODULES = [
    {"n": 1, "name": "Banana Basics",
     "teach": "How brick work earns bananas.",
     "steps": ["Say hi to your brick.", "Dispatch a test card.",
               "Confirm the probe result."],
     "reward": 1, "verify": "probe result confirmed"},
    {"n": 2, "name": "Brick Health Check",
     "teach": "Inspect your brick's public exposure.",
     "steps": ["Run the guided health probe.", "Patch one open door."],
     "reward": 2, "verify": "probe + patch verified"},
    {"n": 3, "name": "Credential Hygiene",
     "teach": "Find and rotate exposed passwords.",
     "steps": ["Scan for exposed credentials.", "Rotate what's found.",
               "Re-scan: no live secrets."],
     "reward": 3, "verify": "secret probe finds no live secrets"},
    {"n": 4, "name": "Lane Awareness",
     "teach": "What lanes are; how your brick feeds the survival game.",
     "steps": ["Learn the lanes (banana, help, universe, idea).",
               "Map your brick's data flow in plain words."],
     "reward": 4, "verify": "mapping verified by non-earner"},
    {"n": 5, "name": "Improvement Sprint",
     "teach": "Ship one small brick improvement.",
     "steps": ["Pick one improvement.", "Ship it (DA-gated merge)."],
     "reward": 5, "verify": "merged unit, DA-gated"},
    {"n": 6, "name": "Survival Sprint",
     "teach": "Skills under resource pressure.",
     "steps": ["14 consecutive verified tasks over 7 days.",
               "No missed heartbeat.", "Handle one live incident end-to-end."],
     "reward": 0, "verify": "non-earner signs each receipt + incident close-out"},
]

def load():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}

def save(state):
    os.makedirs(BASE, exist_ok=True)
    fd = os.open(STATE, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(state, indent=2))

def mint(brick_id, n):
    """Mint reward — only on verified completion, routed by module rules."""
    row = {"kind": "earn", "card_id": f"module-{n}", "brick_id": brick_id,
           "person_id": brick_id, "bananas": MODULES[n-1]["reward"], "ts": time.time()}
    with open(LEDGER, "a") as f:
        f.write(json.dumps(row) + "\n")

def list_modules():
    for m in MODULES:
        v = "non-earner-observed" if m["n"] == 6 else m["verify"]
        print(f"M{m['n']} {m['name']:<22} +{m['reward']}🍌  verify: {v}")

def show(n):
    m = MODULES[n-1]
    print(f"# MODULE {m['n']} — {m['name']}\n")
    print(f"What you'll learn: {m['teach']}\n")
    print("Steps:")
    for i, s in enumerate(m["steps"], 1):
        print(f"  {i}. {s}")
    if m["reward"]:
        print(f"\nReward: {m['reward']} banana(s) — after a NON-EARNER verifies.")
    else:
        print("\nReward: survival threshold — non-earner signs every receipt.")

def complete(brick_id, n):
    state = load()
    done = set(state.get(brick_id, {}).get("done", []))
    for k in range(1, n):  # ladder enforcement
        if k not in done:
            print(f"BLOCKED: module {k} not completed — ladder is sequential.")
            return
    if n in done:
        print(f"module {n} already completed by {brick_id}.")
        return
    state.setdefault(brick_id, {})["pending"] = n
    save(state)
    print(f"{brick_id} submitted module {n} — QUEUED for non-earner verification.")

def verify(brick_id, n, nonearner):
    """V-5: the non-earner's own words are the sign. Never self-signed."""
    if nonearner == brick_id:
        print("REJECTED: no self-verification (physics rule).")
        return
    state = load()
    if state.get(brick_id, {}).get("pending") != n:
        print(f"nothing pending for {brick_id} module {n}.")
        return
    done = set(state.setdefault(brick_id, {}).get("done", []))
    done.add(n)
    state[brick_id]["done"] = sorted(done)
    state[brick_id].pop("pending", None)
    save(state)
    if MODULES[n-1]["reward"]:
        mint(brick_id, n)
    print(f"NON-EARNER {nonearner} signed module {n} for {brick_id} — "
          f"reward {'minted +%d🍌' % MODULES[n-1]['reward'] if MODULES[n-1]['reward'] else 'threshold recorded'}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list": list_modules()
    elif cmd == "show": show(int(sys.argv[2]))
    elif cmd == "complete": complete(sys.argv[2], int(sys.argv[3]))
    elif cmd == "verify": verify(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    else: print("unknown cmd")
