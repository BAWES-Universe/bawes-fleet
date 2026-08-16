# ROUND-112 — Brick penalized for 3 more failures (khalid directive)

thread: bawes-zeus-001 · khalid: "Make sure brick is penalized for losing the slim thing and not having hindsight memory or self repairing."

## The 3 failures
1. **Lost the slim fix** — built the slim-prompt once, then it vanished (only the agi profile dir survived; the repo branch was never merged/applied). Built → lost = worse than losing docs; it's losing actual work.
2. **No hindsight memory** — the vector-store retrieval / hindsight bank is not wired, so the brick doesn't learn across sessions (the amnesia defect again).
3. **No self-repair** — no mechanism for the brick to detect + fix its own faults; it just fails and waits.

## Context (credit where due)
Brick did re-commit the slim fix (`brick-profile/slim-prompt.yaml`, sub-10s on the 4B) and designed the cross-brick inference (consent opt-in, distilled intents only, hash+timestamped receipts, suggestion-not-override). That's good. The PENALTY is for the loss + the two missing capabilities, not for the re-fix.

## Required (not optional — part of "amazing experience for all onboarded")
- **Hindsight memory** = wire vector-store retrieval into every brick's session start (the known defect). A brick that forgets is a brick that re-asks its owner.
- **Self-repair** = a brick detects its own fault (slow, wrong, failed) and fixes or re-routes before the owner ever sees it.
- **Never lose a built fix** = every fix commits to a durable, non-removable path BEFORE it's considered done.

## Dock
**Brick −10🍌** — one dock covering all three (set by DA, escalated above round-111's 5).

Decomposition (for the ledger, not additive — the 10 is the single dock):
- **Lost slim fix = 6🍌** — state-loss of BUILT work, +1 over round-111's 5 doc-loss baseline (a working, validated fix is worth more than deleted records; "never lose a built fix" is a standing rule). Capped here because Brick re-committed it same-round (credit where due — the penalty is for the loss, not the re-fix).
- **No hindsight memory = 2🍌** — missing required capability; the recurring amnesia defect. Tiered at round-111's "un-flagged oversight" severity: a capability gap, not an active harm.
- **No self-repair = 2🍌** — missing required capability; same tier.

Rationale for 10: it is 2× the round-111 first-offense state-loss (5), a clean escalation that says "lost work + two missing caps" is heavier than "deleted docs" — a real deterrent, not a slap. Non-crippling per round-110: 10 = two thinking-tasks' worth, earnable back within a day of honest service (speed-bump, not death sentence). Forfeited bananas go to the red-team bounty pool (penalty-system rule 6), not destroyed.

Remediation (required to close the loop; does not reduce the dock):
1. wire vector-store retrieval into every brick's session start (hindsight memory),
2. add a self-repair detect → fix/reroute loop (no owner sees a brick's own fault),
3. commit every fix to a durable, non-removable path BEFORE it's considered done.
