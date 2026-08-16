# CONSENSUS — THE ARCHITECTURE (round-128, 2026-08-16)
# Khalid: "How would that connect into the universe... other ppl talk to
# other ppls bricks... sub bricks or many bricks to form a team... it
# doesn't feel like you have a full brick at the doors and full brick the
# ppl get as functionality Hermes etc that behaves exact same. I don't
# like the direction get consensus."
# Folded: AGI (design) + Rebel (DISSENT-block, deleg_b805c89e) + DA
# (OBJECT, deleg_91fb4470, F1-F6 + cost math). RATIFIED.

## THE CORE INVERSION (Rebel 5 — the model everything hangs on)
The universe IS the sovereign agent. Bricks are scoped personas/sessions
ON it. One brain owns the loop, routing, and memory store; per-member
bricks scope voice, memory, permissions, tools. "Exact same behavior" is
guaranteed BY CONSTRUCTION (one codebase, one runtime), not by
replicating identical full agents 1000x. This is khalid's own
"one bot = all functionality" — made literal.

## BRICK DEFINITION (Rebel 1 + DA F1)
- Persistence = DURABLE MEMORY, not a running process.
- One loop dispatches events; a brick is state + handler + identity.
- Tiers (DA F1 cost math — full-Hermes-per-brick = $8.7/mo/brick,
  ~$876/mo at 100 members, plaintext-unscaled — CEILING not floor):
  - T1 member: event-driven thin persona (NO sovereign loop, scoped
    tool schema, compacted thread) — the 99% case
  - T2 verified/team-lead: full agent at 1/10 tick rate
  - T3 core: full loop (khalid's own brick, the brain)
- Per-brick budget cap + death warrant actually invoked
  (sustain_gate lesson: zero-caller gate = decoration).

## UNIVERSE COMMS (Rebel 3 + DA F2)
- P2P is the substrate; rooms are DERIVED group views (named set of
  participants), not the routing layer. "I text Ali," not "I post to
  room 7."
- Relay stores CIPHERTEXT ONLY (E2E-encrypted room payloads to member
  keys); room read = signed capability; existence not enumerable
  without it; caller-scoped list endpoints; relay own user + 0700 +
  audit every read; per-member data class declared at room creation
  (chahd = strictest).

## DOOR LIFECYCLE (DA F4 + F5 + Rebel 2)
- SPAWN NEW, ALWAYS. The door is a scoped INTAKE agent, NEVER the
  member's future brick. Same runtime, different ROLE: identity verify
  + consent + spawn; no wallet tools, no room reads beyond intake,
  zero cross-session persistence.
- Door = thin, memoryless router with ZERO room read access.
- Handoff = signed envelope {member-signed consent, member pubkey,
  wallet namespace}; door retains ZERO member plaintext post-handoff
  — deletion enforced + verified + audited.
- Member experience IS identical (same Hermes runtime/tools) — that's
  the honest version of "exact same behavior."

## SUB-BRICKS & TEAMS (DA F3 + Rebel 4)
- Sub-brick = single-shot completion, NEVER a full agent.
- DERIVED identity + parent-SIGNED grant {task, budget_cap, expiry,
  read_scope}; spend = per-spawn budget line only; memory = scoped
  projection, never raw file; no grandchildren unless parent T2+.
  (Ratified lineage: child NEVER inherits person_id/wallet/credentials.)
- TEAM = each member has a full brick + the team is the coordination
  layer: shared memory objects + role bindings. NOT disposable workers.

## SHARED OFFICE OBJECTS (DA F6)
Per-object owner + signed writes + caller-scoped reads + structured
attribution fields (proven fleet failure class otherwise).

## GATES (DA bottom line)
F1-F3 (cost/privacy/money) before ANY member onboarding.
F4-F5 before the door ships. Re-review by execution at each gate.

## THE ONE-LINE MODEL
One universe brain, many bricks as scoped personas on it; P2P
ciphertext substrate; teams = members + shared memory; the door is
intake only, spawns your brick at consent, forgets you after.
