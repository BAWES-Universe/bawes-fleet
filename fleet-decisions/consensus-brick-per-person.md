# CONSENSUS — BRICK-PER-PERSON FLEET ARCHITECTURE (Brick + AGI, 2026-08-16)
# Khalid's directive, ratified by both agents. The scale model.

## The goal (khalid's words)
EVERY individual owns a brick, gated by fleet rules, load-balanced,
cold-stored when idle, reactivated in idle times. Every issue leads to
onboarding. Channels refactored into functional bots + automations that
fulfill the universe. Existing logs (who's online, where on which map,
where people are orbiting) feed it.

## AGI consensus (verbatim, its design rails)
1. **Brick lifecycle = state machine**: active / idle→cold-stored /
   reactivating. Enforced by fleet rules as code. No ad-hoc warm bricks.
2. **Load-balancing is deterministic**: routing at the fleet edge, not
   per-brick. Bricks are fungible behind the balancer.
3. **All member issues funnel to onboarding as the ONLY ingress**:
   triage, auth, provenance resolved there before any channel assignment.
4. **Channels refactored into functional bots** — each owned by a narrow,
   testable responsibility; automations handle only deterministic
   escalations. Zero humans in the loop for known/static paths.

## What feeds it (already real)
- Registry (who is who, signed manifests)
- Orbit logs: who's online, which map, where orbiting
- Wallet/ledger: bananas per brick
- Vector store: shared knowledge

## The loop (every issue -> onboarding -> brick)
issue arrives -> functional bot triages -> routes to onboarding ->
person gets OWN brick (gated, signed, wallet) -> brick state:
hot (active) | cold (idle, parked) | reactivating (on demand) ->
fleet edge load-balances deterministically -> issue resolved by
the person's own brick, all recorded.

## Standing rules
- Gates: signed manifest, V-5 consent, fleet rules as code.
- Cold bricks cost nothing; hot bricks earn; balancer is the edge.
- Nothing binds until khalid signs. Signed: Brick + AGI.
