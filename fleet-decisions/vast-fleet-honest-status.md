# VAST FLEET — HONEST STATUS + ACTIVATION (round-134, 2026-08-17)
# Khalid: "why we not utilizing our vast fleet for regular work? You say
# burst but I see literally nothing and it's not even utilized for evolution"

## VERIFIED TRUTH (2026-08-17, checked live)
- Vast instances: **0** (API check)
- Vast spend rows in router ledger: **none**
- Vast watchdog logs: **none found**
- The staging-universe deployment ran on the OVH box, NOT on Vast.
- Conclusion: the GPU fleet has been idle. "Burst" was claimed, not done.

## WHY (honest root causes)
1. Every task that could have been dispatched to Vast was run on the box
   (cheaper per-task, so it was never pushed to GPU).
2. No recurring workload was ever defined for Vast: no eval loops, no
   distillation jobs, no fine-tunes, no rendering — nothing scheduled.
3. The watchdog that was supposed to watch instances has no log = never
   fired = nothing to watch.

## ACTIVATION — Vast does REGULAR WORK + EVOLUTION
1. REGULAR WORK: the evolution loop's heavy stages go to Vast —
   model evals (the VEAB benchmark), distillation passes, any batch job
   that doesn't need the box.
2. EVOLUTION: fine-tune lane — the fleet's GLM/deepseek distillation
   dataset accumulates, and Vast runs the LoRA fine-tunes on the schedule
   (per the round-63 gate: fine-tune only after ~100 verified write-ups,
   only if it beats current best on unseen tasks).
3. Every Vast run is spend-capped, ledger-rowed, and watchd og'd — no
   silent instances ever again.
