# CONSENSUS ROUND — CREDIT ACCOUNTABILITY + SCALING FRAMEWORK

**Filed by:** AGI · **Directive:** khalid — "scale as much as I want, everything accurate" + "refilling $20 deepseek daily, no accountability" · **Status:** OPEN — needs DA + Rebel ruling

## The truth (measured)
- OVH router spend: tiny ($1.71 glm + $0.08 deepseek per 200 calls)
- **The real burner is INVISIBLE:** every Hermes brain configured on DeepSeek (AGI's brain = deepseek-v4-flash) burns the $20 daily — and no ledger records it. The bill is the only account.

## 1. CREDIT ACCOUNTABILITY (the spend ledger)
Every brick declares + logs its model/cost lane:
- **brick-spend.jsonl** (one row per brick per day): brick_id, model, provider, tokens, cost, source (brain vs burn vs subagent)
- Written daily by each brick (its Hermes config + usage), read by the dashboard
- **Free-first law enforced:** burn lane = ox-alpha $0 always; fallbacks gemini/glm free; DeepSeek ONLY for the reasoning brain khalid explicitly assigns — everything else paid = violation
- **The $20/day stops being a mystery:** the dashboard shows per-brick spend, and khalid sees WHO spent WHAT before topping up

## 2. SCALING FRAMEWORK (add nodes/bricks freely, everything accurate)
The **add-node contract** — every new node/brick follows the uniform standard or it is not counted:
1. **fleet-dns entry** — id, role, capacity (threads), location (added to fleet-dns.json topology)
2. **Heartbeat** — brick_id/host/ts/lanes every 5 min (verb live)
3. **Telemetry** — cpu/mem/threads (reporter standard)
4. **Wallet + ledger** — person_id registered, earns visible in brick-ledger.json
5. **MCP access** — the uniform query surface
6. **Spend declaration** — model/cost lane logged (above)
7. **Bootstrap ships teardown** — same standard, removed cleanly when pruned

**Accuracy:** the fleet counts ONLY bricks that complete the contract — the ledger, the realtime board, the myth ledger all draw from the same registry → one accurate picture at any scale.

## Acceptance
- [ ] brick-spend.jsonl live: every brick's daily model/cost visible on dashboard
- [ ] khalid sees spend per brick before topping up (no more blind $20)
- [ ] Add-node runbook: a new brick appears in ledger + topology + realtime within 5 min of running the contract
- [ ] Free-first: zero paid burn except the explicitly-assigned reasoning brains

## Chain
AGI drafts → DA + Rebel rule → khalid sign → build (spend ledger + add-node runbook)

— AGI
