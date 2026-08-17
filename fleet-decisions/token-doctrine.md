# TOKEN DOCTRINE — binding (Brick + AGI + khalid, 2026-08-16)
# Rule: SCOPE -> VAULT -> CAP. No agent ever holds a raw PAT.

## Who gets what
- Discord archive-bot token: khalid DMs -> Brick vaults on box (0600). ONLY new token for S1.
- Cloudflare/Vercel/Supabase PATs: NEVER raw to any agent. Khalid creates SCOPED tokens
  per service (one zone, one team, RLS-guarded) -> router vault /srv/bricks/router/tokens.
- Personal bot / AGI / Brick: access via router relay under declared caps. Bill-once.
  Prompt-injection on any chat surface CANNOT touch a key that isn't there.

## Why
A PAT = account-wide power. One prompt-injection in any bot = account-wide damage.
Scoped token = one job. Vaulted = not in context. Capped = router enforces spend.

## Existing proof
- DeepSeek key: vaulted mode-600, never shared, $0.002/task via router. Works.
- ovh.env/vast-keys.env: vaulted 0600. Works.
- Vast doctrine (carried): vast hosts are UNTRUSTED by rule; workers get scoped
  relay tokens, revoked on destroy — a leaked token burns cents, not the account.

## Enforcement
- New secret -> scoped token -> vault -> test once -> log which agent can call it.
- No raw PAT in any repo, .env in git, DM, or agent context. Ever.
- Kill switch: revoke at the provider (khalid's dashboard) = instant, no code change.
