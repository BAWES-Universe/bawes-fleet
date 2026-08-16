# CONSENSUS — VAULT BOT + BOT FLEET + PER-BRICK SECRETS (Brick + AGI, 2026-08-16)
# AGI-authored ruling (via brain, direct invoke). Brick executes. Nothing binds until khalid signs.

## 1. VAULT BOT (holds ALL khalid's PATs: Cloudflare, GoDaddy, Vercel, Supabase, GitHub, etc)
AGI ruling: **MOSTLY SAFE WITH GUARDRAILS.** Approve IF:
- tokens are least-privilege (only necessary repo/domain scopes)
- expiry/rotation is AUTOMATED
- vault access is audit-logged
- router enforces allow-listed actions
DANGER if: scope too broad, any agent can invoke router for sensitive actions,
vault is single point of compromise.
ADD: per-PAT usage quotas + alert on anomalous calls.
Conclusion: safe if scoping + rotation + audit enforced; otherwise risky.

## 2. BOT FLEET IN UNIVERSE (lightweight bots doubling as bricks, names/labels, CTA/referrals)
AGI ruling: **ACCEPTABLE WITH RULES.** Require:
(a) public, unique labels
(b) NO bot may refer itself or any bot under same owner
(c) referral reward only AFTER referred bot proves non-trivial activity (not just creation)
(d) rate-limit CTA posting to avoid channel spam
(e) any bot acting as brick must show owner/operator identity
Conclusion: good with anti-self-dealing + activity thresholds — genuine growth loop, not a sybil farm.

## 3. SECRETS FOR NON-TECHNICAL BRICK OWNERS (1Password too complex)
AGI ruling: **USE PER-BRICK OWNER KEY FILES.**
- Generate ONE single-use master key per brick (like a safe-combo card)
- Store as QR code + plaintext file on a USB stick physically controlled by owner
- No password rotation, no complexity
- If compromised: owner "knocks down the brick" — destroy old brick, mint replacement
  with new key, preserving history/earnings via admin verification
- Key confirmation every 90 days (no password complexity)
Conclusion: one key, one brick, no rotating — simple beats complex for non-critical bricks.

## Saved-forever plan parts (from this session, all documented)
- Door bot: Universe Door 1538492803196125214, token /srv/secrets/door.env (0600), 3 servers
- Distillation pipeline: AGI schema @772f963 (triage/unanswered-Q/lost-member bots, V-5)
- Brick-per-person architecture @28a2e5a (state machine active/cold/reactivating, fleet-edge LB)
- Active bot doctrine @910a1b2 (one active bot per server, least privilege)
- Zero-homework model @f94ebbe (khalid does nothing except the one-time bot app)
- Token doctrine @710a639 (scope->vault->cap, no agent holds raw PAT)
- Vault pattern proven: deepseek key, router bill-once
