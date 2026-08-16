# PAT VAULT — safe custody for all khalid's tokens (Cloudflare, GoDaddy, Vercel, Supabase, GitHub, …)

thread: bawes-zeus-001 · goal: everything runs without khalid doing work, but no raw PAT ever touches an agent.

## The core decision: a VAULT + RELAY, not a "bot"
An LLM bot holding PATs = a single prompt-injection away from full account loss. The safe
form is a **non-LLM relay** that holds scoped tokens and exposes narrow endpoints. Agents
call the endpoint by name; they never see the token value.

## Design (SCOPE → VAULT → CAP, carried from round-94 + Brick doctrine 710a639)
1. **Scoped tokens, not full PATs.** khalid creates least-privilege tokens once:
   - Cloudflare: API token scoped to the zone(s) — never the global API key
   - GoDaddy: production API key/secret scoped to the domains
   - Vercel: token scoped to the team/project
   - Supabase: service-role key scoped to one project + RLS
   - GitHub: fine-grained PAT scoped to specific repos + minimal perms
2. **Encrypted vault** (on the existing Hetzner/Coolify stack — Infisical/Vault or sops+age in git, mode-600). Tokens encrypted at rest.
3. **The relay** — a thin audited HTTP service (not an LLM) that:
   - reads the vault, never returns raw values
   - exposes ONE endpoint per action: `/vercel/deploy`, `/cloudflare/dns`, `/supabase/query`, `/github/push`, `/godaddy/domain`
   - each endpoint uses its SPECIFIC scoped token, rate-limited + allowlisted
   - logs every access (who/agent, what, when) — audit trail
4. **Agents call by handle** ("deploy prod") → relay does the real call with the scoped token → returns the result. AGI/Brick/bricks never see a raw PAT.
5. **Kill switch** — revoke at the provider (instant), plus a relay kill flag.

## Why this is safe
- No raw PAT in any agent context → prompt-injection can't leak what isn't there.
- Scoped = a leaked token burns one project/zone, not the account.
- Narrow endpoints = the relay can't be abused for arbitrary calls.
- Audit + kill switch = every use visible, instant cutoff.

## Why khalid does ~zero ongoing work
One-time: create scoped tokens + seed the vault. After that, agents auto-provision/deploy/manage via the relay; khalid only signs what binds + revokes if something's wrong.

## Honest risks (for DA + bandits to attack)
- The vault is a single point of failure → mitigated by encryption + access control + audit + kill switch, but still one target.
- A relay bug (SSRF/injection) could abuse scoped tokens → mitigated by narrow allowlisted endpoints + no raw exposure.
- "Scoped" is only as good as khalid's token creation → GoDaddy/GitHub are account-level if scoped wrong. This is the one thing that must be done right.
