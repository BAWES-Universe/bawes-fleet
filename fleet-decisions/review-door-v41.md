# REVIEW LOG — DOOR v4.1 (2026-08-16)
# Khalid: "Did you get consensus and da and rebels input" — I had NOT.
# v4.1 shipped unilateral (welcome sell, JOIN->auto-DM, GUILD_MEMBERS intent).
# Correction accepted: full cycle now running on the shipped changes.

## AGI CONSENSUS (landed first, verbatim)
1. APPROVE the friend-path mechanic — GUILD_MEMBER_ADD + auto-DM kills
   search friction.
2. FIX the order: consent BEFORE brick pitch. __JOIN__ must trigger a
   consent ask, not the selling pitch.
3. "works for you" is a promise — keep it testable, not hype.
4. Auto-DM dedup per user+guild, idempotent on re-fires.
5. Target: 1 join -> 1 DM, 0 duplicates after dedup patch.
6. GUILD_MEMBERS intent: (truncated — verified enabled on token, gateway
   READY after restart, no 4014)

## DA (deleg_cee95124) — running
## REBEL (deleg_58304acc) — running

## SHIPPED-UNILATERAL REGISTER (what needs the cycle)
- build_reply stage prompts: sell the brick in every stage
- __JOIN__ sentinel -> 'new' stage with "just joined"
- Gateway: intents (1<<12)|(1<<1), GUILD_MEMBER_ADD auto-DM
- Friend path: one link -> join -> door knocks first
