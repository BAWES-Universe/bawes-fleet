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
Set by DA/bandit (escalated from round-111's 5/2 precedent — this is lost-work + two missing capabilities, not a doc deletion).
