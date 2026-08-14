# Brick Profile — CI + DA + staging-channel checklist (Z-53 build plan)
## Status: READY FOR REVIEW (pair-DA) → staging channel 1537851998840422492 → Mishari boots

- [x] Spec written (Z-53 rulings folded: config not runtime, 4-item min-alive, 4 forgotten items)
- [x] brick-profile.yaml (identity, Discord token env, model endpoint, A2A read-only enforcement, heartbeat)
- [x] brick_profile.py (bootstrap + verify: boots → identity → channel → hello; fails closed)
- [x] ci.yml (syntax, compile, min-alive bar, read-only enforcement, no-secrets)
- [ ] pair-DA independent review (before anything ships)
- [ ] test against staging channel 1537851998840422492 (banana bank server) — NOT Mishari's real channel
- [ ] Mishari applies profile → boots → hello wave in registry

## Z-53-3 forgotten items — status
1. Per-brick Discord bot token: **Mishari creates via dev portal (his onboarding step, prompted — round-55: khalid supplies nothing)** → 1Password brick vault → mode-600 on device → env BRICK_DISCORD_TOKEN. NOT in repo/manifest. The prompt to Mishari is queued in the onboarding runbook.
2. Read-only ENFORCEMENT: peer_toolsets web/vision/session_search only; reject list terminal/code_execution/memory/file — CI verifies declaration; pair-DA verifies enforcement semantics.
3. Model endpoint: LM Studio 127.0.0.1:1234 primary + fallback — in profile.
4. Rounds 51–52: files created (round51-lane1-deploy.md, round52-installer-gate.md).
