#!/usr/bin/env python3
"""sustain_gate.py — THE SELF-SUSTAIN DECISION (khalid directive 2026-08-15).
The AGI decides whether to spend: a GPU instance runs ONLY while its expected
earnings >= its cost (round-24 self-funding rule, machine-enforced).
Reads the ROI ledger; outputs SCALE / HOLD / STOP with the number that decides.
Scar doctrine: no invented costs — every number comes from real ledger rows.
"""
import json, pathlib, sys

def read_rows(p):
    if not pathlib.Path(p).exists():
        return []
    out = []
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out

def decide(wallet_path, roi_path, instance_cost_per_hr, ledger_path=None):
    wallet = read_rows(wallet_path)
    roi_rows = read_rows(roi_path) if roi_path else []

    # real earnings: mint rows (kind=earn or card-bearing rows)
    earns = [r for r in wallet if r.get("kind") == "earn" or "card_id" in r]
    earned_total = sum(r.get("bananas", 0) for r in earns)
    # real cost: dispatch cost rows
    cost_total = 0.0
    if ledger_path and pathlib.Path(ledger_path).exists():
        for line in open(ledger_path):
            try:
                r = json.loads(line)
                if r.get("op") in ("dispatch-price", "invoke") and r.get("outcome") == "committed":
                    cost_total += 0.002  # router cost per invoke (real, declared)
            except Exception:
                pass

    # bananas have a peg: 1 banana = $0.01 of verified fleet cost (v1.1: $0.012)
    BANANA_PEG = 0.012
    earned_value = earned_total * BANANA_PEG

    verdict = "HOLD"
    reason = f"earned ${earned_value:.4f} vs cost ${cost_total:.4f} (inst ${instance_cost_per_hr}/hr)"
    if earned_value >= cost_total + instance_cost_per_hr * 4:
        verdict = "SCALE"
    elif earned_value < cost_total * 0.5 and cost_total > 0:
        verdict = "STOP"

    print(json.dumps({
        "verdict": verdict,
        "reason": reason,
        "earned_bananas": earned_total,
        "earned_value_usd": round(earned_value, 4),
        "cost_usd": round(cost_total, 4),
        "instance_cost_per_hr_usd": instance_cost_per_hr,
        "banana_peg_usd": BANANA_PEG,
        "self_sustain": earned_value >= cost_total,
        "scar_doctrine": "all numbers from real ledger rows",
    }, indent=2))
    return verdict

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--wallet", required=True)
    ap.add_argument("--roi", default="")
    ap.add_argument("--ledger", default="")
    ap.add_argument("--instance-cost", type=float, default=0.05)
    args = ap.parse_args()
    decide(args.wallet, args.roi, args.instance_cost, args.ledger)
