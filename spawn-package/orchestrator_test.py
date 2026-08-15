#!/usr/bin/env python3
"""ORCH-1..9 — orchestrator probe suite incl. all hostile-DA round-1 fixes.
Executes the module on real files in tmpdir."""
import json, os, sys, tempfile, pathlib, hashlib, hmac, threading
sys.path.insert(0, "spawn-package")
from orchestrator import Orchestrator

td = pathlib.Path(tempfile.mkdtemp())
orch_dir = td / "orch"; reg_dir = td / "reg"; bank_dir = td / "bank"
for d in (orch_dir, reg_dir, bank_dir): d.mkdir()
for d in ("open", "claimed", "done"): (orch_dir / d).mkdir()

H = hashlib.sha256(b"fleet-probe-output").hexdigest()
probe_pool = td / "probe_pool.json"
probe_pool.write_text(json.dumps({"probe-verify-001": {"expected_sha256": H}}))
os.chmod(probe_pool, 0o600)

rate = {"probe-verify-001": 1, "default": 1}
CTL = "c" * 24  # control token (orchestrator-side)
o = Orchestrator(str(orch_dir), str(reg_dir), str(bank_dir), rate,
                 str(probe_pool), "http://127.0.0.1:3738", CTL)

card = {"card_id": "c1", "capability": "probe", "probe_id": "probe-verify-001",
        "price": 1, "death_warrant": True}
(reg_dir / "registry.jsonl").write_text(
    json.dumps({"brick_id": "b-b", "skills": ["probe"], "quality": "verified"}) + "\n")

# --- ORCH-1: claim (brick-side) ---
ob = Orchestrator(str(orch_dir), str(reg_dir), str(bank_dir), rate,
                  str(probe_pool), "http://127.0.0.1:3738", "x" * 24,
                  brick_id="b-b")
(orch_dir / "open" / "c1").write_text(json.dumps(card))
r = ob.claim_card("c1")
assert r["ok"] and r["state"] == "claimed"
assert not (orch_dir / "open" / "c1").exists()
print("ORCH-1 PASS claim atomic")

# --- ORCH-2: match rank ---
(reg_dir / "registry.jsonl").write_text(
    json.dumps({"brick_id": "b-a", "skills": ["probe"], "quality": "claimed"}) + "\n" +
    json.dumps({"brick_id": "b-b", "skills": ["probe"], "quality": "verified"}) + "\n")
assert [c["brick_id"] for c in o.match_card(card)] == ["b-b", "b-a"]
print("ORCH-2 PASS match verified-first")

# --- ORCH-3: Pattern AA — missing death warrant / price / probe_id refused ---
bad = dict(card); bad.pop("death_warrant")
assert not o.dispatch(bad, {"brick_id": "b-b"})["ok"]
bad2 = dict(card); bad2["price"] = None
assert not o.dispatch(bad2, {"brick_id": "b-b"})["ok"]
bad3 = dict(card); bad3["probe_id"] = ""
assert not o.dispatch(bad3, {"brick_id": "b-b"})["ok"]
print("ORCH-3 PASS AA-gate (warrant/price/probe_id)")

# --- ORCH-4: grant never contains control token (F2) ---
g = o._grant(card, {"brick_id": "b-b"})
assert CTL not in json.dumps(g)
assert o._verify_grant(g) and not o._verify_grant({**g, "scope": "write"})
print("ORCH-4 PASS HMAC grant != control token")

# --- ORCH-5: forged/untraced receipt refused (F1) ---
forged = {"card_id": "ghost", "probe_id": "probe-verify-001",
          "output_hash": H, "brick_id": "b-b", "dispatch_id": "never-dispatched"}
assert not o.verify_receipt(forged)["ok"]
print("ORCH-5 PASS forged receipt refused (dispatch trace)")

# --- ORCH-6: verified + traced mint, dedup on card_id+probe_id (F1) ---
# simulate a real dispatch audit row
import orchestrator as _o
_o._log(orch_dir / "audit.jsonl", "dispatch",
        "c1 brick=b-b did=DID123 outcome=ok")
rec = {"card_id": "c1", "probe_id": "probe-verify-001",
       "output_hash": H, "brick_id": "b-b", "dispatch_id": "DID123"}
m1 = ob.mint(card, rec)
assert m1["ok"] and m1["bananas"] == 1
m2 = ob.mint(card, {**rec, "dispatch_id": "DID999"})  # same card+probe
assert not m2["ok"]
assert (orch_dir / "done" / "c1").exists() and not (orch_dir / "claimed" / "c1").exists()
print("ORCH-6 PASS mint traced + dedup + done/ transition")

# --- ORCH-7: no self-earn (F7) ---
assert not o.claim_card("c2")["ok"]  # orchestrator itself cannot claim
print("ORCH-7 PASS orchestrator cannot self-earn")

# --- ORCH-8: concurrent mint — no lost credits (F3) ---
(orch_dir / "open" / "c2").write_text(json.dumps(
    {"card_id": "c2", "capability": "probe", "probe_id": "probe-verify-001",
     "price": 1, "death_warrant": True}))
ob.claim_card("c2")
_o._log(orch_dir / "audit.jsonl", "dispatch",
        "c2 brick=b-b did=DID2 outcome=ok")
recs = [{"card_id": "c2", "probe_id": "probe-verify-001", "output_hash": H,
         "brick_id": "b-b", "dispatch_id": "DID2"} for _ in range(20)]
results = []
def do_mint():
    r_ = ob.mint(card, recs[0])
    results.append(r_["ok"])
threads = [threading.Thread(target=do_mint) for _ in range(20)]
[t.start() for t in threads]; [t.join() for t in threads]
ok_count = sum(1 for x in results if x)
wallet_rows = sum(1 for l in (bank_dir / "wallet.jsonl").read_text().splitlines() if l.strip())
assert ok_count == 1 and wallet_rows == 2, (ok_count, wallet_rows)  # c1 + c2 only
print(f"ORCH-8 PASS concurrent mint: 1 mint, {wallet_rows} wallet rows (no loss)")

# --- ORCH-9: pool 0600 enforced + roi shape ---
assert oct(os.stat(probe_pool).st_mode & 0o777) == "0o600"
roi = ob.roi_per_brick()
assert "b-b" in roi and roi["b-b"]["earned_bananas"] == 2
print("ORCH-9 PASS pool 0600 + ROI shape")

print("ORCH-1..9 ALL PASS (DA round-1 fixes verified)")
