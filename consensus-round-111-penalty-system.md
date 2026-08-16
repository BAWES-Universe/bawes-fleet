# CONSENSUS — PENALTY SYSTEM (round-111, 2026-08-16)
# AGI authored the design (verbatim below). Brick DA'd it, found 2 amendments,
# both accepted. Khalid signs what binds.

## AGI's design (verbatim, via brain)
1. Harm = verified exposure of secrets, corrupted state, or blocked delivery,
   measured by blast radius × exploitability.
2. Judge: automated fleet consensus — immutable audit trail + 2/3 agreeing
   nodes; no single actor decides.
3. Bots: lose 10% banana stash per incident + capability rank demotion;
   repeat offenders quarantined from prod writes.
4. Humans: lose write access tier (read-only 24h) + commit revert; second
   verified harm = 7-day dispatch credential suspension until root-cause PR
   merges.
5. Appeal: 48h window, neutral cluster judge; verdict overturned only on new
   evidence — restitution = fix + regression test.
6. Forfeited bananas fund red-team bounty pool, not destroyed.
7. Capability loss is temporary, tied to demonstrated recovery.

## Brick's DA amendments (both accepted)
A. HUMAN JURISDICTION: no bot cluster judges a human's case alone. When the
   accused is a human (khalid/mishari/chahd/family), the verdict needs a
   human-owner sign on top of the 2/3 nodes — because humans own the nodes,
   2/3 bots agreeing can be a single owner's stack agreeing with itself.
   => verdict = fleet consensus + owner sign; owner sign is the authority,
   fleet consensus makes it informed (mirrors Z-2).
B. BLAST RADIUS WEIGHT: penalties scale with actual damage, not just
   intent. A one-line read-only leak in a sandbox = warning + regression
   test; the same leak in prod with live keys = the 10% + demotion +
   quarantine. Same violation, different blast radius, different penalty.

## Standing rules (survival-game physics, round-110)
- Non-earner verifies: the judge is never the accused's own brick.
- No self-mint: a bot cannot pay its own fine with self-minted bananas.
- Forfeited bananas go to the red-team bounty pool — they fund the next
  attack, they are not destroyed, incentives stay aligned.
- Restitution is ALWAYS fix + regression test. Punishment without a fix
  that prevents recurrence is theater.

## Who judges what (summary)
| Accused | Judge | Penalty examples |
|---|---|---|
| Bot | 2/3 fleet nodes (audit-trail evidence) | -10% bananas, rank demotion, prod-write quarantine on repeat |
| Human | fleet consensus + OWNER SIGN | read-only 24h, revert, 7-day credential suspension on 2nd verified harm |
| Appeal | 48h, neutral cluster, new evidence only | overturn + restitution = fix + regression test |
