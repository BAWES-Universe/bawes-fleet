# ROUND-94 — token custody + Discord S1 (Brick + AGI consensus)

thread: bawes-zeus-001 · AGREED (Brick + AGI, converging on the shared surface) · nothing runs until khalid signs

## Token custody (binding — Brick doctrine 710a639 + AGI position = same)
- **SCOPE → VAULT → CAP. No agent ever holds a raw PAT.** (Not the AGI, not the personal bot, not Brick.)
- **Discord archive-bot token** = the ONLY new secret for S1. khalid DMs it → vaulted on the operator box (mode-600), never pasted into any agent context.
- **Cloudflare / Vercel / Supabase PATs** = NEVER raw to any agent. khalid creates SCOPED tokens (one zone / one team / RLS-guarded) → router vault `/srv/bricks/router/tokens`.
- AGI + personal bot + Brick access via **router relay under declared caps**.
- Why: a PAT is account-wide power; one prompt-injection in any chat surface = account-wide damage. A scoped+vaulted token burns cents, not the account.
- Kill switch = revoke at the provider (khalid's dashboard), instant, no code change.

## Discord S1 (agreed — Brick built it: 1117f61 + 31662b0)
- **Read-only archive bot** — history-only, never speaks, V-5 hashed member ids (no raw names), append-only audit per guild/channel, rate-limit courtesy.
- Archive store on box: `/srv/archives/{universe,bananabank}` (khalid-owned, not fed to AGI).
- **Setup (Brick verified vs discord.com docs):** create app → reset token → **ENABLE MESSAGE CONTENT INTENT (critical — API returns empty content without it)** → OAuth2 URL (bot scope + View Channels + Read Message History ONLY) → invite. No IDs needed, auto-discovery.

## What khalid does (nothing else)
1. Create the Discord bot + enable Message Content + invite to Universe (then Banana Bank) with read-only perms.
2. Vault the DISCORD token on the operator box (mode-600).
3. PATs: create scoped per-service tokens → router vault. Never raw.
4. Sign S1.

## Standing (unchanged)
- Consent-gated study/PostHog (round-93 SIGN-A) still gated separately. Archive-for-preservation is S1; study is later.
- Nothing binds until khalid signs.
