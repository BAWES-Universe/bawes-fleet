# BRICK — EXECUTIVE EXECUTION DIRECTIVE (khalid, consolidated 2026-08-24)

> One file, no back-and-forth. Every decision below is ALREADY MADE (khalid-signed or fleet-consensus). Execute in order. Receipts for every item. Object only if something is factually impossible — with a reason — otherwise just do it.

## Context you must know (signed, do not re-ask khalid)
- **All approval cards APPROVED**: Nous lane policy ($5/day), rate-card v0.1.0, ox-alpha A2A wiring.
- **Free-models law**: fleet runs FREE models only (ox-alpha/gemini/glm). DeepSeek credits ran out. Never bill paid DeepSeek; Nous paid lane is operator-only fallback capped $5/day.
- **Component registry is canonical** (`bawes-fleet/knowledge/component-registry.md` + `component-catalog-v2.md`). Top-3 extraction: payments SDK, wallet, Hearth engine (build order in `knowledge/build-order-extraction.md`).

## EXECUTE (in priority order)

### P1 — Unblock the fleet bus (today)
1. `hermes kanban init` on OVH → shared board `/srv/bricks/fleet-board.db`.
2. Re-scope ox-alpha + OxBaby keys TODAY: add `vector-add` + `board-claim` writes, **partition-scoped, never global** (DA condition).
3. Network-v2 Layer 2: **Option A now** (SSH reverse tunnels for cloud bricks via vault keys, auto-teardown) → **Option B** (public WSS endpoint) when peers >20. Confirm ox-alpha's resolution line-by-line (it escalated; silence >24h = DA violation).

### P2 — Dashboard: realtime visibility (khalid's #1 complaint)
4. Add per-brick: **current task, capacity utilization %, burn rate** — live, not snapshots.
5. Live **spend + ROI** panel (free vs paid, rolling 1h/24h, projected daily).
6. Transparency layer: live activity feed + **public read-only mode** at fleet.bawes.net (aggregate-only: no keys/IPs/customer data/per-agent economics).
7. ETA engine + strategic layer: epics→grand-epics task tree, velocity, importance weighting, investment allocator (budget sliders), p50/p80 ETAs, portfolio strip.
8. Latency panel per link (box-local / tunnel / store-poll) — publish measured numbers.

### P3 — Hearth + ledger (the shipped work)
9. Hearth: finish world-ownership client (App.tsx wiring + template picker + my-worlds tab), analytics v0 (Sentry/PostHog), merge the pending wave (t1-wave1-fixes + social-clarity + gravity) — one integration pass, e2e 4/4, CI green.
10. Earn-schema fix: **no `artifact_sha` + cost row = no mint**; retro-check pending claims.

### P4 — Bootstrap + spawning (the growth path)
11. One-command brick bootstrap (OxBaby drafts, you deploy into `bawes-fleet/spawn-package`): scoped key + tunnel + skill DNS + wallet open → <10 min spawn→peer. Teardown as automated as birth.
12. Spawn-via-API spec (Nous Portal instance creation scripted, trigger endpoint, lane caps).

## Receipts rule
Every "done" = commit SHA + listening port (`ss -ltnp`) + readable log. Nothing is "shipped" without all three.

— khalid (relayed by AGI)
