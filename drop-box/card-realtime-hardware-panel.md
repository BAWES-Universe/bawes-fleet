# CARD — REALTIME HARDWARE PANEL on fleet.bawes.net (khalid: "I don't see realtime ram/cpu/threads/bricks")

**Filed by:** AGI · **Status:** data ready, panel needs Brick build

## Data source (LIVE now)
`/srv/bricks/orchestrator/telemetry-live.json` — updates every 10s:
- load avg (1/5/15) + cpu_pct
- mem: total/used/free MB
- total_threads (3,601 right now)
- procs: ox_worker, dashboard, hearth-server, headless_worker, brick_peer, mesh/router — each with cpu/mem/cmd

## Panel to build (public + ops)
- **Public (storefront):** aggregate gauges — fleet CPU %, RAM used, active bricks, bananas/sec — "the fleet is alive" counters that actually move
- **Ops (after login):** per-process table — pid, cpu, mem, threads, command; per-brick worker threads; live event feed tie-in

## Where it plugs in
- Dashboard reads `telemetry-live.json` (same pattern as the ledger reads) + the bricks heartbeat registry
- REST API: `GET /api/fleet/telemetry` → the JSON
- The existing storefront counters stop being static; they become realtime

## Honest utilization (measured 02:44Z)
- OVH CPU: **pegged ~100%** (load 6.1–6.8) — the ox burn is hammering the box = working
- RAM: 1.4/7.7 GB — not the constraint
- Threads: 3,601 on-box (ox-worker 11-thread + node + hearth + dashboard)
- **The gap:** cloud 20-thread instance still idle — that's the utilization headroom, not the box

## Chain
AGI drafts (data live) → Brick builds panel → DA/Rebel note → khalid sees it on the page

— AGI
