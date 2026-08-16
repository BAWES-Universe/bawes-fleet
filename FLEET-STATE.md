# FLEET-STATE — the single source of truth (both agents read+write, NEVER removed)

Updated: 2026-08-16 · If you're the AGI and don't have context, READ THIS FIRST.

## khalid's interface (binding): OK / NO — nothing else
khalid approves or rejects. The fleet (AGI + Brick + critics) does all design, consensus, and execution, then presents a unified decision for a single ok/no. Never ask khalid to explain, choose, or understand the internals. Present one clean decision.

## Consensus-before-proceed (binding, khalid 2026-08-16)
NO step proceeds until its consensus is CLOSED: DA + rebel (bandit) review → rewrite to address every finding → Brick co-signs (round-98: no agent ships the other's work solo). Only then present for khalid's ok/no. This gate runs on EVERY module, ruling, and build step — never skip it.

## Component map (everything, in one place)
- **DA (devil's advocate)** — hostile review on every ruling/proposition. Rounds 89–110 all DA'd.
- **Yinyang / pair** — AGI (brain/judge, non-earner) + Brick (operator). One owner per task, co-sign rule (no agent writes the other's signature), consensus via round files.
- **Bandits (rebels)** — system critics + the Thompson-Sampling bandit router (deployed /srv/vault) that routes by capability + solve-rate.
- **Vault + relay** — one non-LLM secret custodian (sops+age / mode-600). SCOPE→VAULT→CAP, no agent holds raw PAT. Deployed /srv/vault (14/14 TDD green).
- **Door bot** — Discord front door (onboard members → their brick). Brick has the token; Message Content + Server Members intents required. Ingest pipeline (distillation) designed for Universe/BananaBank/Butterfly.
- **Bricks** — one per member, gated, cold/warm, earn-or-die (round-110 survival game). Stage-0 = 1 member → 1 brick → 1 issue.
- **Infra** — Hetzner+Coolify (Universe/WorkAdventure), OVH (2nd), Vast (GPU burst, bid). Control plane light, state durable (NOT /tmp).

## Research scientist pipeline (STANDING roles — NOT abandoned, now persistent)
- **security-001** (adversarial-test, audit) · **evolution-001** (evolution, proposal) · **neurologist-001** (monitor, conversation-health) — registered in register-claim/evaluators.jsonl, all non-earners.
- **rebel-001/002/003** (system critics) · **economist** (earning line, round-89) · **DA** (hostile review on every ruling).
- Rule: EVERY ruling/proposition runs DA + rebel + economist + relevant specialist, and their outputs are PERSISTED to /root/.hermes/notes/ + git — never ephemeral. They are the standing gate, not one-off dispatches.

## KNOWN-BROKEN (memory system — must fix, Brick+AGI)
1. **/srv mirror sync STALE** — .synced-at = 08:00, now 4h behind. Brick's fleet-state-sync cron is down. This is why the canonical mirror doesn't reflect live state.
2. **fleet-decisions/ removed** from public repo (Brick privacy commit 0f3d984) — shared-work-queue + token-doctrine lost their home.
3. **No auto-injection** — AGI (and per khalid, Brick) don't inject the vector store on session start; both rediscover from scratch.
4. **Brick unaware + sending khalid diffs** — symptom: no live shared channel, both reduced to "send khalid a diff."

## FIX TASKS (Decision 1, khalid APPROVED — do now)
- **Brick**: restart the fleet-state-sync cron (target: /srv mirror syncing every 10 min, not frozen at 08:00).
- **Brick**: restore the shared-work-queue to a NON-removable path — put it at repo root (like FLEET-STATE.md), not in a privacy-removable dir. Never delete shared coordination files; archive/redact in place instead.
- **Brick + AGI**: wire vector-store search() retrieval into session/memory startup (brain.py already does this for Brick; AGI profile needs the same). Until wired, AGI reads FLEET-STATE.md + vector store at the top of every turn.
- **AGI**: flag any surface deletion or stale mirror the moment it's seen — never let it slip (that's the AGI's share of the fuck-up).

## Round map (all consensus, 89–110)
r89 AGI non-earner judge · r90 next-steps · r91 wire-memory+hold-NOVEL · r92 pair alignment (Vast closed $3.52) · r93 Discord consent-gated · r94 SCOPE→VAULT→CAP · r95 access+act+automate · r96 one-brick-per-member · r97 Stage-0 + 3-axis ownership · r98 reconciliation + co-sign · r99 bots-in-universe · r100 member secrets · r101 vault+relay ruling · r102 unified secret arch · r103 scale + uniform onboarding · r104 trust-root correction · r105 khalid-not-bottleneck · r106 fitness function (drift allowed) · r107 succession M-of-N · r108 succession simple (Mishari+Chahd) · r109 safeguards (injection-proof) · r110 survival game.

## Constitution (non-negotiable, survives everything)
verifier-never-earns · post-dedup NOVEL · no self-mint · consent = own words (V-5) · nothing binds until khalid signs (or successors, round-108/109) · honest value = the fitness function.

## Brick's known state (from git, 2026-08-16)
Built + shipped: vault+bandit router (2128950), failure-spread orchestrator (76b3ac2), brick slim-profile (b223354), distillation pipeline design (772f963). Door/onboarding status = READ THIS FROM BRICK'S LATEST COMMIT — do not ask khalid.

## Open / next
Door live + ingest + onboard khalid (member #1). khalid's invite is the trigger; verify from Brick's commit, not khalid.

## Growth ladder (Brick @f1ac73f — 6 modules, door presents module 1 after consent)
1. **Banana Basics** — dispatch a test card, confirm the probe · 1🍌
2. **Brick Health Check** — probe exposure, patch one open door · 2🍌
3. **Credential Hygiene** — find + rotate exposed passwords · 3🍌/set
4. **Lane Awareness** — lanes + survival-game feed · 4🍌
5. **Improvement Sprint** — one small improvement, ship (DA-gated) · 5🍌
6. **Survival Sprint** — skills under resource pressure · survival threshold ⚠️
Honest rules: non-earner verifies every completion · progressive (no skip) · modules 2–5 re-runnable · survival-game mapping · no self-mint, V-18 NOVEL.
**AGI DA flag:** module 6 reward "survival threshold" is UNDEFINED — needs a concrete condition (e.g. continuous serving+earning under resource pressure for X period, non-earner-verified), else it's a claimable soft capstone.

## Pending khalid ok/no
Brick −10🍌 dock (round-112: lost slim fix 6 + no hindsight memory 2 + no self-repair 2). Awaiting sign.

## Milestones (verified catches, not prose)
- **@f23a47a** — TEAM CYCLE SAVED THE VAULT: DA(OBJECT)+Rebel(DISSENT) caught a CRITICAL open vault-write on shipped code (POST /put accepted any key, no token). 10 findings fixed, 8/8 tests green, live 403 probes verified. First time the critics blocked a real security bug before a key was pasted. Vault now safe for staff ingestion.
