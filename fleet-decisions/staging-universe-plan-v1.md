# STAGING UNIVERSE — DEPLOYMENT + EVOLUTION (round-132, 2026-08-17)
# Khalid: "Use it for true evolution and deployment of staging universe
# that evolves. Competing with one we have deployed on universe.bawes.net
# which uses livekit and our bot server and all. Also the browser and
# messaging ui."
# Direction: STOP the member-message research loop (no more tokens on
# Discord corpus). Spend the frontier key + Vast on REAL deployment:
# a staging universe that EVOLVES, competing with prod universe.bawes.net.

## THE GOAL
A fleet-owned staging universe (from the workadventure-universe repo:
~19 services — play/back/maps/uploader/messages/redis/synapse/oidc +
bot-server + LiveKit/egress/minio + discord) deployed on our own infra,
that EVOLVES — our bricks are the brains, our economy is the spine, the
AGI self-loop evolves it — competing head-to-head with prod
universe.bawes.net (Coolify-deployed, Livekit + bot server).

## WHAT "EVOLVES" MEANS HERE
- The AGI self-loop (deepseek-pro reasoning) drives staging changes:
  hypothesis -> deploy -> measure (RAM, boot time, cost/bot, ROI) -> learn
- Our brick system wires in as brains (goal->quest->verify->mint)
- Browser (Orbit Browser = the door) + messaging UI ship WITH the universe
- Compare against prod on cost/efficiency/ROI (the round-110 mandate)

## INFRA FACTS (verified on the box)
- RAM: 7746 MB total, 5809 avail — full 19-service envelope needs ~8GB
  (core 12 ~2GB; +bots +livekit/egress/minio +admin +discord beyond)
- Disk: 53G free. Docker 29.1.3 present. Box is KVM.
- Repo: /srv/universe-staging (349MB source, copying now)
- Prod universe.bawes.net: HTTP 302 -> @/bawes/bawes/headquarters map

## SEQUENCE (pack the paid box first — free-first doctrine)
1. CORE stack up (docker-compose.yaml, no-synapse variant if RAM tight):
   play/back/maps/uploader/messages/redis + oidc-mock. Verify HTTP 200.
2. BOTS (docker-compose.bots.yaml: bot-server + uploader) — our MCP +
   brick brains wire here.
3. LIVEKIT (docker-compose.livekit.yaml: livekit + egress + minio) —
   AV; measure RAM before committing (DA: it's the heavy one).
4. BROWSER + MESSAGING UI — Orbit Browser door + chat surface.
5. EVOLUTION LOOP on staging: AGI self-loop proposes changes, applies,
   measures, reports — the evolving universe khalid asked for.
6. BENCHMARK vs prod: RAM, cost/bot, boot time, ROI — public numbers.

## AV ARCHITECTURE (khalid: "we have our stack in Coolify having separate
boxes for Livekit and turn" — round-133, 2026-08-17)

PROD PATTERN (Coolify): Livekit on its OWN box, TURN on its OWN box.
STAGING FOLLOWS THE SAME SHAPE:
- The livekit+egress+minio containers on the staging box = STACK-PROOF
  (18/18 up, verified) — NOT the production AV path.
- Real AV = dedicated Livekit box + dedicated TURN box, mirroring prod.
- The 3 confirmed blockers on the single box (no TURN, UDP port mismatch,
  no traefik UDP entrypoint) are WHY prod uses separate boxes — staging
  will not fight them; it will replicate the split.

## TOKEN POLICY (khalid: "forget member messages, don't waste tokens")
- Member-message research loop: STOPPED. No tokens on Discord corpus.
- Frontier key + deepseek-pro: evolution + staging deployment only.

## 8-HOUR EVOLUTION REPORT (2026-08-17 13:40, khalid: "what did the agi evolve to")
- AGI self-loop ran 21 cycles unsupervised (cron heartbeat, no prompting needed)
- 25 evolution-feed entries; state: cycles=21, last_action set_env:play
- The loop DID break the world 3x (cycles 17/18/20: play env changes -> :8082 404)
  and healed it (21: back to 302/healthy). Honest verdict: trial-and-error
  evolution, self-directed and self-correcting, NOT yet smart evolution.
- World currently healthy: :8082 302 (OAuth redirect = normal), 18/18 up.
- CRON FAILURES at 13:10/13:26: staff-activity-audit + scientists-alive both
  timed out (provider idle 604s > 600s limit) — transient provider outage on
  the LLM lane, NOT the self-loop (self-loop uses GLM lane directly; crons use
  the shared model). Both re-ran clean: audit execution_success=true,
  scientists 3 findings. No cron config broken.
