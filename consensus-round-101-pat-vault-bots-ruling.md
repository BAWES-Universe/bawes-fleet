# ROUND-101 — PAT vault + bots-in-universe: consolidated rulings

thread: bawes-zeus-001 · nothing binds until khalid signs

## A. PAT vault — APPROVE-WITH-CONDITIONS (DA + rebel + specialist)
Direction is binding (SCOPE→VAULT→CAP, round-94). But:
- **Vault NOW, relay LATER.** The vault half (encrypted custody: `sops`+`age` in a private repo, mode-600) already exists as a pattern (vast-keys/ovh.env/DeepSeek). The relay (7 endpoints, HMAC, audit) is **premature — zero live tasks need it yet.** Build the vault; defer the relay until a real task (deploy/query) exists.
- **"Scoped" is FALSE for two providers as I wrote it:** GoDaddy = account-level key (can't scope to a domain), Supabase `service_role` bypasses RLS. Those need explicit handling (proxy + column-level policy), not "just scope it."
- **Conditions before ANY token is seeded:** (1) real task that needs it, (2) recovery story for the vault (backup of the age key), (3) scoped-token correctness verified per provider, (4) the relay is a non-LLM binary with no raw-token readback, enforced (not asserted).

## B. Bots-in-universe — OBJECT as-scoped; APPROVE the no-earn automation slice (DA + rebel)
- **Names/labels/CTA/reference/referral = $0 and fine.** They're the capability register's human face + routing. Approve. (Referral = routing = automation.)
- **"Double-up-as-brick for extra bananas" = OBJECT.** A bot that runs automation AND earns = self-mint-shaped (round-89). The exact rules:
  - **R1** Identity earns nothing (name/label/presence/CTA/reference/routing earn $0).
  - **R2** Serving = mintable (real member issue → verified resolution, non-earner verified, post-dedup NOVEL).
  - **R3** Automation = un-mintable, founder-seeded (welcome/route/archive/relay/referral).
  - **R4** Referral earns nothing (no split, no credit — only the serving bot mints).
  - **R5** Verifier never earns. **R6** AGI mints only via round-89 (provenance-gated, capped).
  - **R7** "Double-up" only as a two-ledger-identity split (bot-role un-mintable / brick-role mintable on a verified serving receipt).

## C. The shared Stage-0 (both land here)
One named bot → one real member issue → one verified resolution (member's own words, non-earner verified, post-dedup NOVEL), with zero earning for names/routing/referral. Cost $0. This is the same gate as round-91/97: prove one real serving event before building the fleet.

## Files
da-ruling-pat-vault.md · pat-vault-relay-implementation.md · da-ruling-round-99-bots-in-universe.md (in /root/.hermes/notes/).
