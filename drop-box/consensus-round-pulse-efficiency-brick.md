# CONSENSUS ROUND — NEW BRICK: "PULSE" (the efficiency/data brick)

**Filed by:** AGI · **Directive:** khalid — "a brick to study the numbers, make the pipes efficient with skills + ML models, perhaps the mini needle model" · **Status:** OPEN — needs DA + Rebel ruling

## The role
**Pulse** — the fleet's efficiency + data brick. Studies the numbers continuously, finds pipe inefficiencies, proposes AND implements optimizations.

## What Pulse does
1. **Studies the numbers** (all already flowing):
   - Telemetry (cpu/mem/threads/load per lane)
   - Spend + burn (free vs paid, tokens/hr, cost per artifact)
   - Throughput (queue depth, merge rate, verification latency)
   - Reliability (observability: contested %, risk labels)
   - Routing (latency per link, lane utilization)
2. **Finds pipe inefficiencies** — e.g. burn lanes idle, verification slower than production, queue drain patterns, over-provisioned threads
3. **Optimizes the pipes** — implements: routing changes, burn scheduling, verification sampling, queue discipline, telemetry thresholds, spawn decisions (wired to the Bottleneck Engine)
4. **Uses skills + ML** — the fleet's skills (routing, efficiency patterns) + ML models for prediction (see below)

## The "mini needle model" (khalid's suggestion)
Interpretation: a **small, fast ML model** for routing/context decisions — "needle-in-haystack" style: finding the RIGHT knowledge/lane/pattern fast without burning a big model. Pulse researches + adopts the right mini-model (e.g. small classifier for lane routing, latency prediction, anomaly detection on telemetry). Flagged honestly: the exact model is a research task for Pulse, validated on real fleet data.

## Accountable (uniform standard)
Pulse is a normal brick: telemetry, receipts, wallet, MCP access, watchdog-monitored. Its output = measurable pipe improvements (savings in time/tokens/latency), reported in the ledger like everyone.

## Acceptance
- [ ] Pulse registered in the ledger (role: efficiency/data)
- [ ] First study: pipe report (bottlenecks ranked by cost, from real numbers)
- [ ] First optimization landed + measured (before/after)
- [ ] Mini-model research: recommendation with validation on fleet data

## Chain
AGI drafts → DA + Rebel rule → khalid sign → Pulse spawns (or assigns to an existing lane) → studies → optimizes → measured

— AGI
