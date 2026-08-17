# VAST BENCHMARK 001 — HONEST STATUS (2026-08-17)
# Card 9: first GPU workload. Key wired (found /root/.hermes/vast-keys.env,
# khalid@bawes.net, credit $18.94 verified live). Watchdog hardened
# (destroys phantom contracts too) + cron'd 45m. Spend pre-declared $3.00 cap.

## DONE + VERIFIED
- Key live, credit $18.94, 0 instances at rest (watchdog destroy verified).
- API leg COMPLETE: deepseek-v4-flash 5/5 on the fixed benchmark
  (math/logic/knowledge/code/reasoning), total cost $0.00016, avg latency
  ~1.8s. Results: bench-api.jsonl (5 rows, scores 1.0 each).
- Watchdog: vast-watchdog cron 45m no-agent silent-until-change; destroys
  any contract it mints (success OR phantom — old code only on success).

## NOT DONE (honest)
- GPU leg (local model on Vast vs API) did NOT complete before the worker
  iteration limit. Instance was launched ($0.0378/hr bid, 3060 Ti) and
  destroyed; benchmark driver killed; no lingering spend.
- Quality-per-cost comparison table: API leg numbers only. GPU leg pending.

## NEXT (needs one re-dispatch, still under the same $3.00 cap)
- Re-run GPU leg: launch → run llama.cpp sm_86 pinned build → same 5
  questions → score/cost → destroy → table (API vs local).
- Ledger row: vast/vast-benchmark-001 0.30USD pre-declared (cost ledger).
- Spend to date: ~$0.02. Credit: $18.94.
