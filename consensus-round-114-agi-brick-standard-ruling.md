# ROUND-114 — AGI brick standard RULING (target spec, sequenced)

thread: bawes-zeus-001 · nothing binds until khalid signs

## DA + rebel converged: APPROVE as TARGET SPEC, REJECT as current state
On disk: 3 of 5 unbuilt, 1 broken. I was declaring "mandatory" what isn't built — same future-fiction mistake, caught again.

- **SELF-RECOVERING (pt2) = zero code.** Grep for watchdog/repair/reroute → 0 matches. A sentence, not a mechanism.
- **INTERCONNECTED (pt4) = the KNOWN DEFECT still open.** brain.py sits at /tmp (non-durable); no gateway injects the vector store on boot. One boot-time read would end the amnesia — not done.
- **GENIUS (pt1) = broken dependency.** `agi_self_loop.py` imports `brain` from a path where brain.py doesn't exist.
- **GROWING (pt3) + TRANSPARENT (pt5) = real but standalone** — evolution_achievements / smart_evolution_guard / earn_loop_ai / public_audit exist, no shared boot path.

## The honest sequence (M1 → M2 → M3, defer M4)
- **M1 — INTERCONNECTED (the #1 fix):** wire vector-store injection on every brick's boot. Ends amnesia + out-of-sync. Trivial to build, currently missing.
- **M2 — SELF-RECOVERING:** detect (slow/wrong/failed) → re-route-or-flag → verify (non-earner). NOT self-modify (too dangerous); re-route-and-flag is the honest version.
- **M3 — GROWING:** wire the existing evolution loop (earn_loop → verified artifacts → growth curve) into every brick's boot.
- **M4 — FINE-TUNE at 100 artifacts:** DEFERRED until the artifacts actually exist.

## The gate (both critics): no khalid sign on the full vision until ONE brick proves M1+M2 end-to-end.
Then every brick gets the same boot path. Stop declaring "mandatory"; build M1+M2 on one brick, prove it, scale.

## Also flagged
FLEET-STATE.md has embedded NUL bytes (binary corruption) — the "single source of truth" is corrupted. Fix: rewrite clean + re-commit.
