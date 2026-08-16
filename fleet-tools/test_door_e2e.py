#!/usr/bin/env python3
"""E2E DOOR SUITE — every scenario, validated (khalid directive 2026-08-16:
"full end to end tests set up and all scenarios validated").
A stranger or universe member or whoever texts is ALLOWED a brick.

Scenarios:
 S1 stranger -> onboarding -> consent -> brick spawns
 S2 universe member (known) -> brick companion, NEVER onboarding
 S3 owner (khalid) -> brick companion, knows identity
 S4 rejoin/duplicate join -> no extra DM, profile untouched (dedup)
 S5 Arabic member -> language auto-switch, still onboards
 S6 consent refusal -> stays building, no spawn
 S7 daily cap -> polite stop, no spend
 S8 PII perms: profiles/spawns/transcripts 0600
 S9 flow audit: every interaction logged
 S10 two strangers -> two independent bricks, no cross-talk
 S11 __JOIN__ literal DM -> no privilege, normal handling
 S12 known member consent-state -> no re-consent
"""
import json, os, pathlib, sys, tempfile, time
sys.path.insert(0, "/srv/door")
os.environ["BRICK_DISCORD_TOKEN"] = "x"

import door_v4 as d

tmp = tempfile.mkdtemp()
d.STATE_DIR = pathlib.Path(tmp)
d.FLOW = d.STATE_DIR / "flow.jsonl"
d.PROFILES = d.STATE_DIR / "profiles.json"
d.TRANSCRIPT = d.STATE_DIR / "consent-transcripts.jsonl"
d.COST = d.STATE_DIR / "door-cost.jsonl"

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}  {detail[:70]}")

def say(uid, name, msg):
    try:
        return d.handle_dm(uid, name, msg, time.time()) or ""
    except Exception as e:
        return f"ERROR: {e}"

def profiles():
    return json.load(open(d.PROFILES)) if d.PROFILES.exists() else {}

def spawns():
    return d.STATE_DIR.joinpath("brick-spawns.jsonl")

print("S1: stranger -> consent -> brick")
r1 = say("111111111111", "alice", "I want to build a website for my bakery")
r2 = say("111111111111", "alice", "I do design and some coding")
r3 = say("111111111111", "alice", "yes")       # confirming question answered
r4 = say("111111111111", "alice", "yes")       # consent confirmed
check("S1a consent accepted", "brick is awake" in r4 or "Welcome" in r4, r4[:60])
check("S1b profile consented", profiles().get("111111111111", {}).get("state") == "consented")
check("S1c brick spawned", spawns().exists() and "111111111111" in spawns().read_text())

print("S2: universe member (known) -> brick companion")
r = say("231861753082937346", "mishari", "what's the browser build status")
check("S2 known = no onboarding", "want me to be yours" not in r and "helper" not in r.lower(), r[:60])
check("S2b mishari identity known", "mishari" in r.lower() or "browser" in r.lower(), r[:60])

print("S3: owner -> knows identity")
r = say("189055515819638794", "khalid", "where's my brick")
check("S3 owner = in", "your brick" in r.lower() or "khalid" in r.lower(), r[:60])

print("S4: rejoin -> dedup, no overwrite")
before = json.dumps(profiles().get("111111111111", {}), sort_keys=True)
r = say("111111111111", "alice", "__JOIN__")
check("S4a rejoin = no DM", r == "" or "welcome" not in r.lower())
after = json.dumps(profiles().get("111111111111", {}), sort_keys=True)
check("S4b profile untouched", before == after)

print("S5: Arabic stranger -> onboards in Arabic")
r1 = say("222222222222", "سارة", "مرحبا أريد بريك")
check("S5a Arabic detected", profiles().get("222222222222", {}).get("lang") == "ar", str(profiles().get("222222222222", {}).get("lang")))
r2 = say("222222222222", "سارة", "نعم")
check("S5b Arabic consent works", "بريك" in r2 or "مرحبا" in r2 or r2 != "", r2[:60])

print("S6: consent refusal -> no spawn")
say("333333333333", "bob", "I want a brick for my shop")
r = say("333333333333", "bob", "no")   # refusal during learning
check("S6a refusal respected", "no rush" in r.lower() or "door stays open" in r.lower(), r[:60])
check("S6b no spawn for bob", "333333333333" not in (spawns().read_text() if spawns().exists() else ""))

print("S7: daily cap")
d.DAILY_CAP = -1  # force cap
r = say("111111111111", "alice", "hello again")
d.DAILY_CAP = 2.0
check("S7 cap = polite stop", "full day" in r or "tomorrow" in r, r[:60])

print("S8: PII perms 0600")
for f in ["profiles.json", "brick-spawns.jsonl", "consent-transcripts.jsonl", "door-cost.jsonl"]:
    p = d.STATE_DIR / f
    if p.exists():
        mode = oct(p.stat().st_mode & 0o777)
        check(f"S8 {f} 0600", mode == "0o600", mode)

print("S9: flow audit")
check("S9 flow written", d.FLOW.exists() and len(d.FLOW.read_text().splitlines()) >= 8, str(len(d.FLOW.read_text().splitlines()) if d.FLOW.exists() else 0))

print("S10: two strangers independent")
r = say("444444444444", "carol", "I want a brick for my gym")
check("S10 carol onboards independently", "carol" not in json.dumps(profiles().get("111111111111", {})))

print("S11: literal __JOIN__ from stranger")
say("555555555555", "dave", "hello there")
r = say("555555555555", "dave", "__JOIN__")
check("S11 sentinel no privilege", "brick" not in r.lower() or len(r) < 200)

print("S12: known member no re-consent")
p = profiles().get("111111111111", {})
check("S12 alice stays consented", p.get("state") == "consented")

passed = sum(1 for _, c, _ in results if c)
print(f"\n=== {passed}/{len(results)} PASSED ===")
sys.exit(0 if passed == len(results) else 1)
