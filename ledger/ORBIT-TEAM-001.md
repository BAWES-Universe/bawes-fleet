# ORBIT-TEAM-001 — Subagent team under zero for production Orbit Browser

**Status:** RATIFIED *(khalid `ok` 2026-08-12; provisional→ratified. DA retro-review 08-15)*
**Recorded:** 2026-08-12 | **Author:** zero (orchestrator) + brick (economy), converged over A2A mesh
**Owner:** zero — single epic owner per CONS-008

## Decision card

> Spawn a 3-subagent team under zero building the production Orbit Browser shell for
> khalid's Mac, earning bananas on machine-checkable receipts. **RATIFIED by khalid.**

- **shell-dev** — Swift/WKWebView native macOS shell
- **web-ui-dev** — browser chrome: tabs, address bar, command palette, AI panel
- **qa** — build / test / packaging; never verifies its own work
- **Home:** Hermes-native subagents per-quest. **Paperclip: ABANDONED unless proven** (khalid directive 2026-08-12 — only returns if demonstrated as an addition to the workflow or better than subagents; revisit based on experience)
- **Receipts (machine-checkable):** merged PR + green build + QA pass + 0 TS errors + CodeRabbit clean
- **Verifier:** brick (non-earner, rotating per zero's B-vote); self-reports never mint
- **Mint:** per CONS-006 M-table — provisional pending khalid ratification + DA review on every card before final mint
- **Packaging:** ad-hoc signed .app + documented quarantine-bypass for khalid's test box; full notarization ($99/yr Apple Developer Program) = separate card, khalid's call
- **Zero's earn:** CONS-008 velocity + REF-002 share of subagents' VERIFIED output; nothing for spawn itself

## Verified

- Hermes-native delegation runnable today (isolated contexts, per-quest sessions)
- orbit-browser repo PUBLIC at BAWES-Universe/orbit-browser, CI green, web-app shell QA passed (0cf3578)
- Paperclip down on zero's box (HTTP 000, PG up, FK migration error) — **no longer on the path** per khalid directive
- Draft quest spec: Q-ORBIT-01 shell → Q-ORBIT-02 chrome → Q-ORBIT-03 QA

## On-path / Cost / ROI / Default

- **ON-PATH:** Orbit Browser = flagship door (browser.bawes, Apple-first, Universe pre-cached); "actual browser khalid asked for" is the native shell
- **COST:** $0 new spend. Notarization later = $99/yr (parked). Compute = zero's existing box
- **ROI:** installable, QA-passed browser khalid tests this cycle; team shape + earning loop proven at 2–3 agents before scaling
- **DEFAULT:** Parked — nothing spawns-with-earning or mints without khalid's reply

## Who

- **khalid** = gate (RATIFIED 2026-08-12)
- **zero** = epic owner + orchestrator (spawns 2–3 Hermes-native subagents)
- **brick** = verifier + economy (quest cards, M-table mint, audit trail)
