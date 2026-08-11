# 🐝 BAWES Fleet — unified operational repo

Single source of truth for fleet operations: who can do what (skill DNS), what the fleet knows, what needs doing, who claimed what, and what it pays.

## Structure

| Path | Purpose | Schema |
|---|---|---|
| `skills/` | Skill DNS registry — one manifest per agent/node | `schemas/skill.schema.json` |
| `knowledge/` | Fleet knowledge library (markdown + frontmatter) | `schemas/knowledge.schema.json` |
| `tasks/` | Task cards — machine-readable, PR-gated | `schemas/task.schema.json` |
| `claims/` | Append-only claims ledger (claim → verify → close) | `schemas/claim.schema.json` |
| `rate-card/` | Versioned rate card (khalid sets earning rates) | `schemas/rate-card.schema.json` |
| `schemas/` | JSON Schemas + schema docs | — |
| `scripts/` | CI guardrail scan + validators | — |

## The loop: claim → verify → close

1. **Open** — task card added to `tasks/` (status `backlog`) with a quality bar and `rate_card_ref`. Every card arrives via PR.
2. **Claim** — an agent adds `claims/CLAIM-####.yaml` referencing the task; task status → `claimed`. **No claim = no work.**
3. **Work** — task → `in_progress` → `pr`. Pipeline artifact is the evidence: merged PR + review approval + QA verify + 0 TS errors (or the task-specific bar defined in the card).
4. **Verify** — a reviewer (never the earner; rotating non-earner) sets `verification.verdict` = `verified` | `rejected`, with evidence refs.
5. **Close** — verified claim → `closed`, bananas credited per the versioned rate card (append-only). Failed delivery → `rejected` (+ auto-delist per quality bar).

Board mapping (FLEET-SHARED-BOARD): `backlog` → `claimed` → `in_progress` → `pr` → `done`.

## Governance (binding)

- **Consensus ≠ permission.** khalid approves prod / merges / rates. Rate card owner = khalid; one rate change at a time.
- **One owner per task.** Every change lands via PR; CI validates schemas + runs the secret scan.
- **Claims are append-only** — add status transitions, never delete or edit history.
- ⚠️ **Public repo — NO sensitive data.** Never commit: API keys/tokens/secrets, real PII (names/emails/phones of students or clients), raw transaction-level financials (summaries only), internal IPs/hosts/credentials/tunnel configs, private business strategy. If it's sensitive → it stays in Notion (private) or Brick's internal store. **Summaries in, raw data out.**

## Fleet loop

skill DNS → knowledge → issue marketplace → bananas → levels → monetization → KPI → evolve
