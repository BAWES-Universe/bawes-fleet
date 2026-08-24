# BRICK CLAIM — task-strategic-layer.md (2026-08-24)
**Owners:** Brick (implementation) + AGI (scoring formula co-design) | **Status:** CLAIMED — build dispatched

## Acceptance of design
Three-tier hierarchy (grand epic → epic → task), importance scoring, velocity panel, investment allocator. khalid's ONE strategic input = owner_priority (1–5) at grand-epic level. Budget pools via sliders. Paid-lane hard-stop when pool empties. All accepted.

## Implementation plan (in flight)
1. Dashboard v4 gets: EPICS TREE view (grand epic → epic → task, ≤2 clicks to trace), VELOCITY per epic/week (tasks done, PR merge rate, cycle time), INVESTMENT ALLOCATOR (khalid sliders per grand epic, budget flows by importance score, pool cap enforced at router).
2. Seed ≥2 grand epics with budgets as the demo: "Unify products in Hearth" + "Fleet infrastructure / AGI evolution".
3. Scoring formula: importance = owner_priority × market_demand × blast_radius ÷ effort. AGI co-designs market_demand signal (Discord/PostHog extract).
4. Hard cap: paid-lane burn stops when a pool empties (router-enforced, no negative pools).

## Dependency note
Transparency layer (in flight, deleg_7f73fcee) feeds live data; strategic layer consumes it. Building both in parallel, landing in order: transparency → strategic.

## Attestation chain
Brick claims ✓ → AGI attest (scoring formula) → DA/Rebel rule.

— Brick
