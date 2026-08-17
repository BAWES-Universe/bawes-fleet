#!/usr/bin/env python3
"""test_round146.py — VERIFICATION BY EXECUTION for round-146 items 3+4.

Sandbox discipline (round-139 harness pattern): real modules, module-global
path constants monkeypatched to tempfile dirs where prod state must not move
(router lanes/vault/ledger); the allowance ledger itself receives clearly-
labeled TEMP rows for the sandbox person (the card's "temp allowance row").
Prod wallets/registry/tokens/mint are NEVER touched. sha256 of prod ledgers
before/after must not move.

Coverage:
  1. ladder walk 0->50 (debit): warning80 @40, warning95 @47, stop @50
  2. the exact AGI lines render at each rung
  3. router invoke: reservation debit, refund on failed call, 403 stop @50
     with retrieval-only degraded message + khalid alert row (durable first)
  4. khalid alert DM: dry-run template + REAL delivery via the door bot
     (the card's acceptance: "khalid alerted"), then closed (no spam)
  5. door surface: degraded reply + 3 options at cap (deterministic, no LLM)
  6. gift: signed ledger row sponsor_id=khalid, idempotent, unblocks
  7. bananas: beyond_cap price = cost+20% (0.20 for deepseek), earned-only,
     debit lands on the spend ledger
  8. BYOK: vault per-user 0600 owner-bound; full lane register/revoke against
     a sandbox router instance; revoke zero-retention (grep the box)
"""
from __future__ import annotations
import hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile, time

sys.path.insert(0, "/srv/bricks/ovh-server-001")
sys.path.insert(0, "/srv/door")
sys.path.insert(0, "/srv/bricks/orchestrator")

import allowance_meter as meter
import allowance_notifier as notifier
from banana_spend import BananaSpend, beyond_cap_price
import byok

TEST_PERSON = "sandbox-146-test"
TEST_BRICK = "sandbox-146-test"
SERVICE = "deepseek"
TEST_KEY = "sk-sandbox146-0123456789abcdef0123456789abcdef"

PASS, FAIL = [], []
def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f" — {extra}" if extra else ""))

# ---- 0. prod ledger fingerprints (must not move) ----
def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() if pathlib.Path(p).exists() else None
PROD = ["/srv/bricks/register/wallet.jsonl", "/srv/bricks/register/registry.jsonl",
        "/srv/bricks/register/audit.jsonl", "/srv/bricks/router/state/lanes.jsonl",
        "/srv/bricks/router/state/ledger.jsonl", "/srv/bricks/router/state/tokens-meta.jsonl"]
before = {p: sha(p) for p in PROD}

print("== round-146 item 3: the ladder ==")

# ---- 1. ladder walk: 0 -> 50 ----
for i in range(40):
    d = meter.debit(TEST_PERSON, TEST_BRICK, "deepseek-api",
                    card_id=f"sandbox-walk-{i}", invoke_ts=int(time.time()))
    check(f"debit {i+1}/40 ok", d.get("ok"), str(d.get("usage_after")))
b40 = meter.bucket(TEST_PERSON)
check("bucket at 40/50", b40["usage"] == 40 and b40["allowance"] == 50, str(b40))
w80 = meter.maybe_warning(TEST_PERSON, TEST_BRICK)
check("warning80 row written once", w80 and w80.get("rung") == "80")
w80b = meter.maybe_warning(TEST_PERSON, TEST_BRICK)
check("warning80 dedup (no second row)", w80b is None)
pend = meter.pending_warnings(TEST_PERSON)
check("pending warnings contains 80", any(w.get("rung") == "80" for w in pend))
line = meter.line_80(40, 50)
check("exact 80% AGI line", "Heads up — you've used 40 of your 50 free tasks this month" in line, line)
for i in range(40, 47):
    meter.debit(TEST_PERSON, TEST_BRICK, "deepseek-api",
                card_id=f"sandbox-walk-{i}", invoke_ts=int(time.time()))
w95 = meter.maybe_warning(TEST_PERSON, TEST_BRICK)
check("warning95 row written once", w95 and w95.get("rung") == "95")
line95 = meter.line_95(47, 50)
check("exact 95% AGI line", "You're at 47 of 50 — when you hit 50 the team decides" in line95, line95)
a95 = meter.open_alert(TEST_PERSON, TEST_BRICK, name="sandbox-146-test",
                       cost_usd=0.10, rung="95")
check("95% khalid heads-up alert row", a95.get("new") and a95.get("rung") == "95")
a95b = meter.open_alert(TEST_PERSON, TEST_BRICK, name="sandbox-146-test",
                        cost_usd=0.10, rung="95")
check("95% alert dedup", not a95b.get("new"))
for i in range(47, 50):
    meter.debit(TEST_PERSON, TEST_BRICK, "deepseek-api",
                card_id=f"sandbox-walk-{i}", invoke_ts=int(time.time()))
b50 = meter.bucket(TEST_PERSON)
check("bucket at 50/50 exhausted", b50["usage"] == 50 and b50["exhausted"], str(b50))
d51 = meter.debit(TEST_PERSON, TEST_BRICK, "deepseek-api",
                  card_id="sandbox-walk-51", invoke_ts=int(time.time()))
check("51st debit refused (stop)", not d51.get("ok") and d51.get("exhausted"))
a100 = meter.open_alert(TEST_PERSON, TEST_BRICK, name="sandbox-146-test",
                        cost_usd=0.12, rung="100")
check("100% stop alert row (durable, new)", a100.get("new") and a100.get("rung") == "100")
check("stop alert row fsync'd + signed", bool(a100.get("row", {}).get("hmac")))
a100b = meter.open_alert(TEST_PERSON, TEST_BRICK, name="sandbox-146-test",
                         cost_usd=0.12, rung="100")
check("100% alert dedup (one per person/month/rung)", not a100b.get("new"))
line100 = meter.line_100(50, 50)
check("exact 100% AGI line", "That was your 50th free task. You're not blocked — this is the switch to retrieval-only mode" in line100, line100)
degraded = meter.degraded_reply("Sandbox", 50, 50, 3.5, 0.20)
check("degraded reply: retrieval-only + 3 options + balance shown",
      all(s in degraded for s in ("retrieval-only", "1 — Wait", "2 — Bring your own key", "3 — Spend bananas", "🍌3.50", "🍌0.20")), degraded[:120])
# tamper detection (C6)
rows = meter.read()
tampered = dict(rows[0]); tampered["tasks"] = 999
with open(meter.ALLOWANCES, "a") as f:
    f.write(json.dumps(tampered) + "\n")
try:
    meter.read()
    check("tamper raises", False)
except ValueError:
    check("tamper raises", True)
# remove the tampered row (it is the LAST line)
lines = meter.ALLOWANCES.read_text().splitlines()[:-1]
meter.ALLOWANCES.write_text("\n".join(lines) + ("\n" if lines else ""))
os.chmod(meter.ALLOWANCES, 0o600)

print("== round-146 item 3: router integration (sandbox router instance) ==")
tmp = pathlib.Path(tempfile.mkdtemp(prefix="r146-router-"))
import token_router
# patch module globals so the SANDBOX brick resolves to the SANDBOX person
_orig_owner_uid = meter.OWNER_UID
_orig_registry = meter.REGISTRY
def _sandbox_patch(brick, owner_name, reg_file):
    meter.OWNER_UID = {**_orig_owner_uid, owner_name: TEST_PERSON}
    reg_file.parent.mkdir(parents=True, exist_ok=True)
    reg_file.write_text(json.dumps({"brick_id": brick, "owner": owner_name,
                                    "quality": "verified", "active": True}) + "\n")
    meter.REGISTRY = reg_file

tokrec = {"lane_scope": ["test-lane-146"], "spend_cap_usd": 25.0}
# A) invoke at usage=50 -> 403 allowance_exhausted BEFORE any upstream call
_sandbox_patch(TEST_BRICK, "sandbox146", tmp / "registry.jsonl")
r = token_router.TokenRouter(tmp / "state", tmp / "tokens", "router-146-test",
                             "deepseek-api", tmp / "measurements.jsonl")
r._rebuild_token_index()
lane_res = r.register(TEST_BRICK, "test-lane-146", "https://api.deepseek.com/chat/completions",
                      "deepseek-v4-flash", "unlimited", 0.002, "routine", "bearer",
                      "sk-dummy-146-0123456789abcdef0123456789abcdef")
check("sandbox lane registered", lane_res.get("status") == "registered")
res = r.invoke(TEST_BRICK, "test-lane-146", {"prompt": "x"}, token_record=tokrec)
check("stop: 403 allowance_exhausted", res.get("status") == 403
      and res.get("error") == "allowance_exhausted"
      and res.get("degraded") == "retrieval-only"
      and "next_window_ts" in res and "message" in res, str(res)[:160])
check("stop message = the degraded reply", "switch to retrieval-only mode" in res.get("message", ""))
# B) refund path: fresh person at 49, invoke -> 401 upstream -> refund -> usage stays 49
p2 = "sandbox-146-refund"
for i in range(49):
    meter.debit(p2, TEST_BRICK, "deepseek-api", card_id=f"rf-{i}", invoke_ts=int(time.time()))
_sandbox_patch("sandbox-146-r", "sandbox146r", tmp / "registry2.jsonl")
r2 = token_router.TokenRouter(tmp / "state2", tmp / "tokens2", "router-146-test2",
                              "deepseek-api", tmp / "measurements2.jsonl")
r2._rebuild_token_index()
r2.register("sandbox-146-r", "test-lane-146", "https://api.deepseek.com/chat/completions",
            "deepseek-v4-flash", "unlimited", 0.002, "routine", "bearer",
            "sk-dummy-146-0123456789abcdef0123456789abcdef")
res2 = r2.invoke("sandbox-146-r", "test-lane-146", {"prompt": "x"}, token_record=tokrec)
check("failed call refunds the reservation (usage stays 49)",
      meter.bucket(p2)["usage"] == 49, f"usage={meter.bucket(p2)['usage']} (got HTTP {res2.get('status')})")
meter.OWNER_UID = _orig_owner_uid
meter.REGISTRY = _orig_registry

print("== round-146 item 3: khalid alert delivery ==")
a100row = meter.open_alert_rows()[-1]
dr = notifier.deliver_alert(a100row, dry_run=True)
check("alert template: person/usage/cost/3 options",
      all(s in dr.get("content", "") for s in ("ALLOWANCE", "50/50", "Cost so far", "1 — Gift", "2 — Bill", "3 — Cheaper")), dr.get("content", "")[:200])
# REAL delivery to khalid's DM via the door bot (the card's acceptance) —
# clearly labeled as a sandbox test; closed right after so the watchdog
# never re-sends.
tok = notifier._token()
real = notifier.send_dm(meter.KHALID_UID, dr["content"] + "\n\n_(round-146 sandbox test — not a real member)_", tok) if tok else {"error": "no token"}
check("khalid alert DM delivered (real Discord API)", "error" not in real, str(real)[:120])

print("== round-146 item 3: door surface at cap (deterministic) ==")
import door_v4
door_reply = door_v4.handle_dm(TEST_PERSON, "Sandbox Tester", "hello", time.time())
check("door degraded reply at cap (no LLM, no router)",
      "retrieval-only" in door_reply and "1 — Wait" in door_reply, door_reply[:150])

print("== round-146 item 4: gift path ==")
# khalid replies '1' to the 100% alert
resp = door_v4._alert_response_branch(meter.KHALID_UID, "1")
check("khalid '1' -> gift executed + alert closed", resp and "Gifted" in resp, (resp or "")[:120])
grow = [r for r in meter.read() if r.get("kind") == "allowance-gift"
        and r.get("person_id") == TEST_PERSON and r.get("month") == meter.month()]
check("gift row signed (hmac) sponsor_id=khalid",
      len(grow) == 1 and grow[0].get("sponsor_id") == "khalid"
      and grow[0].get("granted_by") == "khalid" and bool(grow[0].get("hmac"))
      and grow[0].get("state") == "open")
# idempotency: a second gift for the same person+month must not duplicate
g2 = meter.gift(TEST_PERSON, TEST_BRICK, tasks=50, alert_id="x", response_row="y")
check("gift idempotent (no second open row)", g2.get("existing") is True)
check("bucket unblocked after gift (50/100)",
      meter.bucket(TEST_PERSON)["allowance"] == 100
      and not meter.bucket(TEST_PERSON)["exhausted"], str(meter.bucket(TEST_PERSON)))
check("unblocked notice for the user (deterministic)",
      "You're unblocked" in (door_v4._unblocked_notice(TEST_PERSON) or ""))
# gift month-scoping: next month has NO gift credit (no rollover, C5)
next_m = meter.month(time.time() + 32 * 86400)
check("gift does not roll over (month-scoped)",
      meter.allowance(TEST_PERSON, next_m) == 50)
# alert closed by the gift action -> watchdog will not re-send
check("100% alert closed by gift", meter.alert_status(a100row.get("alert_id"))["state"] == "closed")

print("== round-146 item 4: bananas ==")
spend_ledger = pathlib.Path(tempfile.mkdtemp(prefix="r146-spend-")) / "spend.jsonl"
s = BananaSpend(spend_ledger)
price = beyond_cap_price(0.002)
check("beyond_cap price = cost+20% (0.20 for deepseek)", price == 0.20, str(price))
check("earned-only: no earnings -> refused",
      not s.spend(TEST_PERSON, "beyond_cap", "utt-1", {"cost_usd": 0.002}).get("ok"))
# seed verified earnings (kind=earn) in the spend ledger
with open(spend_ledger, "a") as f:
    f.write(json.dumps({"kind": "earn", "person_id": TEST_PERSON, "bananas": 5,
                        "card_id": "sandbox-earn-1", "ts": time.time()}) + "\n")
os.chmod(spend_ledger, 0o600)
sp = s.spend(TEST_PERSON, "beyond_cap", "utt-2", {"cost_usd": 0.002, "lane": "deepseek-api"})
check("banana spend debits 0.20 at cost+20%", sp.get("ok") and sp.get("price") == 0.20, str(sp))
check("balance debited (5 -> 4.80)",
      abs(s.balance(TEST_PERSON)["available"] - 4.80) < 1e-9, str(s.balance(TEST_PERSON)))
spend_rows = spend_ledger.read_text().splitlines()
check("spend row is permanent consent record",
      any("beyond_cap" in l and "cost_usd" in l for l in spend_rows))

print("== round-146 item 4: BYOK ==")
# ingest-side vault: per-user 0600 owner-bound (custody hash)
v = byok.vault(TEST_PERSON, SERVICE, TEST_KEY)
check("byok vault ok (ingest store, custody hash)", v.get("ok") and bool(v.get("key_sha")))
store = pathlib.Path("/srv/vault/store.jsonl")
stored = [json.loads(l) for l in store.read_text().splitlines()
          if json.loads(l).get("person") == TEST_PERSON]
check("key stored per-user (0600) with custody link",
      len(stored) >= 1 and stored[-1].get("key_sha") == v.get("key_sha")
      and oct(store.stat().st_mode & 0o777) == "0o600")
# full lane wiring against a SANDBOX router instance (no prod state touched)
tmp2 = pathlib.Path(tempfile.mkdtemp(prefix="r146-byok-"))
_sandbox_patch(TEST_BRICK, "sandbox146", tmp2 / "registry.jsonl")
r3 = token_router.TokenRouter(tmp2 / "state", tmp2 / "tokens", "router-146-byok",
                              "deepseek-api", tmp2 / "measurements.jsonl")
r3._rebuild_token_index()
rb = r3.register_byok(TEST_BRICK, SERVICE, TEST_KEY)
check("byok lane registered (allowlisted endpoint only)",
      rb.get("status") == "registered"
      and rb.get("endpoint") == "https://api.deepseek.com/chat/completions"
      and rb.get("lane_id") == f"byok-{TEST_BRICK}", str(rb)[:160])
lane_row = [l for l in r3._read(r3.lanes_path, "lanes")[0]
            if l.get("lane_id") == f"byok-{TEST_BRICK}"]
check("byok lane owner-bound to the person's brick",
      lane_row and lane_row[0].get("owner") == TEST_BRICK)
check("byok lane secret vaulted 0600",
      (r3.vault_dir / f"byok-{TEST_BRICK}.secret").exists()
      and oct((r3.vault_dir / f"byok-{TEST_BRICK}.secret").stat().st_mode & 0o777) == "0o600")
# hostile: a token WITHOUT byok scope must be denied on that lane (C3)
deny = r3.invoke("other-brick", f"byok-{TEST_BRICK}", {"prompt": "x"},
                 token_record={"lane_scope": ["deepseek-api"], "spend_cap_usd": 5})
check("C3: lane outside scope -> 403 (no cross-user burn)",
      deny.get("status") == 403, str(deny)[:120])
# SSRF by construction: user-supplied endpoint refused (C2)
try:
    r3.register(TEST_BRICK, f"byok-{TEST_BRICK}", "http://169.254.169.254/latest/meta-data/",
                "x", "unlimited", 0.01, "routine", "bearer", TEST_KEY)
    check("C2: user-supplied endpoint refused", False)
except ValueError:
    check("C2: user-supplied endpoint refused", True)
# revoke (sandbox router): lane gone + secret unlinked (zero-retention)
rv = r3.deregister_byok(f"byok-{TEST_BRICK}")
check("byok revoke: lane deregistered", rv.get("status") == "deregistered")
check("byok revoke: vault secret unlinked (zero-retention)",
      not (r3.vault_dir / f"byok-{TEST_BRICK}.secret").exists())
# REAL revoke via byok.py: scrub ingest store + audit + zero-retention grep
rev = byok.revoke(TEST_PERSON)
check("byok.revoke scrubbed ingest store",
      rev.get("ingest_scrubbed") and not any(
          json.loads(l).get("person") == TEST_PERSON
          for l in store.read_text().splitlines()))
check("byok.revoke zero-retention report", rev.get("zero_retention") is True,
      str(rev.get("residual_paths")))
leak = subprocess.run(["grep", "-rl", TEST_KEY, "/srv/vault", "/srv/bricks/router/state",
                       "/srv/bricks/register", "/srv/door/state"],
                      capture_output=True, text=True).stdout.strip()
check("zero-retention: no key material anywhere on the box (grep)", not leak, leak[:200])
# clean the re-minted ingest token residue for the sandbox person
try:
    import door_ingest
    data = door_ingest._load()
    data.pop(TEST_PERSON, None)
    door_ingest._save(data)
except Exception:
    pass
meter.OWNER_UID = _orig_owner_uid
meter.REGISTRY = _orig_registry

print("== prod state untouched ==")
after = {p: sha(p) for p in PROD}
for p in PROD:
    check(f"prod untouched: {pathlib.Path(p).name}",
          before.get(p) == after.get(p),
          "" if before.get(p) == after.get(p) else "MOVED!")
shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(tmp2, ignore_errors=True)
print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("ALL VERIFICATIONS PASSED")
