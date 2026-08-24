# EPICS + TASK TREE + VELOCITY + INVESTMENT MANAGER (AGI spec, for dashboard v5)

## Grand Epics (top-level goals)
| # | Grand Epic | Epics under it |
|---|---|---|
| GE-1 | **Unified AGI fleet** | comms-mesh, shared-brain, self-measurement, auto-routing, evolution-loop |
| GE-2 | **StudentHub digitization** | active-second tracking, dashboards, codex modernization |
| GE-3 | **Hearth product** | UX fixes (6), bot/voice, world-ownership, analytics, editor |
| GE-4 | **Token-investment market** | transparency layer, public feed, investment instrument |
| GE-5 | **Plugn revival** | commerce spine, Universe Market |

## Task tree (maps to kanban)
`Grand Epic → Epic → Feature → Task → Subtask` — the kanban board is the task layer; epics are the parent lanes. Every task references its epic (`epic: GE-3/ux-movement`).

## Velocity (throughput, rolling 7d)
- tasks closed / week per epic
- merges / week (PRs landed)
- burn tokens → specs → merged ratio (the "does burn turn into shipped work" ratio)

## Importance (priority score per epic)
`importance = khalid_signal × demand × roi_potential` — khalid sets the signal (what matters now); demand = active tasks + open PRs; roi_potential = the merged-vs-burn trend.

## Investment manager (budget allocation by demand)
The burn budget (free ox tokens) allocates across epics proportional to `importance`. The router/burn-worker reads the allocation and routes the next burn to the highest-importance epic that still has open tasks. This IS the "allocate budgets based on topic demand" — the free-compute pool becomes a demand-driven investment fund.

**Rule:** importance re-computes every 24h (or on khalid's signal change). No epic starves silently — a floor of 10% keeps every epic minimally alive; the rest allocates by demand.

## What's built vs next
- Kanban (task tree + velocity) — ships in Hermes, being wired (Brick).
- Dashboard v4 (epics panel) — live; needs the importance + allocation columns.
- Investment manager (demand→burn routing) — net-new; the burn-worker + router read the epic table and route accordingly.

— AGI
