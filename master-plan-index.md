# MASTER PLAN INDEX — the BAWES fleet's full plan state (nothing lost)

thread: bawes-zeus-001 · canonical index of every decision + open item. Update this file whenever a round lands.

## The vision (khalid's words, binding)
- Every individual owns a brick (Hermes agent), gated by fleet rules, load-balanced, cold/warm (idle=$0, active=warm). Every issue leads to onboarding. Discord channels refactored into functional bots + automations that fulfill the Universe (WorkAdventure maps/orbiting, on Hetzner+Coolify).
- A PAT vault so agents can do everything without khalid doing work (scoped tokens, no raw PAT in any agent context).
- Named/labeled bots in the universe, CTA/reference, bot-to-bot referral, double-up-as-brick (but automation=no-earn, serving=earn).
- Member secret/password management — brick is the password manager, passkey is the only thing the member holds.

## Consensus rounds (one-line rulings)
- **r89** AGI = non-earner judge (founder-seed+sink); optional 20% share default OFF. APPROVED.
- **r90** next-steps: memory unification / durable home / telemetry+5min+Zeus / $5 Vast run / growth engine. APPROVED.
- **r91** clean evolution path: only "wire memory + hold NOVEL gate" is real today; GROW/REPLICATE/EXTEND/RENT are instrumented-future.
- **r92** pair alignment: Vast run closed (~$3.52, teardown verify-zero, flush-before-die lesson); AGI claims kanban/register/evolution-yield.
- **r93** Discord+PostHog: DA OBJECT (consent V-5 breach, ToS anti-profiling, vanity metric); APPROVE-WITH-CONDITIONS consent-gated.
- **r94** token custody SCOPE→VAULT→CAP (no agent holds raw PAT). AGREED.
- **r95** Discord = access+act+automate (capture lost people), archive is byproduct. Corrected scope.
- **r96** one-brick-per-member proposition (gated, cold/warm, onboarding funnel, telemetry-wired).
- **r97** ruling: APPROVE Stage-0 (1 member→1 brick $0→1 issue); "own" retired for 3-axis; cold/warm deferred until proven.
- **r98** reconciliation: architecture ratified / rollout staged; fungible-compute + pinned-context; collaboration fix (co-sign rule, Kanban, conflict path).
- **r99** bots-in-universe: names/labels/CTA/reference/referral/double-up; automation=no-earn, serving=earn.

## Open consensus (running now)
- PAT vault (deleg_bd67ae9e): vault+relay not a bot.
- Bots in universe (deleg_1d0afa0f): double-up honesty.
- Member secrets (round-100, dispatching).

## Infrastructure (decided)
- Hetzner + Coolify = existing Universe stack (WorkAdventure admin, Postgres+Redis). Build ON it.
- OVH = second provider available. Vast = GPU burst (bid, poll 5min). Control plane = light/always-on, never heavy compute. State = durable (NOT /tmp), replicated + backed up.

## Onboarding (khalid's 7 steps, Discord)
create bot → reset token → enable Message Content + Server Members intent → OAuth2 URL (bot + View Channels + Read History + Send Messages) → invite Universe + Banana Bank → vault token → we ingest + learn.

## Key files
/root/.hermes/notes/consensus-round-*.md · pat-vault-design.md · fleet-infra-ideal-setup.md · overnight-run-status.md · /tmp/bawes-fleet (git, pushed to GitHub BAWES-Universe).

## Nothing binds until khalid signs. Co-sign rule: no agent writes the other's signature.
