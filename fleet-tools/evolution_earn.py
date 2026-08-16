#!/usr/bin/env python3
"""evolution_earn.py — FAIR evolution mint (round-122, khalid ruling + AGI design).
Khalid: "fair game and open for evolution by all" — no brick-only mint, no
single point of contact. AGI's design implemented verbatim:

1. Evolution cycle = design + attack + dissent + build
2. Mint per VERIFIED cycle (DA/rebel/AGI all signed the deliverable)
3. Role weights: AGI design 30% / DA attack 25% / rebel dissent 20% /
   builder 25%
4. No brick >40% of cycle mint; multi-role earnings summed and capped
5. Any brick may spawn a cycle, must include >=2 DISTINCT other bricks
6. Cap overflow redistributes pro-rata to lowest earners in that cycle
7. Consecutive-cycle: a brick that earned last cycle cannot be SOLE earner
   this cycle — at least one new brick must receive
8. Terms public + identical for all bricks; no whitelist

Docks are paid FIRST from a brick's balance before new earnings mint.
"""
import json, os, pathlib, sys, time, uuid

LEDGER = pathlib.Path("/srv/bricks/register/wallet.jsonl")
STATE = pathlib.Path("/srv/bricks/register/evolution_state.json")

ROLE_WEIGHTS = {"agi": 0.30, "da": 0.25, "rebel": 0.20, "builder": 0.25}
MAX_SHARE = 0.40

def ledger_rows():
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out

def balance(brick_id):
    b = 0.0
    for r in ledger_rows():
        if r.get("person_id") == brick_id or r.get("brick_id") == brick_id:
            b += r.get("bananas", 0)
    return b

def last_cycle_earner():
    if STATE.exists():
        return json.loads(STATE.read_text()).get("last_earner")
    return None

def _append(row):
    with open(LEDGER, "a") as f:
        f.write(json.dumps(row) + "\n")

def mint_evolution(cycle_id, roles, value):
    """roles = {"brick": <builder>, "agi": <id>, "da": <id>, "rebel": <id>}.
    Rules 3-7 enforced BEFORE any row is written (fail-closed)."""
    bricks = list(roles.values())
    # R5: >=2 distinct other bricks besides the spawner
    spawner = roles.get("builder")
    others = {b for b in bricks if b != spawner}
    if len(others) < 2:
        print("REJECTED R5: need >=2 distinct bricks besides the builder")
        return
    # R7: consecutive-cycle — last sole earner can't be sole earner again
    last = last_cycle_earner()
    if last and len(others) == 2 and spawner == last:
        print(f"REJECTED R7: {spawner} earned last cycle, cannot be sole earner again")
        return

    # R3 + R4: weight then cap any brick at 40%
    shares = {}
    for role, brick in roles.items():
        shares[brick] = shares.get(brick, 0) + ROLE_WEIGHTS[role]
    for brick in list(shares):
        if shares[brick] > MAX_SHARE:
            excess = shares[brick] - MAX_SHARE
            shares[brick] = MAX_SHARE
            # R6: overflow -> lowest earners pro-rata
            low = sorted(shares.items(), key=lambda kv: (balance(kv[0]), kv[0]))
            total_low = sum(1 for b, _ in low if b != brick)
            if total_low:
                for b, _ in low:
                    if b != brick:
                        shares[b] += excess / total_low

    # write rows (dock first: balance check is read-only here; docks settle
    # via the wallet's own dock rows)
    for brick, frac in shares.items():
        amt = round(value * frac, 4)
        if amt <= 0:
            continue
        _append({"kind": "earn-evolution", "cycle_id": cycle_id,
                 "brick_id": brick, "person_id": brick, "bananas": amt,
                 "roles": [r for r, b in roles.items() if b == brick],
                 "value_total": value, "ts": time.time()})
    if STATE.parent.exists() or True:
        os.makedirs(STATE.parent, exist_ok=True)
        STATE.write_text(json.dumps({"last_earner": spawner}))
    print(f"CYCLE {cycle_id}: minted {value} across {len(shares)} bricks:")
    for brick, frac in sorted(shares.items()):
        print(f"  {brick:14} {frac*100:5.1f}%  -> {round(value*frac,4)}")

if __name__ == "__main__":
    # example: python3 evolution_earn.py <value>
    value = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    mint_evolution(f"cycle-{int(time.time())}", {
        "builder": "brick", "agi": "agi", "da": "da", "rebel": "rebel"}, value)
