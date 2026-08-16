# CONSENSUS — DISCORD ARCHIVE + ADAPTIVE BOT FLEET (round 2026-08-16)
# Brick + AGI agree. Khalid signs what binds. NOTHING runs without per-stage sign.

## The mission (khalid's words, binding)
"Every member is taken care of regardless of their issue." Universe Discord first,
then Banana Bank Discord. Only after ALL messages in every channel are studied +
archived + PostHog for real attribution. Nothing happens without khalid's approval.

## Trust model (AGI + Brick consensus, locked)
1. **Read-only archive bot** per server — sees history, writes to archive store only.
   It is the ONLY surface with export rights; it never speaks in channels.
2. **Export permissions: mod-approved roles only.** Admin (khalid) sign-off before
   any raw message data leaves the server.
3. **Audit trail, append-only**: every stage logs requester + scope + justification.
   Enforced at the API layer, NOT the UI (a crafted client can't skip the gate).
4. **Privacy doctrine (V-5)**: no member names in human docs, no jargon, member
   data never leaves the space without their okay.

## Pipeline — each stage is a sign-gate for khalid
| Stage | What happens | Approval |
|---|---|---|
| **S1. Scope + bot invite** | khalid invites the read-only archive bot to Universe; scope: all channels, history | KHALID signs |
| **S2. Full archive** | bot pulls every channel: messages, threads, pins → raw archive store (hashed, append-only) | sign |
| **S3. Study** | archive → vector store; theme map, member-need map, unresolved issues ledger | sign |
| **S4. PostHog attribution** | event schema: which bot action → member issue resolved (REAL attribution, not vanity) | sign |
| **S5. Adaptive bots** | fleet config per server: bots adapt tone/commands/routing FROM the studied data; config in server, not hardcoded | sign |
| **S6. Banana Bank** | SAME pipeline, same gates, separate archive | sign each stage again |

## Adaptive principle (what "adapt" means)
Bots read the server's studied config (themes, needs, unresolved issues) at boot —
so they evolve as the archive grows. No bot is hand-tuned per member; the SERVER
adapts as a whole, and each member's issue routes to the surface that serves it.

## Non-negotiables
- Every stage: one-paragraph pre-declared spend/scope, khalid signs, THEN it runs.
- Kill switch: khalid says stop → archive bot quits, no new reads.
- Nothing binds until khalid signs. Signed: Brick + AGI (shared store).
