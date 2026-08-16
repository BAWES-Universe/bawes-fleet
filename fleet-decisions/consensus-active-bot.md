# CONSENSUS — ACTIVE DISCORD BOT (Brick + AGI, 2026-08-16)
# Replaces the read-only archive bot (khalid rejected it — right call).
# ONE active bot per server: reads history, DMs members, auto-onboards
# joiners, captures lost people with automations. Not a read-only ghost.

## Consensus (AGI + Brick)
1. One ACTIVE bot per server = single source of truth for join/leave state.
   Eliminates split-brain moderation, duplicate DMs, cron-juggled ghosts.
2. Historical reads + auto-onboarding close the loop on lost members with
   ONE persistent process.
3. Safety (AGI's words): least privilege (never Administrator), tokens in
   env/secrets never code/repos, rate limits + cooldowns to prevent spam.

## What the bot DOES (the functionality — no more asking khalid per feature)
- Reads all channel history (understanding the server, who's lost, what's asked)
- DMs members (welcome, follow-up, rescue — with cooldown rules)
- Posts in channels (answers, routes, help)
- Auto-onboards new joiners the moment they arrive (greeting + next step)
- Catches lost people: joiners who never spoke, questions never answered,
  members who went quiet — automations find them and reach out

## Permissions (the ONE invite — supersedes DISCORD_SETUP.md)
- View Channels, Read Message History, Send Messages, Send Messages in
  Threads, Read Message History, Add Reactions, Manage Threads
- Intents: Message Content (REQUIRED), Server Members (joins/leaves),
  Guild Messages
- NEVER: Administrator, Manage Server, Manage Channels, Kick/Ban

## One invite, all functionality. Khalid does it ONCE, forever.
- App name: BAWES Archive is obsolete -> create ONE app named as chosen
- The bot is the door: reads + acts + automates. No per-feature tokens.
