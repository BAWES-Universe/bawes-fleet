# THE PLAN — BRICK IDENTITY ARCHITECTURE (one app, two modes, consensus-seeking)

**Filed by:** AGI · **Based on khalid's correction:** the brick bot IS the orchestrator + staff tool, "Brick" name is taken, OAuth is on that app · **Status:** PLAN — needs DA + Rebel ruling → khalid sign

## The real situation (no more wrong pictures)
- The "Brick" bot = the fleet's orchestrator + staff tool (staff use it today, in Universe + Banana Bank)
- The name "Brick" is taken → no second bot with that name
- OAuth was configured on that same app → mixing public identity login with orchestrator/staff access

## The plan: ONE app, TWO modes, cleanly separated
Discord supports one app with **both** a bot (guild-install) and a **user-install** mode. That solves the name problem and the safety problem at once:

1. **Mode A — User-install (public):** people add "Brick" as an app (Add App). OAuth identity (`identify` + `guilds` only, read-only), slash commands in DMs (`/brick`, `/claim`, `/ask`...). **No bot in servers, no server access, no orchestrator functions.** This is the public door.
2. **Mode B — Bot (staff/orchestrator):** the existing brick bot stays exactly as-is in Universe + Banana Bank — the door bot, staff access, the orchestrator's Discord presence. **No user-facing OAuth attached to this mode.**

## The safety boundary (the core of the plan)
- User-install OAuth = identity only. Cannot read messages, cannot manage servers, cannot touch orchestrator functions
- Orchestrator bot = server role unchanged; **never carries user-facing OAuth**
- A user who adds the app gets identity + DM commands — they NEVER get orchestrator/staff powers
- Staff keep their existing bot access — unchanged

## What gets built/wired
1. Wire the **tested `discord_auth.py`** (20/20 PASS, on the box) into the user-install flow → "Continue with Discord" → consent → person_id=snowflake → onboard
2. Discord app config: user-install enabled + scopes `identify guilds` (correct scopes, correct redirect)
3. Slash commands on user-install mode (`/brick` onboarding first)
4. **Credentials inventory card** — every token/key in the vault, what it accesses, last rotation — for khalid's safety review (this is the "is it safe" answer, in writing)

## What stays untouched
- The orchestrator bot's server presence + staff access
- The door bot's joiner registry + DM flow

## Chain
Plan (this) → DA + Rebel rule → khalid sign → Brick wires per this plan (no freelancing) → credentials inventory card delivered with it

— AGI
