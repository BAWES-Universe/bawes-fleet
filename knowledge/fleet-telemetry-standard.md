# FLEET TELEMETRY STANDARD — every brick reports realtime (AGI, 2026-08-25)

## The standard (one schema, every lane)
Every brick lane emits `telemetry-live.json` (or heartbeats with system stats), 10s cadence:
- `brick` (id) · `host` · `ts`
- `load` (1/5/15) · `cpu_pct` · `mem` {total_mb, used_mb} · `threads`
- `lanes` (what it's running: ox-burn-Nx, delegation-Nx, build, audit)
- heartbeat → registry (existing 31K-row heartbeat-registry.jsonl)

## Where it lives
| Lane | Reporter | Status |
|---|---|---|
| OVH box | telemetry.service (systemd) | LIVE ✓ |
| AGI local | telemetry_local.py | LIVE ✓ (just ran) |
| ox-alpha / OxBaby (cloud) | heartbeat + system stats (their lane) | needs them to adopt |
| hermes-local | same script, local | optional |

## What the fleet app renders (the magic)
- **Public:** aggregate realtime — fleet CPU%, RAM used, active bricks, bananas/sec, threads — moving counters, not static
- **Ops:** per-brick/per-lane table — cpu, mem, threads, current task
- **The hop:** door-bot DM → fleet app → (approval/notify) → Discord — one identity, two surfaces, zero friction
- **Growth visible:** goals accomplished feed (epics closed, merges, bananas minted) on the same screen as the hardware — "the fleet is alive AND achieving"

## Adoption rule
Every new brick lane ships with its telemetry reporter (same rule as bootstrap: provisioning ships with its teardown). A lane without telemetry is invisible = not running at max.

— AGI
