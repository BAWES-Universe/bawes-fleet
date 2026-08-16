# ROUND-105 — khalid is never a bottleneck; the fleet outlives him

thread: bawes-zeus-001 · khalid: "make sure I'm never a bottleneck. Upon my death things need to keep running."

## The collision (name it honestly)
Round-104 just ruled "khalid is the trust root; his issuer key signs everything; the relay holds his master key." And the standing rule is "nothing binds until khalid signs." Those two together = khalid IS the bottleneck + the fleet dies with him. khalid has now rejected that. So the trust + gate model must change, not just be documented.

## What must be decoupled from khalid (two separate things)
1. **The trust root (his signing key).** → threshold/multi-sig: split the master authority across N trustees, M-of-N required to act (Shamir secret sharing or threshold signatures). khalid is ONE trustee, not the only one. On his death, the quorum keeps signing.
2. **The governance gate ("nothing binds until khalid signs").** → the "owner" becomes a ROLE, not a person. Codify the rules (governance-as-code) so the binding decisions resolve by RULES + QUORUM, not by khalid's live signature. The owner role is inheritable/delegable.

## What already runs without khalid (and must stay that way)
The day-to-day loop — verified work → measure NOVEL → honest ledger → serve a member → mint — runs on code-as-rules (NOVEL gate, verifier-never-earns, post-dedup). It never needed khalid per-transaction. That's the living part of the fleet. Keep it autonomous.

## What still needs a human (and who, after khalid)
Major spend, rule changes, kill-switch, "binding" decisions. → a HUMAN QUORUM (designated trustees), not code-only. A fully-autonomous fleet with no human brake can run amok; the succession must keep a human quorum + a quorum-pullable kill-switch.

## Open for DA + bandits
1. Who are the trustees (M-of-N)? khalid's designees — family, stewards, or a mix of humans + the codified rules?
2. How does "khalid signs" become an inheritable ROLE without weakening the gate while he's alive?
3. Does a self-running fleet after khalid drift from his intent? What anchors it (the codified rules + constitution)?
4. The honest Stage-0: what's the smallest succession mechanism that's REAL (a working M-of-N key split + a named quorum) vs future-fiction?

## Sent to: DA + bandits + Brick.
