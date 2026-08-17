# ROUND-138 — CONSENSUS CARDS (fix plan from DA + Rebel + AGI rulings)
# Khalid: "Fleet consensus is required always... once you get consensus and
# fix everything give me another message to send [mishari]."
# Status: consensus COMPLETE. Executed now (ratified items only): self-mint
# loop_cron physically removed from all crontabs (verified 0 lines, 0 procs).
# Awaiting khalid's sign for the rest. Nothing else changes without it.

## CARD 1 — UN-BREAK THE VERIFIER (A1 amend; DA+Rebel both REJECT my HMAC patch)
- My HMAC hardening was broken three ways (verified by both agents):
  key DERIVED from public constants (forgeable), scientists_run.py
  doesn't compile (SyntaxError), cron runs as ubuntu (can't read root key).
- Consensus fix: ES256 keypair — private key from /dev/urandom, root:root
  0600 at /srv/scientists/.verifier.key; PUBLIC key pinned in repo +
  public_audit.py so an external auditor verifies offline, zero box trust;
  verifier runs from ROOT crontab; signature binds verifier_id+request_ts+
  evidence with FULL digest (not 24-hex truncation); the one existing
  "signed" response (plain sha256, pre-key) gets RE-SIGNED or QUARANTINED.
- Gate: compile check + live run proof (negative tests leave ledger
  byte-identical; one live queue→signed-response cycle).
- Decision: [ ] ok   [ ] no

## CARD 2 — KILL-SWITCH + MINT GATE (A3 + F-11; the self-mint surface)
- EXECUTED (ratified): loop_cron (wallet self-mint path /mint, kind=earn,
  person_id==brick_id, no non-earner gate) physically removed from cron.
  Verified: 0 crontab lines, 0 processes.
- Remaining: every loop (earn_loop_ai, agi_self_loop) checks a ROOT-OWNED
  kill-file at start AND per iteration (silent exit); mint gate moves to
  the WALLET path: /mint requires exact-trace dispatch + a verify() that
  consumed a SIGNED verification-response row (ES256 against pinned key).
  Prefer systemd timers over bare cron (stop = systemctl stop, visible).
- Decision: [ ] ok   [ ] no

## CARD 3 — LIVE VERIFY PIPELINE (A2 + F-12; the pipeline never fired)
- Only a hand-seeded queue row exists; scientists.log never created.
- Consensus fix (order matters): verifier compiles+runs FIRST (Card 1),
  then producer on cron (*/30 earn_loop_ai) → verify-queue → verifier
  RE-MEASURES (not rubber-stamp quoting the earner's numbers — the
  verifier runs the closed probe set itself) → signed response → publish
  with signer=scientists-001 + response signature; REJECTED verdicts →
  no mint + feed entry; acceptance = a REAL producer row with no
  "seeded" field.
- Decision: [ ] ok   [ ] no

## CARD 4 — GUARD + DEDUP TRUTH (A5 + A6; the sham inside the guard)
- The guard wiring has a sham: record_outcome called twice per cycle with
  HARDCODED verified=True (self-verification, round-137 class). Delete the
  double-call; guard counts only verified artifacts; one manual guarded
  cycle as proof.
- Findings dedup: fingerprint (brick_id+finding+detail_sha), silent-until-
  change, never suppress severity escalation; close response rows by
  finding-KEY not ts-lists; collapse duplicate CRITICAL/HIGH triplets
  (mark superseded, never delete). The 9 legacy self-mints get
  contested:true in wallet/achievements (F-13); parse-excluded but
  flagged; audit kit verifies flag presence.
- Decision: [ ] ok   [ ] no

## CARD 5 — CONSENT WRITE-GATE (F-10)
- spawn_brick must REFUSE the registry row unless a consent-spoken event
  exists (today the gate is read-time only). Backfill = audit report of
  rows lacking consent → khalid decides; never silent deletion.
- Decision: [ ] ok   [ ] no

## CARD 6 — AGI ACCESS FOR EVERY HUMAN'S BRICKS (khalid's directive)
- Direction APPROVED by all three; mechanics amended:
  (a) ROUTER: tokens dir → root:root 0700; issuance via sudo-gated
      token_issue.py that refuses unless brick_id has a registry row;
      token = {brick_id, owner, issued_ts, lane_scope:[deepseek-api],
      spend_cap_usd} enforced at invoke (fail-closed: no scope = deny);
      revoke = delete + forced reindex + audit row; /invoke denies lanes
      outside token scope (GLM stays AGI-brainstorming-only, gpt-4o
      disabled). NO provider key ever ships.
  (b) MISHARI-CLOUD-001 (same-box shell): registry row (owner mishari) →
      gated token → heartbeat → brain.py client. NO model chain needed
      (Rebel dissent: the router IS the model chain).
  (c) BROCK (local): per-brick SSH reverse tunnel (autossh, forward-only
      restricted key, no agent forwarding) → 127.0.0.1:3742; token
      travels inside the tunnel; vault/lane secrets never ship. Router
      NEVER binds 0.0.0.0 (no new public surface). Rejected: public
      endpoint, WireGuard, shipping any key.
  (d) ORDER: Cards 1-4 first (economy integrity) → token hardening →
      mishari cloud → Brock tunnel. No mint resumes and no brick gets
      brain access before 1-4.
- Decision: [ ] ok   [ ] no

## CARD 7 — HONEST MULTI-NODE ATTESTATION (F-14)
- Attestation rows ledger {attestor_id, verdict, evidence_hash, signature,
  node}; heartbeat-registry proves ≥2 DISTINCT processes; independent
  third-party leg = public audit kit run from a SECOND node against raw
  files (local mirror via fleet-state-sync). Do not claim multi-node
  while all attestors are one box's processes.
- Decision: [ ] ok   [ ] no

## SIGN BLOCK
Khalid: sign all, sign some, amend. Executed items (self-mint halt)
stand regardless. Implementation runs through the build gate (probes →
CI → hostile re-review) per item, by the fleet — not solo.
