"""tests_fleet_engine.py — the tests that should have existed (round-84).
Pin the contracts the DA caught in rounds 81–82: earn definition consistency,
credit exclusion, ROI honesty, sustain-gate verdicts.
"""
import json, os, pathlib, sys, tempfile

ROOT = str(pathlib.Path(__file__).parent.parent)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "spawn-package"))

from sustain_gate import decide

def _mkwallet(rows):
    p = tempfile.mktemp(suffix=".jsonl")
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p

W_MINT = {"kind": "earn", "card_id": "c1", "brick_id": "worker-001", "bananas": 1}
W_LEGACY_MINT = {"card_id": "c2", "brick_id": "worker-001", "bananas": 1}
W_CREDIT = {"kind": "credit", "brick_id": "chahd-cloud-001", "bananas": 200}
W_SEED = {"kind": "founder-seed", "brick_id": "khalid-device-001", "bananas": 5}

def _decide(wallet, cost):
    """decide() returns a dict; capture its print noise."""
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return decide(wallet, "", cost)

def test_earn_definition_includes_mint_rows_only():
    """credits and seeds are NEVER earnings — only mint rows count."""
    wallet = _mkwallet([W_MINT, W_LEGACY_MINT, W_CREDIT, W_SEED])
    out = _decide(wallet, 0.05)
    # unified definition: kind=earn OR card-bearing
    earn_rows = [W_MINT, W_LEGACY_MINT]  # the two mints
    assert out["earned_bananas"] == sum(r["bananas"] for r in earn_rows) == 2, \
        f"earned should be 2 (mints only), got {out['earned_bananas']}"

def test_credit_never_counts_as_earned():
    wallet = _mkwallet([W_CREDIT])
    out = _decide(wallet, 0.05)
    assert out["earned_bananas"] == 0, "200 credit must NOT count as earned"

def test_halt_when_cost_exceeds_earnings():
    """self-sustain: don't spend GPU money the fleet hasn't earned."""
    wallet = _mkwallet([W_MINT])  # 1 banana = $0.012
    out = _decide(wallet, 1.00)  # $1/hr instance
    assert out["verdict"] in ("HOLD", "STOP"), "expensive instance must not SCALE"
    assert out["self_sustain"] is False

def test_scale_only_when_earnings_cover_instance():
    wallet = _mkwallet([W_MINT] * 100)  # $1.20 earned
    out = _decide(wallet, 0.05)  # cheap instance
    assert out["verdict"] == "SCALE", f"cheap instance + real earnings should scale, got {out['verdict']}"

if __name__ == "__main__":
    import traceback
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{4 - failures}/4 passed")
    sys.exit(1 if failures else 0)
