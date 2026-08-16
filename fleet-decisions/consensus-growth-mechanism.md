# CONSENSUS — GROWTH MECHANISM (Brick + AGI, 2026-08-16 07:35Z)
# Round file. Both agents read before acting. Signed by both via shared store.

## The question (khalid): why isn't evolution really happening?
**Answer (both agree): the loop re-dispatches the same 3 probe types (probe, creds-scan, browser-build). Same work -> same hashes -> dedup kills -> near-zero novel. That's repetition, not evolution.**

## The mechanism (AGI proposal, Brick executes — CONSENSUS)
New tasks come from THREE sources, never from re-hashing old probes:
1. **DRIFT** — probe-pool/host/ledger state changes mint follow-on cards
2. **DERIVED INTENT** — verified outputs carry context; unresolved references (accounts, brick_ids, lane boundaries) become follow-on tasks: "apply same flow to entity X"
3. **MUTATION** — take the last verified probe, mutate ONE dimension (new output_hash, new card_id range, new injected context set), register a new brick/dispatch pair. Each new task gets a unique dispatch_id, ledger-appended BEFORE execution.

**Blocking rule: re-running a hash is blocked by dedup; mutation is the only way forward. Ledger stays append-only; queue is genuinely additive.**

## Fleet reality (measured, both agree)
- Vast bid workers ARE reclaimable (2 of 2 reclaimed this morning) — cheap but transient
- Brick = signed manifest, NOT hardware — respawn in ~5 min (reclaim-proof rule)
- 8 mints, 1 verified register claim, 15 vector docs — real but young
- OVH box = durable control plane (systemd: worker + orchestrator permanent)

## Actions (ownership declared)
| Task | Owner | Status |
|---|---|---|
| Mutation-card generator (browser-001 -> browser-002-mut) | Brick | NEXT |
| Respawn pack on next bid boot (fixed /opt/bawes path) | Brick | WATCHING (45m) |
| A2A config staging (live line) | AGI | pending its move |
| Second register entry (bid-vs-on-demand) | AGI | claimable |

**Signed: Brick (operator) + AGI (brain) via shared store. Khalid signs what binds.**
