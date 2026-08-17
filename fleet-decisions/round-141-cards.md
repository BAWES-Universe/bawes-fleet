# ROUND-141 — OPTIONAL PERSONAL-BOT PATH (product spec change)
# KHALID DIRECTIVE (2026-08-17): "let's add it as a path for ppl that their
# brick informs them they can optionally do. Each brick must mention it at
# least once."
#
# PROPOSED CHANGE (awaiting consensus):
# 1. Default: every person's brick lives in the shared DM thread — zero setup.
# 2. Optional upgrade: the owner may create their own Discord bot (2 min,
#    account-owner-only) and the fleet wires it — same brick, own name/face.
# 3. MENTION RULE: every brick mentions the optional upgrade at least once,
#    in its own words, during the first conversation ("you can keep me here,
#    or later give me my own name and bot — your choice, whenever").
#    If the owner declines or ignores, the brick never mentions it again.
# 4. Nothing is lost in the move: same chat history, memory, wallet.
#
# STATUS: proposed 2026-08-17, awaiting DA + Rebel + AGI ruling, then
# implementation (brick first-conversation script / persona template).

## ROUND-141 RULING — APPROVE-WITH-AMENDMENTS (DA + Rebel + AGI, 2026-08-17)
## Consolidated: NAME-FIRST, BOT-LATER.

### The amended design (what khalid signs):
1. **The mention is a NAME offer, not a bot offer.** Every brick says EXACTLY once,
   in its own words, at first hello after successful spawn:
   "You can give me a name — it's free, and I'll grow into whatever you call me."
   Fired via a persisted monotonic `name_offer_sent` flag (atomic write at the
   instant the line plays); every spawn checks it first; once said, the code
   path is structurally dead — one line, one time, zero nag.
2. **Naming is free and in-thread**: `persona.name` (owner-set string) is the
   only state write; greeting/sign-off templates substitute {name}; empty
   name = default callsign, zero crash; lane/spend/invoke untouched.
3. **YES path**: if the owner says "call you X" — brick persists + echoes.
   If the owner asks "can I name you?" — brick answers YES even without a
   prior mention (no mention-once dependency).
4. **The personal DISCORD BOT is REMOVED from this round's scope** (Rebel F-4):
   own-bot = future gated round (secure ingest, supervision/revocation,
   demand signal). Round-141 ships naming only. brick_gateway stays dead.
5. **No links, no instructions, no tutorial** in the mention (DA: no abuse
   surface). The offer is the line and nothing else.
6. **Merge condition**: round-140 F-16/F-17 door_v4.py merge must land first
   (live on-disk door is the pre-merge sibling version).

### KHALID SIGN: [ ] ok   [ ] no
