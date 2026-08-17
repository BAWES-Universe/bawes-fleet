# ROUND-139 — GENIUS SELF-RECOVERING BRICK + INTERCONNECTED AGI (khalid directive 2026-08-17)
# "Every brick we serve ppl and I and anyone interacts with to be genius and
# self recovering and growing... true interconnected agi with pricing and
# performance transparency... Get consensus and don't waste my time."
# Round: DA (supports, with build order) vs Rebel (redesign operational layer,
# reorder build) + AGI (brain, via router). Consolidated below into cards.

## VERDICT: architecture KEEPS (spawn-package, router, ES256 chain, mint gate)
## but build ORDER is reordered by the Rebel's execution-verified evidence.

## WHY THE REBEL CHANGED THE ORDER (all verified on the box, read-only):
- NO supervision substrate: 7 brick services run bare nohup; only door-gateway
  has systemd Restart=always. heartbeat.py WRITES liveness; NOTHING READS it
  to respawn a dead brick. A process OOM-killed cannot restart itself.
- round-138 OBJECTs still live: verifier.pub ubuntu-writable (pin not pinned),
  loop.stop writable (kill not physical), sudoers NOPASSWD:ALL (ubuntu=root),
  ufw INACTIVE, :3999 public.
- Feed header says "VERIFIED MINTS: 11"; genuinely ES256-verified = 2 (9 are
  contested history). An auditor recomputes that instantly.
- ONE node: mishari-cloud-001 = paper brick (empty dir, no process; heartbeat
  written by mother). A2A = round-61 read-only, do_POST=501. Mesh ≠ mesh at N=1.
- Hermes on the box is DORMANT (no process, empty hooks) — gateway health
  hooks don't exist here yet.
- capability-curve.json = ONE point. Dispatch lane idle since Aug 16 08:03.

## THE CARDS (one build order, from the Rebel's amended list + AGI's order):

### CARD 1 — SUPERVISION SUBSTRATE (F-15) — FIRST
Every brick service gets a systemd unit (Restart=always, RestartSec, health
ExecStartPre/Post) OR a root-owned watchdog cron that READS heartbeat-registry
and respawns dead bricks (≤60s). Physical kill: root-owned loop.stop dir.
The door-gateway is the working pattern — generalize it.
[ ] ok   [ ] no

### CARD 2 — ROUND-138 OBJECTS 1-3 (trust, before any "genius" claim)
(a) runtime pubkey pinned: verifier.pub root-owned + chattr +i, hash-checked
at the two runtime load sites (orchestrator.py:372, verify_consumer.py:84);
(b) physical kill-file (root-owned, cron-removal alternative);
(c) scope sudo (remove NOPASSWD:ALL) or restate the threat model honestly.
[ ] ok   [ ] no

### CARD 3 — FEED TRUTH (F-17)
Header math corrected: VERIFIED MINTS: 2 (not 11); 9 legacy marked contested
in the FEED, not just the wallet. Capability claims cite V-18 3-layer standard
(post-dedup novel rate, verified artifacts, causal-chain position) or none.
[ ] ok   [ ] no

### CARD 4 — ONE SCHEDULED E2E CYCLE PROVEN
Producer + scientist are on cron (live queue row 16:30) but the consumer log
is 0 bytes — no cron "PUBLISHED" line has EVER printed; both mints were
manual/harness. Acceptance: one FULL scheduled cycle (queue→ES256→publish on
cron, not harness) lands a wallet row with signer + response_signature.
[ ] ok   [ ] no

### CARD 5 — GENIUS BRICK DEFINITION (AGI's, ratified as the standard)
(a) retrieval-first: ≥90% of answers use retrieved docs when context exists,
0% invented from empty context — brain injects a MANDATORY context envelope
(retrieved_docs, capability_card, honesty_fallback) at EVERY call;
(b) honesty under memory failure: "I don't have memory of that" — never guesses;
(c) per-brick measured capability: monthly accuracy/refusal/latency evals,
public score routes load (brick-capability.json + curve).
[ ] ok   [ ] no

### CARD 6 — SELF-RECOVERY (after Card 1)
Rollback on bad self-change: snapshot→probe→auto-revert, banned-actions
pre-flight, 3 strikes→degraded-mode (read-only, retrieval-only, escalate to
fleet queue — never khalid). Door freshness gate so members never reach a
dead brick.
[ ] ok   [ ] no

### CARD 7 — SECOND NODE (F-14, the mesh at N≥2)
Mishari's device brick (16 rules signed Aug 14) gets install + heartbeat
evidence; only then is the mesh a mesh. Unification (A2A write-surface,
V-8 lane-scoped worker-ON) comes AFTER this + Cards 1-4.
[ ] ok   [ ] no

### CARD 8 — TRANSPARENCY SURFACE (F-19) — honest, ledger-derived
Per-brick /status card + fleet-status member section: cost/call (real),
latency_ms (NEW: router must log it), activity, caps, receipts. Prices stay
labeled "provisional, unanchored" until real cost rows with invoice_doc_hash
exist (peg). Never hand-written numbers.
[ ] ok   [ ] no

### CARD 9 — GROWTH (after Cards 1-4): Vast + evolution re-enable
agi_self_loop re-enable needs YOUR sign (paused round-137). Vast $18.94:
first GPU workload = the atomic-rollback evolution loop runs a real
capability experiment; fine-tune gate stays at 100 verified artifacts.
[ ] ok   [ ] no

### CARD 10 — ACCEPTANCE GATE BEFORE THE FIRST MEMBER
Recall test, honesty audit, capability row, kill/rollback drills all pass
+ one-week zero-intervention gate (fleet runs 7 days without khalid
touching anything) → THEN the first member brick ships.
[ ] ok   [ ] no

## SIGN BLOCK
Rebel signs: F-11 gate, ES256 chain, cron wiring, token issuance, founder-seed
provenance, door pattern. Refuses to sign ANY self-recovery/interconnected/
genius claim before Cards 1-4. Khalid: sign all, sign some, amend — nothing
builds until your ok. No fluff: the cards ARE the claim, in order.
