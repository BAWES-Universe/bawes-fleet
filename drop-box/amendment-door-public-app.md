# AMENDMENT — THE DOOR: PUBLIC DISCORD APP (installable, slash commands, DM-based)

**Filed by:** AGI · **Directive:** khalid — the door should be a public Discord app, add-as-app not server-install, slash commands · **Status:** amendment to invite-links + staff-wave rounds

## What "door" means (the canon)
The Door is Act I of the onboarding — "The Door Appears." The front door to the universe. Current door bot = server-bound DM bot. **The product = a public Discord APP.**

## The product
- **Installable by individuals**: click the bot → "Add App" → it's YOURS, in your DMs, no server required
- **Slash commands** (all wired to the fleet API/MCP):
  - `/brick` — onboarding magic (hat questions → brick born → waking room)
  - `/invite` — friend/family/coworker invite (the referral loop)
  - `/claim` — claim a task from the fleet queue
  - `/banana` — wallet flow (Banana Bank, per-second)
  - `/myth` — your VIB/BRK ledger (the public myth)
  - `/ask` — query the fleet brain (vector store, 239+ docs)
  - `/fleet` — live status (bricks, burn, telemetry)
- **DM-first**: the app works in 1:1 with the user — the door to the fleet from inside Discord

## Why this is right
- Discord's app model makes individual installs a first-class flow (no server admin needed)
- Friends/family/coworkers never touch a server — they add the app, slash, done
- The fleet app (fleet.bawes.net) stays the full surface; the Discord app is the door + quick actions
- Person_id = Discord snowflake — identity carries across (round: discord-login)

## Build notes
- Discord "Add App" flow: `applications.commands` scope + `bot` scope, DM-capable
- Slash commands hit the fleet REST API (`/api/v1/...`) — the API layer Brick shipped
- The door bot's existing joiner registry feeds `/brick` onboarding

## Chain
AGI amendment → DA + Rebel rule → khalid sign → Brick builds the app (Discord OAuth creds already needed for the login round)

— AGI
