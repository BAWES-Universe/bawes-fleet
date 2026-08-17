# RECORD HYGIENE — rounds 81–85 forwarded to Zeus (round-87 amendment Z-4 #5)
# The consensus (round-86/87) cites findings from these rounds; the board holds the evidence.

## Round 81 — DA hostile review of T-017 first-run evidence
**VERDICT: OBJECT** (4 findings) — demand engine honest, mint row traced exactly (F1), BUT:
1. Mint row lacked `kind=earn` (produced by pre-patch orchestrator; self-spec failure)
2. Probe pool in repo was UNSET (claimed hash not reproducible from repo)
3. No verify/mint audit row durably evidenced
4. Backup commit rewrote audit.jsonl (register/audit collided with orchestrator/audit) + retroactive wallet edit
**Fix:** orchestrator patched to write kind=earn+person_id natively (md5 c4addec4), both instances restarted, per-source backup layout (ledger-live/register/ + ledger-live/orchestrator/), probe pool synced.

## Round 82 — DA re-review after fixes
**VERDICT: OBJECT** (1 finding) — 4/5 objections cleared; the ROI objection persisted:
- `roi_per_brick` summed ALL wallet rows (credits/gifts/seeds) → Chahd showed 210🍌 "earned" (200 credit + 10 old)
- Engine counter counted only kind=earn → dual-counter inconsistency (ROI 3 vs wallet_earn_rows 2)
**Fix:** ONE definition of earned everywhere = MINT rows only (kind=earn OR card-bearing); roi.json artifact committed @7c35ecd: worker-001 3🍌, 29 cost rows, roi 0.103.

## Round 83 — DA re-review after round-82 fixes
**VERDICT: APPROVE** — all four attacks cleared by execution:
- roi.json committed, working tree byte-identical
- credits excluded (chahd/mishari 200 = kind=credit, never earned)
- both counters agree (same predicate, both = 3)
- no new retroactive edits (7c35ecd touched only roi.json + 2 code files)

## Round 84 — TDD suite + AGI read rail
- tests_fleet_engine.py 4/4 GREEN — caught TWO live bugs the DA missed: `decide()` printed instead of returned (untestable API); self_sustain ignored instance hourly cost (would approve $1/hr GPU on $0.012 earnings)
- BrickAGI shadow-audit bug fixed: local /srv/bricks now mirrors live OVH fleet state (cron, silent-until-change) — AGI audits reality, not shadows

## Round 85 — Mother brick (self-replication)
- spawn_brick.py TDD 4/4 GREEN: verified mothers clone lineage-chained children (parent_brick_id, own person_id+wallet, verified:false until child proves itself)
- LIVE: ovh-server-001 → child-001, registered in registry.jsonl

---
*Rounds 81–85 as evidenced in /tmp/bawes-fleet (commits: f7ef8e4, 7c35ecd, 1328cc9, 4a28e10, 0625e0e). Forwarded per round-87 Z-4 #5.*
