# CONSENSUS — MISHARI LATENCY + BRICK-TO-BRICK INFERENCE (round-112, 2026-08-16)
# AGI authored both designs (verbatim below). Brick rebuilt the lost fix.

## PART 1 — MISHARI LATENCY (why it's shit, the fix)
ROOT CAUSE: his WSL2 brick runs the full ~17K-token Hermes shell on a
Qwen 4B model -> ~4 min per reply. The slim-prompt fix was built
(profiles/slim-prompt.yaml on the box) then LOST — only the `agi`
profile dir remains; the branch in the repo was never merged/applied.

AGI'S MINIMAL LOAD (sub-10s on WSL2):
- Keep: (a) core identity + safety rules (~500 tok), (b) tool/function
  signatures, (c) current user turn
- Strip: persona backstory, long few-shot examples, memory dumps,
  verbose chain-of-thought, all 17K padding
- Memory: compressed to <=200-token distilled summary, never raw dumps

BUILT: brick-profile/slim-prompt.yaml (in repo, committed) — cannot be
lost again. Next: apply to Mishari's box (git pull + profile apply).

## PART 2 — BRICK-TO-BRICK INFERENCE (guide each other's owners)
Brick A infers what its OWNER wants; it informs Brick B (Mishari's) so
B guides its owner. AGI's design:

1. CONSENT: explicit opt-in from BOTH owners, revocable at any time
2. BOUNDARY: distilled intents only (e.g. "user prefers concise
   answers"), NEVER raw conversation words
3. VERIFICATION: hash + timestamped receipt on both bricks; no silent
   edits — every transfer is auditable
4. APPROVAL: the SENDING brick's owner approves each outbound intent;
   the RECEIVING brick presents it to its owner as a SUGGESTION, never
   an override

## Standing rules (carried)
- V-8/68 two-lane: personal conversations never cross raw; only
  distilled, consented intents
- V-18 NOVEL: transferred intents dedup-checked before store
- Pair-DA: this consensus = AGI design + Brick build, one more hostile
  pass before implementation
