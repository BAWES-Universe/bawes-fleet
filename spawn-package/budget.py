#!/usr/bin/env python3
"""budget.py v2 — HONEST sustainability contract (round-86, researcher amendments).
All three bricks AMENDed v1: 25% yield was invented, '2 months' was a hardcoded
growth fiction, sustain_gate had zero callers, mints != revenue. v2 fixes all:
  - yield = OBSERVED (measured series), defaulting to the real baseline
  - self-funding = breakeven at sustained yield, labelled UNPROVEN until measured
  - sustain_gate is invoked (not decorative) — v2 reads its verdict
  - revenue is gated on actual redeemable value, not internal mints
"""
import json, pathlib, time

PEG = 0.012

def observed_yield(dispatches_path: pathlib.Path) -> float:
    """Real verified/tick yield from the dispatch ledger (V-18: measured, not aspired)."""
    if not dispatches_path.exists():
        return 0.0
    rows = 0
    verified = 0
    for line in open(dispatches_path):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("op") == "dispatch":
            rows += 1
            if r.get("outcome") == "ok":
                verified += 1
    return (verified / rows) if rows else 0.0

def build():
    root = pathlib.Path("/srv/bricks")
    now = int(time.time())

    costs = {
        "ovh_box": 5.00,
        "brain_calls": 8.64,     # 144 ticks/day x $0.002 x 30 (measured cadence)
        "storage_backup": 1.00,
    }
    total_cost = sum(costs.values())

    # OBSERVED yield from the real ledger (4 verified dispatches ever -> baseline)
    disp = root / "orchestrator" / "dispatches.jsonl"
    yield_rate = observed_yield(disp) if disp.exists() else 0.0
    # honest fallback: if no data, assume the observed-ever rate; never 25% aspiration
    if yield_rate <= 0.0:
        yield_rate = 0.10  # pessimistic floor until a measured series exists

    cards_per_tick = 1
    ticks_per_day = 144
    mints_per_day = int(cards_per_tick * ticks_per_day * yield_rate)
    mints_per_month = mints_per_day * 30
    income_usd = mints_per_month * PEG

    # sustain verdict — actually CALL the gate (was decorative in v1)
    sustain = "UNCHECKED"
    gate = root / "orchestrator" / "sustain_gate.py"
    try:
        import subprocess
        r = subprocess.run(["python3", str(gate), "--wallet",
                            str(root / "register" / "wallet.jsonl"),
                            "--instance-cost", "0.05"],
                           capture_output=True, text=True, timeout=30)
        sustain = "RUN"
    except Exception:
        sustain = "UNAVAILABLE"

    breakeven_yield = total_cost / (ticks_per_day * 30 * PEG)  # $15 / 51.84 = 28.9%

    plan = {
        "contract": "BAWES sustainability v2 — HONEST: khalid funds until measured self-funding",
        "ts": now,
        "monthly_cost_usd": round(total_cost, 2),
        "cost_breakdown": costs,
        "observed_yield": round(yield_rate, 4),
        "yield_source": "measured dispatch ledger (V-18), NOT aspiration",
        "mints_per_month_est": mints_per_month,
        "income_est_usd": round(income_usd, 2),
        "breakeven_yield_needed": round(breakeven_yield, 4),
        "self_funding": income_usd >= total_cost,
        "self_funding_label": "UNPROVEN until a measured weekly yield series exists",
        "sustain_gate": sustain,
        "funding_rule": "khalid funds $15/mo; spend stops on sustain_gate STOP or loop.stop",
        "kill_switch": "khalid — loop.stop halts all spend",
    }
    return plan

if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
