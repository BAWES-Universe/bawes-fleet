# Skill marketplace

The **listing layer on top of skill DNS**. `skills/` answers *who can do what*; `marketplace/` answers *how proven is it* — adoption, ROI evidence, and lifecycle state. One listing per skill: `marketplace/<skill_key>.yaml`.

## Lifecycle (khalid condition — staleness)

```
proposed → active → stale → archived   (archived is TERMINAL; entries are archived, NEVER deleted)
```

- **Stale rule:** adoption count < `N` within `window_days` (config.yaml, khalid-owned knobs) → the watchdog (`scripts/staleness-check.py`) flags the entry → a PR moves `lifecycle.status` to `stale`, then `archived` with `archived_at` + `archived_reason`.
- The entry file stays in the repo forever (git history + retained file = archived, not deleted).

## ROI / reviews (khalid condition — evidence)

Every `roi.*` entry carries an **evidence ref to a committed artifact** (claim id, task id, PR, hash). Bare prose is not evidence.

| Signal | Meaning |
|---|---|
| `roi.load_count` | Instrumented loads/usages (append-only events) |
| `roi.incident_usage` | Skill used in incident runs + outcome (resolved/mitigated/failed) |
| `roi.citations` | Skill cited in merged artifacts (knowledge docs, PRs, claims) |
| `roi.reviews` | Quality reviews by a **non-earner** reviewer (rotating) |
| `adoption` | Peer adoption — **secondary** signal only |

Ratified rules (SKILL-SHARING-BANANAS card): usefulness = instrumented usage + outcome evidence; self-report zero weight; **bananas earned through the skill is never a metric** (circular). No per-use royalties until instrumentation is proven — load_count/incident_usage/citations ARE that instrumentation, so royalties can be re-examined once real data exists.

## Ledger (khalid condition — self-built, git-native)

- The ledger is **this repo**: `claims/` (append-only claim→verify→close) + `rate-card/` (khalid-owned rates). Git-native, replayable, no external service.
- **NO Xero / QuickBooks / any accounting SaaS. Ever.** (`config.yaml` → `ledger.external_services: []`).
- Tooling fallback, if ever needed: **open-source only**.

## Rules

- Same PR discipline + consensus gate as everything else (2/3 quorum, khalid ratifies).
- Secrets/PII-embedded skills stay private — never listed here (public repo).
- Metrics are appended by instrumentation (CI/audit runs); humans/agents never self-edit their own load counts.
