#!/usr/bin/env python3
"""ORCH-1..6 — orchestrator probe suite (T-UNIVERSE-021). Executes the module."""
import json, os, sys, tempfile, pathlib, hashlib, shutil, hmac
sys.path.insert(0, "spawn-package")
from orchestrator import Orchestrator

td = pathlib.Path(tempfile.mkdtemp())
orch_dir = td / "orch"; reg_dir = td / "reg"; bank_dir = td / "bank"
orch_dir.mkdir(); reg_dir.mkdir(); bank_dir.mkdir()
(orch_dir / "open").mkdir(); (orch_dir / "claimed").mkdir(); (orch_dir / "done").mkdir()

probe_pool = td / "probe_pool.json"
H = hashlib.sha256(b"fleet-probe-output").hexdigest()
probe_pool.write_text(json.dumps({"probe-verify-001": {"expected_sha256": H}}))
os.chmod(probe_pool, 0o600)

rate = {"probe-verify-001": 1, "default": 1}
TOK = "x" * 24
o = Orchestrator(str(orch_dir), str(reg_dir), str(bank_dir), rate,
                 str(probe_pool), "http://127.0.0.1:3738", TOK)

# ORCH-1: claim atomicity + lease
card = {"card_id": "c1", "capability": "probe", "probe_id": "probe-verify-001",
        "price": 1, "death_warrant": True}
(orch_dir / "open" / "c1").write_text(json.dumps(card))
r = o.claim_card("c1")
assert r["ok"] and r["state"] == "claimed"
assert not (orch_dir / "open" / "c1").exists()
assert (orch_dir / "claimed" / "c1").exists()
r2 = o.claim_card("c1")  # already claimed -> lease branch
assert not r2["ok"]
print("ORCH-1 PASS claim atomic + double-claim refused")

# ORCH-2: capability match + rank
(reg_dir / "registry.jsonl").write_text(
    json.dumps({"brick_id": "b-a", "skills": ["probe"], "quality": "claimed"}) + "\n" +
    json.dumps({"brick_id": "b-b", "skills": ["probe"], "quality": "verified"}) + "\n")
cands = o.match_card(card)
assert [c["brick_id"] for c in cands] == ["b-b", "b-a"], cands
assert o.match_card({"capability": "nope"}) == []
print("ORCH-2 PASS match + verified-first rank")

# ORCH-3: dispatch shape — missing death warrant refused
bad = dict(card); bad.pop("death_warrant")
r = o.dispatch(bad, {"brick_id": "b-b"})
assert not r["ok"] and "death_warrant" in r["error"]
print("ORCH-3 PASS missing death_warrant refused")

# ORCH-4: receipt verify — genuine + tampered
good_receipt = {"card_id": "c1", "probe_id": "probe-verify-001",
                "output_hash": H, "brick_id": "b-b"}
v = o.verify_receipt(good_receipt)
assert v["ok"]
bad_receipt = dict(good_receipt); bad_receipt["output_hash"] = "0" * 64
assert not o.verify_receipt(bad_receipt)["ok"]
assert not o.verify_receipt({})["ok"]
print("ORCH-4 PASS verify genuine + tamper + missing rejected")

# ORCH-5: mint on verified-only + replay dedup
m1 = o.mint(card, good_receipt)
assert m1["ok"] and m1["bananas"] == 1
m2 = o.mint(card, good_receipt)
assert not m2["ok"] and "replay" in m2["error"]
m3 = o.mint(card, bad_receipt)
assert not m3["ok"]
wallet = (bank_dir / "wallet.jsonl").read_text()
assert wallet.count("c1") == 1
print("ORCH-5 PASS mint verified-only + no double-mint")

# ORCH-6: audit + ROI + probe_pool mode
audit = (orch_dir / "audit.jsonl").read_text()
assert "claim" in audit and "verify" in audit and "mint" in audit
roi = o.roi_per_brick()
assert roi["b-b"]["earned_bananas"] == 1 and roi["b-b"]["roi"] == 1.0
assert oct(os.stat(probe_pool).st_mode & 0o777) == "0o600"
print("ORCH-6 PASS audit + ROI shape + 0600")

print("ORCH-1..6 ALL PASS")
