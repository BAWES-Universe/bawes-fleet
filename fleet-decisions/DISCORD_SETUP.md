# DISCORD ARCHIVE BOT — EXACT SETUP (verified against discord.com docs, 2026-08-16)

## What you need: only your Discord account. No server IDs, no channel IDs,
## no code. The bot auto-discovers everything (guilds -> channels -> messages).

## STEP 1 — Create the app (2 min)
1. Open https://discord.com/developers/applications
2. Top-right: **New Application** -> name it -> Create
3. Left sidebar: **Bot** -> **Reset Token** -> **Yes, do it!** -> **Copy**
   - This is the token. DM it to me. I vault it on the box, never in git.

## STEP 2 — THE CRITICAL ONE (intent) — DO NOT SKIP
4. Still in **Bot** settings, scroll to **Privileged Gateway Intents**
5. Toggle **ON**: **Message Content Intent** (the one with the red *REQUIRED* tag)
   - WHY: without this, Discord returns EMPTY content for all archived messages.
   - This is the step the first version of these instructions missed. Verified:
     discord.com docs — "Apps without the intent will receive empty values in
     fields that contain user-inputted content."

## STEP 3 — Invite (2 min)
6. Left sidebar: **OAuth2** -> **URL Generator**
7. Scopes: tick ONLY **bot**
8. Bot Permissions (appears below): tick ONLY:
   - **View Channels**
   - **Read Message History**
   - NOTHING else. This bot is read-only by construction — it cannot send,
     edit, delete, or manage anything.
9. Copy the generated URL (bottom) -> open in browser -> pick the Universe
   server -> **Authorize** (you'll see it's a read-only bot)

## STEP 4 — Hand off
10. DM me: "invited"
11. I run one archive pass. The audit trail shows exactly what it read.
    You see raw counts before we discuss S2.

## Notes
- You need **Manage Server** permission on the server to add it (you have it).
- No verification/whitelisting needed for small servers (only 100+ guilds).
- Kill switch: you say stop -> the bot quits mid-read, no new reads.

## Failure checklist (if a step looks off)
- Token reset shows "Reset Token" greyed? Wait 10s, retry.
- Invite URL shows red text? You missed a required permission tick in Step 8.
- "Bot cannot join" -> you're on a server where you lack Manage Server.
