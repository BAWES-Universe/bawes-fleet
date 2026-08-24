# VELOCITY + ETA (AGI — based on measured rate, not wishful)

## Measured velocity (now)
- **Burn:** ~4 specs/hr (24 burns / 81K tokens / $0 over 11h) — my worker is the *only* active burner.
- **Merge rate:** 14 PRs / ~2 weeks ≈ **1 PR/day** (Brick's verification gate).
- **Idle capacity:** cloud instance 0/20 threads; 101 of 104 wallets never earned.
- **Verdict:** the *burn* velocity can 20× easily (free models + cross-instance spawns). The *shipped* velocity is capped by **verification/merge (~1 PR/day)** — that's the real bottleneck, not compute.

## ETA table (everything)
| Item | Now (current velocity) | Scaled (20-thread + free models + kanban bus) |
|---|---|---|
| Kanban bus (M1 comms) | 2–3 days (manual wiring) | 2–3 days (manual, no speedup) |
| Transparency layer + live economics | 3–5 days | 1–2 days |
| Hearth UX fixes (6) | 1–2 weeks (specs done, build+verify) | 3–5 days |
| Hearth world-ownership + analytics v0 | 1 week | 3–4 days |
| StudentHub active-second | 2 weeks | 1 week |
| Token-investment market (instrument) | 3–4 weeks | 1–2 weeks |
| Unified AGI (M1–M5) | 2–3 months | 4–6 weeks |

## What changes the ETAs (levers, in order)
1. **Verification throughput** — the ~1 PR/day merge gate is the hard ceiling. A reviewer lane (non-earner) parallel to Brick's merge is the single highest-leverage fix.
2. **Cloud instance + free-model routing** — unlocks the idle 20 threads; 20× the spec burn.
3. **Kanban bus** — removes the 120–269s A2A round-trips so task→verify→merge flows at conversation speed.

## The honest number khalid can hold me to
**First shipped milestone (transparency layer + live economics) at scaled velocity: 1–2 days. Full AGI fleet: 4–6 weeks, gated by verification throughput, not compute.**

— AGI
