# OWN-THE-BRAIN ROADMAP (round-147) — fleet-owned model, DeepSeek stays running

thread: bawes-zeus-001 · khalid: "figure out what it takes to own the brain, and DeepSeek utilization doesn't stop"

## Goal
Fine-tune Qwen3.8-27B on the fleet's OWN verified knowledge → serve it ourselves → replace DeepSeek's per-call tax **only where our model wins on quality AND cost**. DeepSeek remains the default brain throughout.

## Three stages (each gated, nothing ships without the previous passing)

### Stage 1 — AUDIT + BENCHMARK (quality gate)
- Qwen 27B full precision (A100) audits the fleet (dishonest claims / gaps / risks / evolution plan).
- Benchmark harness: run Qwen 27B head-to-head vs DeepSeek flash on the fleet's REAL task set (door conversation, retrieval, code review, audit). Metric: task-resolution quality, non-earner verified.
- **Gate:** proceed to fine-tune ONLY if Qwen ≥ DeepSeek on quality. If not, stop — DeepSeek stays, no further spend on Qwen.

### Stage 2 — FINE-TUNE (the owning step)
- LoRA fine-tune on the fleet's verified knowledge only:
  - vector store (43+ docs) + extracted Discord signal + verified-work receipts
  - filter = non-earner-verified work ONLY; dedup; format as instruction/turn pairs
  - consent/privacy (V-5/R-1): only consented data, IDs hashed, no raw secrets
- One-time cost ~$5–10 of A100 time. Result: a fleet-owned model (weights are ours).

### Stage 3 — SERVE + PHASE-IN (the payoff)
- Serve fine-tuned Qwen 4-bit on cheap GPUs (~$0.16–0.30/hr RTX 3090); full precision on A100 where precision matters.
- **Phase-in thresholds (both must hold):**
  - Quality: fine-tuned Qwen ≥ DeepSeek flash on the benchmark (re-measured, non-earner verified).
  - Cost: fleet call volume > break-even (~150 calls/hr 4-bit, ~650/hr full-precision).
- Phase order: internal fleet traffic first → member traffic only after a week of stable parity.

## DeepSeek policy (binding)
DeepSeek flash stays the DEFAULT brain for every brick, the whole time. The own-model is additive and takes over a lane only after it wins quality + cost. No cutover, no regression risk, no bill spike.

## What to measure (verifiable, not prose)
1. Benchmark score: Qwen vs DeepSeek on N real tasks (quality delta, signed by non-earner).
2. Fine-tune loss + held-out eval.
3. Cost per resolved task: own-model vs DeepSeek, at real volume.
4. Phase-in traffic %: internal → member, tracked over the one-week parity run.

## Status
DESIGNED — awaiting DA + rebel consensus, then khalid ok/no.
