# CONSENSUS — DISCORD DISTILLATION PIPELINE (Brick + AGI, 2026-08-16)
# AGI-authored design (via brain). Brick executes. Khalid's data = goldmine.

## Source (live)
Door bot "Universe Door" (id 1538492803196125214) — read access to:
- Universe (1261204689261695037)
- Banana Bank (1392786857812819968)
- Follow the Butterfly (1393184925632430130)
Token vaulted /srv/secrets/door.env (0600). Never in git, never echoed.

## What we extract (the goldmine)
Need intents, unanswered questions, lost-member signals, topic clusters,
recurring asks — AGGREGATED only.

## Schema (AGI's, verbatim)
{cluster_id, topic_embedding, signal_type, need_type, count,
 hashed_member_ids[], first_seen, last_seen, priority, status}

## Privacy (V-5, AGI's words)
All member ids SHA-256 hashed. All text discarded after
embedding/aggregation. Brain retrieves by topic/signal, NEVER raw
content or names.

## The 3 automations (AGI-designed, build order)
1. **Triage Bot** — classifies incoming messages by need, dedupes into
   clusters, updates counts.
2. **Unanswered-Question Bot** — flags questions with no reply in 24h,
   routes to fleet brain.
3. **Lost-Member Bot** — detects inactivity/negative sentiment, triggers
   brick-per-person onboarding/re-engagement.

## Output
Distilled docs -> vector store -> brain retrieves -> every issue routes
to onboarding (brick-per-person architecture, ratified @28a2e5a).

## Rules
- READ-ONLY on Discord. No writes, no DMs, no moderation without khalid sign.
- Nothing damaging without approval. Kill switch: revoke token at portal.
- Signed: Brick + AGI.
