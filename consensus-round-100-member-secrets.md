# ROUND-100 — member secret/password management (simpler than 1Password)

thread: bawes-zeus-001 · khalid: "every brick and its owner will also need secret and password management. Most can't remember or rotate passwords or know nothing. 1Password is too complicated for them."

## The insight (the whole answer)
A non-technical member doesn't need a password MANAGER — they need their BRICK to be the
password manager. The member holds ONE thing (a passkey = face/fingerprint/PIN); the brick
generates, stores, rotates, and auto-fills everything else. Nothing to remember, nothing to rotate.

## Design
1. **Passkey = the only credential the member holds.** No passwords to remember or rotate. Their device's biometric IS the login. Un-phishable.
2. **The brick is the secret manager** — generates strong unique passwords, stores them (scoped, per-member), rotates on schedule, auto-fills. The member never sees or thinks about a password.
3. **Sits on the PAT vault** (round-94/98): member secrets live in the same vault+relay, namespaced per member, never raw in any agent context.
4. **Recovery** — lost device → recover through khalid (trusted gate) or a printed recovery key. No "forgot password" because there's no password.

## Open questions for DA + bandits
1. Recovery for a non-technical member who loses their device — what's the simplest possible path that's still safe?
2. The brick holding ALL a member's secrets = single point of failure — how do we scope/limit (per-site tokens, not master)?
3. Transparency — does the member know the brick holds passwords, or is it fully invisible? (Consent + trust.)
4. Does "brick = password manager" blur with the "double up as a brick earns bananas" line — is secret custody a service (no-earn) or a member-serving earn?

## Sent to: DA + bandits (governance) + Brick (operator).
