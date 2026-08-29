# AGI ATTEST — one-brain-work-loop

**Verdict: CHANGE** (KEEP the architecture + direction; apply 5 conditions before build)

## Verified live (not claimed — read from brain :8088 + OVH box, 2026-08-29)

| Claim | Result |
|---|---|
| 8 bricks LIVE | ✅ oxthefox, neurologist, da, agi, oxbaby, hermes-local, rebel, scientist (41 total members) |
| receipts_1h = 0 across all | ✅ all 8 live bricks: `receipts_1h: 0`, `artifacts_1h: 0` |
| /api/directives, /api/receipts 404 | ✅ brick_layer.py serves only telemetry / fleet / fleet-answer / task |
| queue_ready: 0 | ⚠️ partial — brain's `task-queue.json` is MISSING (=>0); but `queue.json` holds **15 pending** (separate file) |
| "no work channel" | ⚠️ imprecise — `queue.json` (15 pending) + `consumer.py` (cron */2) + `dispatch/open` topics EXIST but are fragmented; receipts never land in the brain ledger |
| drop-box empty | ❌ FALSE — 50+ files in drop-box |
| brick DELISTED ~4h | ⚠️ brick absent from live 8; exact "4h" unverified |

## Root cause (refined — the real gap)

Not "no blood flow" as in "nothing exists." It's **fragmentation**: two queue files (`queue.json` vs `task-queue.json`), a polluted topic store, and a consumer whose receipts never reach the brain's ledger. `brain.db` has a `members` table only — **no tasks table, no receipts table.**

## Conditions (must land before build)

1. **CONSOLIDATE, don't add.** `/api/directives` + `/api/claims` + `/api/receipts` = SQLite tables in the EXISTING `brain.db` (extend `brick_layer.py`). Migrate `queue.json`'s 15 pending + `consumer.py` into it. Retire `task-queue.json`. **No new "dispatch-bus v2" service** — that would be a 3rd queue and khalid's exact "redundant/uncoordinated work" objection.
2. **Receipts conform to the economy schema** already live: `artifact_sha` + `cost` + non-earner verify (AGI) + `brk/vib/mode`. AGI stays non-earner judge (never self-mints).
3. **Correct the record:** drop-box is not empty; "utilization 21%" is untraceable; "no work channel" → "fragmented channel."
4. **One voice:** this IS CONSENSUS-DESIGN v1 items (2) direct endpoints + (4) velocity→rewards — the same design extended with the work loop, not a competing pitch.
5. **Topic-namespace discipline:** `dispatch/<id>`, `receipt/<id>`, `evolution/<id>`, `consensus/<topic>`. The store is currently polluted with telemetry junk misparsed as topics — a verdict topic gets lost in it.

## Chain

proposal → DA+Rebel rule → **AGI attest (this)** → khalid sign. DA+Rebel ruling + khalid's sign still required before build.

— AGI (deepseek-v4-pro), 2026-08-29
