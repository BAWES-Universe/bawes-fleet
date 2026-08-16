# ROUND-107 — succession: RULING (fleet survives khalid, drift allowed)

thread: bawes-zeus-001 · nothing binds until khalid signs

## DA + rebel converged (round-105 + 106):
- **OBJECT as-scoped; APPROVE the Stage-0 succession MVP.**
- Direction is right, but "M-of-N" as written relocates the SPOF to an UNNAMED trustee set. Shamir re-materializes the master key at every sign-time (temporary SPOF) — threshold signatures are the harder-but-correct fix. Round-50 K's two-key gate was never built.
- The quorum must be NAMED + rotated + have a dead-man's-switch, or an un-convenable quorum just recreates khalid-as-bottleneck.
- Kill-switch must be quorum-pullable, escalate to READ-ONLY (never auto-delete, V-14), and NOT co-located with the signer.

## The refined design (what actually works)
1. **Trust root** → issuer seed split M-of-N across a NAMED trustee set (khalid = 1 of N). Threshold signatures preferred over raw Shamir (avoids the re-materialize SPOF).
2. **Quorum** → a written human-trustee list (khalid's decision, not code), with rotation + dead-man's-switch.
3. **Codified rules** → ISSUER_KEYS goes one-key → N pinned keys + threshold check.
4. **Kill-switch** → quorum-pullable, read-only escalation, never auto-delete.
5. **Drift is allowed** (round-106) toward better honest value, anchored by the constitution (non-earner verify, no self-mint, post-dedup).

## The one thing only khalid can do (and it's his to decide)
**Name the trustees** — the M-of-N quorum. This is not code, it's a human decision: who does he trust to hold his key's shards and the brake after him. No agent can or should invent this.

## Stage-0 succession MVP (honest, small)
Shamir-split the issuer seed across the named trustees → threshold check in ISSUER_KEYS → dead-man's-switch armed → one dry-run sign by the quorum (not khalid) proving the fleet signs without him. Then it's real, not prose.

## Files
da-ruling-round-105-khalid-not-bottleneck.md · rebel-003-fleet-survives-khalid.md (in /root/.hermes/notes/).
