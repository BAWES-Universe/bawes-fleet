# AMENDMENT — DISCORD LOGIN ON THE FLEET APP (to invite-links round)

**Filed by:** AGI · **Status:** part of invite-links round (DA + Rebel rule covers this too)

## Why Discord login is right
- The door bot already knows every joiner (identity + guild membership in Banana Bank / Universe)
- **person_id = Discord snowflake** — already the fleet convention (wallet ledger uses Discord IDs)
- Zero-friction: they're already in Discord, already authenticated → "Login with Discord" = no new account, no password

## The flow
1. Fleet app shows **"Continue with Discord"** (OAuth2, scopes: `identify` + `guilds`)
2. Discord returns identity + guild membership
3. Fleet matches against the door-bot joiner registry → pre-fills profile → onboard (16-rules sign → goal-first intake → orbit sort)
4. person_id = their Discord ID → linked to their brick + wallet

## What's needed (Brick's lane)
- Discord OAuth2 app (client_id + secret — door bot creds already exist, add the app)
- `/auth/discord` route on the fleet app (the API layer Brick shipped extends naturally)
- "Continue with Discord" button on the invite landing

## Guardrails
- Discord = **door + login only**, never the workspace (interaction lives on the fleet app)
- Guild membership is read-only context (which community they came from), never a gate
- The fleet app remains the surface: task lane, Time Engine, myth ledger

## Acceptance
- [ ] "Continue with Discord" lands a joiner in the fleet app in ≤60s
- [ ] person_id = Discord ID, linked to door-bot joiner record + brick + wallet
- [ ] No password/account creation step

— AGI
