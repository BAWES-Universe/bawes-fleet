# ROUND-102 — member secrets ruling + the unified secret architecture (all three consensus done)

thread: bawes-zeus-001 · nothing binds until khalid signs

## Member secrets — OBJECT as-scoped (DA + rebel)
- The insight is right (collapse "N passwords" → one passkey). But "brick = password manager" is WRONG: it puts an LLM in the secret path (auto-fill = the brick reads/transmits secrets), the exact anti-pattern the token doctrine bans.
- **Correction: the RELAY is the manager, not the brick.** Passkey unlocks the member's vault slice; the relay generates/stores/rotates/auto-fills; the brick calls by handle, never sees a raw secret.
- Also objected: all member secrets on one box (SPOF × N), khalid as recovery root for N members, invisible custody (not consented), custody-vs-earn unseparated.
- **Stage-0 MVP: passkey-only for the brick's own login first** — before full secret custody.

## The unified secret architecture (all three batches converge here)
ONE non-LLM **vault + relay** is the secret custodian for BOTH:
1. **Fleet PATs** (Cloudflare/GoDaddy/Vercel/Supabase/GitHub) — scoped tokens, vaulted.
2. **Member passwords** — each member gets a vault slice unlocked by their passkey.

Rules that hold across all three:
- **No LLM ever holds or transmits a raw secret.** (Brick, AGI, and every bot call the relay by handle.)
- **Passkey = the only credential a member holds.** Nothing to remember or rotate.
- **Custody earns nothing** (infrastructure, founder-seeded). **Serving earns** (verified member resolution, non-earner verified, post-dedup NOVEL). The two are separate ledger identities — never the same.
- **GoDaddy + Supabase can't be scoped** as naively assumed — need proxy + policy, not "just scope it."

## The final Stage-0 gate (everything funnels here)
One member → one brick (passkey login) → one real issue → one verified resolution, at $0.
Vault = yes now (sops+age). Relay = only when a real task needs a token. Fleet of named bots = only after one referral→resolution is measured.

## Files (complete record, nothing lost)
/root/.hermes/notes/: master-plan-index.md · consensus-round-89..102 · pat-vault-design.md + da-ruling + implementation · da-ruling-round-99 + rebel-003 · da-ruling-pat-vault · member-secrets ruling. All mirrored to git (GitHub BAWES-Universe).
