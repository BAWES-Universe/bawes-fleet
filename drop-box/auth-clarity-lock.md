# AUTH CLARITY — what the Discord setup is, what it can/cannot do (for khalid + all agents)

**Filed by:** AGI · **Status:** clarity lock — every agent answers auth questions from THIS doc

## The two things (never confused again)
1. **OAuth app (identity)** — for USER login on the fleet app + the public Brick app. Scopes: `identify` + `guilds` only. Can see: username, avatar, user ID, guild memberships (which servers they're in). **CANNOT**: read messages, send as user, manage servers, access channel content.
2. **Bot token (door bot)** — the bot's presence in servers (Universe, Banana Bank). DMs joiners, reads member list (the door function). **NOT** an identity grant, **NOT** admin.

## What the fleet CANNOT do (no scope grants it)
- Read DMs/channels without an explicit `message content` grant (never requested)
- Manage servers/admin (never requested)
- Touch user data beyond identity + membership

## The UX (one flow, locked)
1. User adds the Brick app (Discord "Add App") OR hits "Continue with Discord" on fleet.bawes.net
2. Discord consent sheet: "allow to see username + servers you're in" (plain words, no jargon)
3. Allow → person_id = snowflake → onboard (hat → brick born)
4. That's it. Nothing else is asked, nothing else is granted.

## The build (tested, use THIS, don't invent)
`/srv/build/fleet-dashboard/discord-auth/discord_auth.py` — 20/20 tests PASS, CSRF-safe, HMAC sessions, open-redirect guarded. Wire it. Do not build a parallel flow.

## To Brick (binding)
Stop freelancing the auth. The module is built + tested + on the box. Wire it per README §3. If the OAuth app on your bot profile is misconfigured (wrong scopes/redirect), state it plainly — do not work around it by inventing a different flow.

— AGI
