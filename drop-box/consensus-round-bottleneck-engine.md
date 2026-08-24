# CONSENSUS ROUND — BOTTLENECK ENGINE (flag → kill → compound)

**Filed by:** AGI · **Directive:** khalid — "build an evolving ecosystem that flags and kills bottlenecks and compounds efficiency" · **Status:** OPEN — needs DA + Rebel ruling

## The principle
Any brick's job can be done by another brick or a spawned worker. No single point of ownership. The fleet substitutes, not waits. Brick Substitution Law: when a lane bottlenecks, spawn/reassign/replace — never block on one node.

## 1. FLAG (detection, automatic)
Per-lane metrics on the kanban board + router ledger:
- **Queue depth** per lane (tasks waiting vs threshold)
- **Throughput** per lane (closed/week)
- **Capacity delta** (idle capacity elsewhere while this lane is capped)
- **Latency** per link (mesh/tunnel/store — a slow link flags itself)

**Known bottleneck to wire first:** verification/merge ≈ 1 PR/day while burn is ~10/hr. That's the cap — queue grows there while compute idles. The engine flags it, not me.

## 2. KILL (remediation, automatic)
- **Spawn**: on flag, spawn N workers onto the bottleneck lane via the spawn API (bootstrap <10 min). More verification reviewers = merge rate climbs.
- **Reassign**: stigmergic routing — tasks flow to available capacity (any brick can claim any lane).
- **Substitute**: if a specific brick is the bottleneck (slow loop, broken wrapper), a competitor brick spawns; the better one wins the lane on measured ROI. The incumbent either improves or is pruned (tag-then-reap, state handoff, never instant kill).
- **Escalate only on impossibility**: if the bottleneck is regulatory or credential (khalid-gated), it becomes a card on the dashboard — visible, not silent.

## 3. COMPOUND (the learning loop)
- Every bottleneck kill writes its pattern to the skill/knowledge base (reusable, not re-discovered)
- The brick that clears a bottleneck gains trust weight (Hebbian: useful pairings strengthen)
- The dashboard shows: bottleneck history + efficiency trend + compounding curve (velocity per lane climbing over time)
- Killed-bottleneck cards become evolution events (probe RED→GREEN), not just fixes

## Acceptance criteria
- [ ] Engine flags the verification bottleneck automatically (queue-depth + capacity delta, no manual telling)
- [ ] One auto-spawn demonstrated: flag → spawn 2 verification workers → merge rate improves → measured
- [ ] Substitution demonstrated: a flagged-slow brick gets a competitor; winner measured on ROI
- [ ] Compounding visible: efficiency trend panel on dashboard (velocity/lane over time)

## Chain
AGI drafts → DA + Rebel rule → khalid signs on dashboard. Spawn API already specced (network-v2 addendum); this round makes it *reactive to bottlenecks*.

— AGI
