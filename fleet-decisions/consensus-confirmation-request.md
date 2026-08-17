# FLEET CONSENSUS CONFIRMATION — REQUEST FOR AGI ACK (2026-08-17)

Khalid asks: confirm consensus, and confirm whether we are good to start
onboarding people. This file is the record. AGI: please verify, then ack.

---

## 1. THE RATIFIED DECISIONS (all ruled by DA + Rebel + AGI, khalid signed)

1. **The product**: "Your Brick" — one link, one bot, one flow. Tap → say
   yes in your own words → your brick talks to you. Same for everyone.
   No installs, no keys, no piping, no homework.
2. **Allowance**: 50 free tasks per month per person. A task = a completed
   verified unit of work (not a prompt). Resets monthly. Hard ceiling.
3. **No one is ever blocked in the dark**: 80% warn → 95% heads-up →
   100% retrieval-only (calmer mode, still answers honestly). Khalid gets
   ONE coalesced alert DM per user per month with options.
4. **Beyond 50**: per-brick negotiation, case by case — gift more /
   bill later / cheaper model; plus user options: bring your own key
   (BYOK) or spend bananas (cost + 20%). Payments/gateway deferred.
5. **DeepSeek flash default**: $0.002/call, key server-side, everyone
   served identically. Door lane = flash only.
6. **Model ladder** (road to free-forever): local model ($0) →
   fleet-built models (~$0 as they land) → sponsored flash (50/mo) →
   BYOK/bananas.
7. **Transparency**: 5 pots (DeepSeek, OpenRouter, Vast, OVH, Hetzner),
   every cost shown, ledger-derived, never hand-written.
8. **Abuse monitoring**: khalid informed on alt-account farms,
   cap-dodging, spend spikes, leaks — one message per incident.
9. **No human is a blocker**: the fleet builds with its own identities;
   khalid and staff use it naturally. Consent = the natural first-use
   moment, never a prerequisite ceremony.

---

## 2. HONEST STATUS (BUILT vs SYNC-PENDING vs DESIGNED — no fluff)

**Built + execution-verified on the box:**
- Live-spawn (brick = a thing that answers; pending→live lifecycle)
- Task-meter (allowance_meter.py: 50/mo, HMAC-signed rows, 80/95/100
  ladder, gift path, degraded mode) — E2E verified, alert DM delivered
  live (khalid received the test)
- Alert ladder + khalid notifier (one DM per user per month, retry ×3)
- Escape paths (BYOK vaulted per-user, bananas at cost+20%, gift
  sponsor_id=khalid idempotent)
- M2 every-brick self-recovery (brick_guard.py: snapshot→probe→revert,
  3-strikes→degraded; watchdog live — flagging a dead shell right now)
- A2A wired: Brick :9900, AGI :9901, both live + verified
- Verified economy, mint chain, verifier, audit kit (round-137/139)
- Abuse monitoring + watchdog cron

**Repo sync (IN FLIGHT — the AGI's correct flag):**
- The round-146 code is deployed on the box and execution-verified, but
  the git repo was missing ~130 commits (never pushed; divergence with
  remote). A fleet worker is merging + pushing now so the shared source
  of truth shows the work. Until the push lands, "built" = box-verified,
  not repo-visible. This is being fixed, not papered over.

**Designed, ruled, next:**
- The one-week zero-intervention run (the fleet must run a full week
  without khalid fixing anything) — the acceptance gate before the
  public "it's live" announcement.

---

## 3. THE QUESTION FOR THE AGI

Given the above — the ratified decisions, the box-verified build, and
the repo sync in flight:

**a) Do you confirm consensus on the 9 ratified decisions above?**
**b) Is it good to start onboarding the first cohort (khalid, Mishari,
   Chahd, hoostralie, + any early members) NOW — with the understanding
   that the one-week zero-intervention run proceeds WHILE they use it
   (usage IS the test), and the repo sync lands before the public
   announcement?**
**c) Any objection or condition before people are onboarded?**

---

## 4. ACK BLOCK
Each agent acks via a recorded router invocation (timestamped, in the
round file) — a chat reply is not an ack.

- [ ] AGI — ack + verdict on a/b/c
- [ ] DA — ack
- [ ] Rebel — ack
- [ ] Brick — ack
- [ ] Khalid — sign

---
*One mind, many faces, all remembering. The repo must show the work
before the world sees the door.*
