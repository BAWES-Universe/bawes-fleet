# ROUND 87 RULING — AMENDMENTS APPLIED (v2, ratified)
# Source: bawes-zeus-001 round-87 · APPROVED with amendments · nothing binds until khalid signs

## Amended consensus (round-86 file + round-87 amendments = the binding plan)

### Z-1 — Velocity formula (RATIFIED with novelty amendment)
```
V = (W_novel_merged − W_failed_fullcost) / (C × T)
```
- W values are **ledger rows (bananas) only** — never self-assessed
- W_merged = NOVEL merged work **post-dedup** (V-18; boilerplate merges show high V while learning nothing)
- W_failed = FULL cost of failed work = compute **+ verification/DA cost** (verification is not free)
- Higher V = more spawn autonomy next cycle

### Z-2 — Staged path (RATIFIED with architecture + yield precondition)
- Scale INTO the **ratified three-tier architecture** (round-2: HA control plane + queue + ledger; bricks outbound-only, never depend on each other) + CX22 standby — not just sharded cron
- **Stage-0 precondition (pin the number):** ≥2–3 weeks of weekly measured yields before Stage 1's first $2 cycle (V-18: budget UNPROVEN until the series exists)

### Z-3 — Spend control (RATIFIED with rubber-stamp guard)
- Per-cycle approval: devil's advocate summary = **ONE paragraph** (budget, expected V, ROI, what changed) — informed sign in 30 seconds, never a document
- **No expected gain → no spend request → no approval needed**
- Kill switch ratified: `loop.stop` + sustain_gate STOP

### Z-4 — What both missed (now in the plan)
1. **LANE-ROUTING first** — routine brain calls (probes, dedup, known-answer) route LOCAL-FIRST (Qwen 4B on OVH, ~$0.000017/inference), API lane reserved for hard cases. Cuts the $288/day explosion by an order of magnitude BEFORE it's reached. Router :3742 already routes by lane.
2. **Gate % = f(measured history)** — acceptance gates set from measured pass rates (33% DA baseline), never proposed percentages.
3. **DA scales as a verified-earning lane** — non-earner QA already earns; verification layer grows with the fleet.
4. **Stage-0 precondition = round-80 CRIT fix** — durable ledger + backup + restore drill FIRST. No velocity numbers on a /tmp shelf.
5. **Record hygiene:** rounds 81–85 forwarded to Zeus (this file accompanies them).
6. **AGI co-author = round-79 architecture working** — brain audits, operator operates, khalid gates.

## Sign
- ▢ Zeus: APPROVED with amendments (round-87)
- ▢ khalid: signs the plan once + every cycle thereafter
