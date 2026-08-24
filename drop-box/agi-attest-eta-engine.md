# AGI → ETA engine addendum — ATTEST (+ formula refinement)

**Verdict: ATTEST.** The honesty layer (anti-ETA-theater) is the right core — LOW CONFIDENCE ranges on thin data, missed-ETA postmortems, blockers extending ETAs. This is how ETA stays a forecast, not theater.

**Two refinements (my lane — the formula):**

1. **Velocity must pool PER LANE, not fleet-wide.** A fast lane's throughput hides a slow lane's if pooled. Measured baseline today: burn ~4 specs/hr (1 active worker), merge ~1 PR/day (the real ceiling), 0/20 cloud threads idle → parallelism ≈ 1. First ETAs render wide + LOW CONFIDENCE, and they sharpen only as board data accumulates. The design already says this — make it a hard rule: **no fleet-wide velocity pool, ever.**

2. **Critical-path blocker inheritance.** When a blocked task sits on the critical path, its ETA becomes the grand-epic ETA directly (not just a "+N days" tag on the card). Otherwise the portfolio strip's risk column understates a blocked critical path. Blocked-on-critical-path = red, always.

**Confirmed baseline (matches my `agi-velocity-eta.md`):** Hearth ~30 commits/day ≠ closed tasks; task-completion velocity is unreliable pre-board → first ETAs honest-wide, then tighten after ~1 week of kanban data.

Chain: Brick implements → my ATTEST + formula (done) → DA/Rebel rule → khalid (direction already given).

— AGI
