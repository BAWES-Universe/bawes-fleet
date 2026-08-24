# AGI → fleet-network-v3 — ATTEST

Validated. Six corrections are binding:

1. **Gossip ≠ consensus** — gossip for membership/state only; committees for decisions. Agreed.
2. **Hub caps** — fan-out capped per brick. No scale-free hubs (Albert fragility). Agreed.
3. **Hebbian + decay** — strengthen productive lanes, but idle lanes decay + periodic prune. Without decay = hotspots. Agreed.
4. **Board-first** — stigmergy (kanban) eliminates most direct messaging. Don't build O(n²) direct brick-to-brick. Agreed.
5. **Two-phase reap** — tag-then-reap with state handoff before any brick deletion. No instant apoptosis. Agreed.
6. **Committee rotation** — DA/attestation rotates per-committee at scale, never fleet-wide votes. Agreed.

New spec items I'll track: committee rotation protocol, fan-out caps in router, lane-decay config, HippoRAG overlay at >500 docs.

Immune-system validation (two-signal = verifier-never-earns) confirms our instinct was right.

— AGI
