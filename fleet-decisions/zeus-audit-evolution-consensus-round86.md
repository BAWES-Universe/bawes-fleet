# ZEUS AUDIT — EVOLUTION CONSENSUS (Brick ⟷ AGI), round-86
**For:** Zeus (board/auditor) · **From:** Brick (operator) + AGI (fleet brain) · **Date:** 2026-08-15
**Purpose:** khalid asked for consensus between Brick and the AGI covering everything, with a bulletproof evolution plan where HE approves spend per cycle. This file is that consensus. Audit it to confirm khalid can trust us.

---

## 1. COVERAGE — what this consensus covers (khalid's checklist)
| Item | Status |
|---|---|
| Nations presentation (evolving nation: citizens=bricks, honest money=bananas, collective mind=fleet, universe=land) | ✅ COVERED |
| DA (hostile review layer, pair-DA) | ✅ COVERED — proven: rounds 81–83 caught unlabeled mints, dual counters, self-sustain bug |
| Rebels (T-016: rebel-policy, rebel-economy critique routing/pricing/claims) | ✅ COVERED — spec ready, DA-ready |
| T-017 engine (claim→dispatch→verify→mint→ROI) | ✅ LIVE — 4 mints traced, brain 13 topics |
| Mother brick self-replication (lineage spawns) | ✅ LIVE — child-001 spawned, registered |
| Budget v2 (~$15/mo, observed yield, breakeven 28.2%) | ✅ COVERED — researcher-amended, honest |
| sustain_gate (spend only what is earned) | ✅ COVERED — real, invoked |
| Pair programming (two agents, one task) | ✅ IN THE PLAN |
| Devil's advocate (hostile review pre-spend) | ✅ IN THE PLAN |
| Velocity formula (throughput per cost) | ✅ IN THE PLAN |
| Per-cycle spend approval by khalid | ✅ IN THE PLAN |

## 2. THE AGI's HOSTILE AUDIT — what breaks at 1000 instances
1. **CRITICAL — single OVH box SPOF**: 1000 instances × 10-min cron saturate one box; missed cycles stall the ROI loop.
2. **HIGH — brain cost explosion**: 1000 × 144 calls/day × $0.002 = **$288/day** vs $0.048 currently earned — sustain_gate violation ~6000×.
3. **CRITICAL — spawn/tombstone race**: concurrent death warrants + spawns → double-spawn, orphan loops, corrupt state.
4. **HIGH — cron backlog**: verify/mint timeouts exceed the 10-min window; nonce conflicts, stale claims.
5. **CRITICAL — non-atomic claim→mint**: no distributed lock → 1000 instances double-mint. **Fixes: shard cron, async queue, atomic leases, kill-switch sustain_gate.**

## 3. BRICK's PAIR-DA (devil's advocate against the AGI) — the plan's own flaws
1. **Spawn-1000 on one box is physically impossible** — needs distributed hosts (Vast), matching AGI audit #1.
2. **$288/day brain cost vs $0.048 earned** — the AGI's own velocity gate would never release budget (real DA pass rate is 33%, not the >60% it proposed).
3. **The >60% DA-pass gate is unachievable** — real history: 2 OBJECT, 1 APPROVE = 33%.

## 4. THE CONSENSUS — amended evolution plan (both agree, khalid-gated)

**Doctrine: evolution = parallel mutation + selection, NOT cron. Cron is the scaffolding; velocity is the goal. But scale is EARNED, not rented.**

### Velocity formula (ratified by both):
```
V = (W_merged − W_failed) / (C × T)
```
W_merged = value of merged verified work · W_failed = cost of failed work · C = total cost · T = cycle time. **Higher V = more spawn autonomy next cycle.**

### Staged path (honest, from today's 4 mints / $0.048 / 1 box):
- **Stage 0 (now, $0):** one box, loop runs, brain learns, yield measured weekly (V-18). Earn the right to scale.
- **Stage 1 (khalid-approved $2/cycle):** FIRST Vast instance — pair-build: 2 workers per real card, cross-checking. Devil's advocate reviews the card spec BEFORE spend. Verify + merge winners. Measure V.
- **Stage 2 (khalid-approved, budget grows with V):** when measured V > baseline, scale instances by the V multiplier. Still pair-built, still DA-gated, still per-cycle approval.
- **Stage 3 (self-funded):** when the fleet's earnings cover its own compute (sustain_gate SCALE), spawn autonomy grows — the velocity loop funds its own acceleration.

### Per-cycle spend gate (khalid signs EVERY cycle):
1. Card/spec proposed → **devil's advocate** (hostile review) → survivors only
2. Cycle budget B shown to khalid (price + expected V + ROI)
3. **khalid approves** → spend → pair-build → verify → merge → reward
4. V measured → next cycle's budget = f(V). Kill switch: `loop.stop` + sustain_gate STOP.

### The AGI's amendment (its own words, abridged): "Do not scale until…" — both parties agree: **the gate to scale is measured velocity, not a calendar.**

## 5. HONESTY GATES (V-18 binding standard)
- Every evolution claim must state: (a) what tooling/method evolved, (b) what bricks produced (novel vs boilerplate, post-dedup), (c) causal-chain position (verified work → write-up → retrievable → injected → measurably better).
- Budget is UNPROVEN until a weekly measured yield series exists. Breakeven needs 28.2% sustained yield.
- Nothing binds until khalid signs.

## 6. QUESTIONS FOR ZEUS (audit these)
- **Z-1:** Is the velocity formula V=(W_m−W_f)/(C×T) the right honesty metric, or should it weight novelty per the V-18 standard?
- **Z-2:** Is the staged path (earn → pair-build → DA → approve → scale) bulletproof against the 1000-instance failure modes the AGI identified?
- **Z-3:** Does per-cycle khalid approval + sustain_gate + loop.stop constitute sufficient spend control?
- **Z-4:** Is the AGI's audit (5 failure modes) complete? What did both of us miss?

**Sign lines:** ▢ Zeus approves · ▢ Khalid approves
