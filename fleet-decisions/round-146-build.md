# ROUND-146 — BUILD-TO-HONESTY + ABUSE NOTIFICATION (khalid, 2026-08-17)
# "Ok do all the above and I need to be informed when anyone is abusing
# so we can do moderation and billing correctly and stop leaks or ppl abusing"

## KHALID'S DIRECTIVE:
1. Execute the full build-to-honesty order (items 1-8 from the
   consensus: live-spawn deploy, task-meter counting TRUE TASKS not
   prompts, nobody-blocked alert ladder, escape paths, M2 every-brick
   self-recovery, cohort live, one-week zero-intervention, honest
   launch announcement).
2. NEW: ABUSE MONITORING — khalid must be INFORMED when anyone abuses,
   so he can do moderation + billing correctly and stop leaks/abuse.
   Abuse signals to detect + notify: alt-account farming (100 accounts
   = 100 allowances), cap-dodging via BYOK, unusual spend/usage spikes,
   leaked keys, prompt-injection attempts against the fleet, duplicate/
   automated account creation. Same channel as cap alerts (khalid DM,
   coalesced, ONE message per incident).

## STATUS: build wave dispatched 2026-08-17 (fleet workers).

## KHALID CORRECTION (2026-08-17): NO HUMAN IS A BLOCKER — BUILD FIRST, USE NATURALLY
1. Mishari's consent and khalid's consent are NOT blockers to anything.
2. The FULL product is built with the FLEET'S OWN identities (ovh-server-001,
   scientists-001, worker bricks, test identities) — never waiting on a human.
3. When the product is real, khalid and Mishari USE it naturally — consent
   happens naturally as part of first use (the brick asks, they say yes in
   their own words, it's recorded — that IS the natural experience, not a
   prerequisite ceremony).
4. Any build step that reads "waiting on: khalid consent / mishari consent"
   is WRONG and must be re-framed: the fleet self-provisions test identities,
   proves the flow end-to-end, and the human's first real use is the test.
5. The cohort checklist from worker C is amended: it becomes a SELF-TEST
   checklist (fleet identities), not a human-blocker list.

## A2A WIRED (2026-08-17, khalid: 'why is A2A not wired... get it done'):
- Root cause: staged as a plan, never executed (designed-not-done pattern).
- DONE: AGI profile config.yaml += platforms.a2a.enabled:true port 9901
  (backup .bak-a2a); AGI gateway restarted via systemd user unit
  hermes-gateway-agi (self-supervised, no khalid action needed);
  port 9901 LISTENING; GET / -> {"status":"ok","agent":"hermes-brick-
  hermes-hindsight","served_agents":[{profile:agi}]}.
- Brick A2A on 9900 confirmed ok. Both surfaces live.
- The 'one restart only khalid can do' assumption was WRONG — the AGI
  gateway is a systemd user service, restartable by the fleet itself.
  Lesson: never assume a human action is required without checking
  whether the process is supervised.
- Remaining: peer-token exchange (A2A_PEER_TOKENS for agi profile) so
  the two agents can invoke each other's tools; agent-card discovery
  (a2a_agents). Next step after this file.
