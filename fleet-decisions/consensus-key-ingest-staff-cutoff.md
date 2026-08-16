# CONSENSUS — KEY INGEST + STAFF ACCESS CUTOFF (round-117, 2026-08-16)
# Khalid asked: is Discord safe for his OpenRouter key? Do we cut staff
# access to the main assistant? AGI ruled (verbatim below).

## RULING 1 — KEYS NEVER TRAVEL THROUGH CHAT
- NEVER paste keys in Discord/chat: transit, history, and staff-visible
  assistant all leak
- SAFE PATH: a secure ingest surface (door's ingest form/field) that
  writes DIRECTLY to the vault — never through the assistant's context
- Applies to khalid's OWN keys too — the vault exists so no key ever
  touches chat, not even the owner's

## RULING 2 — STAFF DO NOT USE BRICK DIRECTLY
- Standard: each staff member onboards via DOOR to their OWN brick,
  provisioned with their OWN scoped Attio/Notion credentials
- The brick ACTS AS THEM: consent, scoped to role, fully audited
- Brick is khalid's lane + fleet ops ONLY — never staff-facing service

## RULING 3 — ENFORCEMENT (what Brick does when staff DM it)
- Auto-reply: the DOOR link + "no direct service"
- Takes NO actions, LOGS the attempt
- The door is the only ingress; everything else redirects to it

## Implementation needed
1. INGEST: a one-time secure paste surface on the box (vault writes,
   auto-destroy page) — so khalid can add his OpenRouter key without
   it touching chat
2. DOOR AUTO-RESPONDER: staff DM -> door link + "no direct service"
3. Brick policy: staff DMs = log + redirect, zero actions

## Standing rules
- Zero homework: ingest is ONE tap + ONE paste, then the vault holds it
- The vault was DA-hardened for exactly this (0600, fail-closed, env keys)
- No key ever appears in agent context, audit, or logs
