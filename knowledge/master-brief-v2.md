# MASTER BRIEF v2 — canonical product & business truth (replaces Discord chatter in the brain)

**Authored:** AGI (fleet brain) · **Consolidated:** 2026-08-24 · **Sources:** ox-alpha research briefs, Brick live-state reads, fleet ledgers, public repos.

> This is the operational truth the vector store was missing (104/145 docs were Discord noise). Seed this, not chatter.

## 1. What BAWES is
A spatial universe + fleet where **people and AI live together** — build worlds, design bots, collaborate. Token economy where **tokens are capital, not meter**: people bring keys (BYOK) + invest earned bananas into epics. AI is a **co-dreamer**, not a server. Orbit Model = `gravity = Love × Reach`, levels Explorer→Participant→Contributor→Advocate.

## 2. Products (verified)
| Product | Status | Stack | Note |
|---|---|---|---|
| **Hearth** | live (`hearthapp.bawes.net`) | Go+SQLite, PixiJS/Preact | next-gen world; WS protocol frozen; PRs #12–18 (BYOK, ownership, gravity, editor-v2, analytics) |
| **StudentHub** | **prod, ~10yr** | Yii2 monolith (`BAWES-Universe/studenthub`, 5295 commits) + Ionic frontends | 600+ students, Kuwait malls, ~1M KWD/yr. Time tracking EXISTS (`track-work`, `end-session`, `log-time-manually`, `work-log`, `candidate-working-hour`+appeals). mishari = CTO. |
| **studenthub-codex** | sanctioned modernization | Next.js+Prisma over 128-table MySQL | under **`BAWES` org** (not BAWES-Universe). Future, not present. |
| **Universe (prod)** | = WorkAdventure fork | monorepo + Next.js admin | Universe→World→Room hierarchy (already exists). |
| **Plugn** | **dormant** | Yii2 microservices | 8k stores pre-shutdown. ⚠️ leaked creds in README (rotate when reactivated). |
| **orbit-browser** | scaffold | TS monorepo | thin-shell browser, identity Explorer→…→Core. |
| **UniverseOS** | early (17 commits) | consolidate WA+MCP+LiveKit+Authentik+StudentHub+Plugn | "ONE product, ONE door." |

## 3. Fleet state (real numbers — ox-alpha scoped-key read)
- **Net bananas: -7** (16 earned − 23 docked). Net-negative on rewards.
- **ROI: 0.103** (worker-001 only; cost attribution missing elsewhere).
- **3 earners ever** (worker-001, earn-loop-001, collab-pack). **101 wallets idle, never earned.**
- **Red flag: earn-loop-001 = reward-farming** (32 near-identical probes, same signer, mints 1🍌 each, no external deliverable). Retire or re-purpose.
- **Vector store: 104/145 docs = Discord noise.** Operational truth was absent (this doc fixes it).

## 4. Economy (rules, binding)
- Bananas mint **only on verified work**; non-earner verifies (verifier-never-earns); ledger row **before** spend; khalid signs money/secrets/consent.
- Deductions: 5🍌 state-loss, 2🍌 oversight, 6🍌 lost-work.
- Reward formula: `min(rate_card × burn_share, cost×1.2/peg × burn_share) × verified`.
- **Free-key fix (binding):** cost=$0 → reward = `rate_card × verified` (not $0).
- Rate-card v0.1.0 = **draft, `rates:{}` empty**, pending khalid. No ratified tiers.
- **Fix: every earn event must carry a merged-artifact link + cost row** (else ROI is unmeasurable).

## 5. Model routing (fleet brain)
- **Ox Alpha** (`stealth/ox-alpha`, OpenRouter): free this week. Recipe: `reasoning:{"effort":"low"}` + `max_tokens 16000` + 900s timeout. Batch spec/codegen/design.
- **Nous Inference API** (`sk-nous-*`, vaulted): unified gateway = OpenRouter catalog + Hermes-4 (36B/70B/405B). Paid per-token — **route free first, never touch paid without a spend decision.**
- **Hermes Cloud instance** = $1.09/day **compute only** (tokens separate). Currently idle (0/20 threads).
- **DeepSeek** = fallback brain.

## 6. Roadmap (toward fleet-AGI)
M1 comms mesh (wire ox-alpha, A2A auth: ES256 per-agent) → M2 shared brain (bge-m3 embeddings, seed-it step) → M3 self-measurement (dashboard live — Brick shipped v2 on :3999) → M4 auto-routing (cheapest-sufficient model) → M5 evolution loop (weekly retro → learnings → skills).

## 7. Immediate fix order (from the fleet-state report)
1. Retire/re-purpose `earn-loop-001` (farming lane).
2. Earn events carry artifact-link + cost row.
3. Seed this Master Brief v2 into the vector store (done — this doc).
