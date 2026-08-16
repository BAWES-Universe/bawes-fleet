# CONSENSUS — MULTI-PROVIDER ROUTER + SPONSORED EVOLUTION (round-116, 2026-08-16)
# Khalid's directive: maintain API access to ALL; add models beyond deepseek;
# sponsor usage for evolution. AGI authored the design (verbatim below).

## AGI's design (10 points)
1. VAULT PER LANE: each provider key encrypted, scoped by provider+model+
   usage cap, with per-lane token budgets.
2. ROUTER: N lanes, each a weighted bandit over provider/model pairs;
   rewards = quality (task-specific eval) minus normalized cost.
3. SELECTION: Thompson sampling per task type; explore ~5%; exploit best
   cost-adjusted model otherwise.
4. LANES: earned (finops, etc.) and sponsored (evolution). Sponsored =
   khalid-funded lane, separate ledger, hard monthly USD cap.
5. ACCOUNTING: two ledgers — earned (revenue-attributed) / sponsored
   (khalid-funded). Each lane tracks token counts, cost, per-model drift.
6. EVOLUTION LANE: sponsored runs carry priority queue; no earned budget
   cross-subsidy; overage gated by cap, alerts before halt.
7. KEYS: never in code; vault fetches per-lane at request time, injects
   via router context only.
8. BANDIT STATE: shared per lane, persisted; cold-start priors from
   historical cost/quality baselines.
9. FAILOVER: if top model 5xx/timeouts, auto-fall to second-best in same
   lane without retry storm.
10. AUDITING: every selection + cost + quality logged (0600), same as
    today's lane ledger.

## What this means concretely
- The vault (built, DA-hardened) already holds keys per service — this
  extends it: one vault, N provider keys, each scoped + capped
- The bandit router (built) already does Thompson sampling over arms —
  this extends it: arms = provider/model PAIRS, reward = quality minus
  cost (not just success)
- Two ledgers from day one: earned (what bricks pay for) vs sponsored
  (what khalid funds for evolution) — never mixed, never cross-subsidized
- Khalid's keys stay HIS: vault-fetched per request, injected only into
  the router context, never into agent memory

## Khalid's role
- He holds/rotates ALL provider keys (OpenRouter, Anthropic, Gemini,
  OpenAI, local) — the vault stores them scoped
- He sponsors the evolution lane: hard monthly USD cap of his choosing,
  alerts before halt, overage gated

## Standing rules
- No self-mint: sponsored evolution earns nothing; it's funded, and its
  output must still be verified by non-earners
- No cross-subsidy: earned lanes never pay for evolution; evolution never
  inflates earned lanes
- Cost declared per task, ledger per lane, audit 0600 forever
