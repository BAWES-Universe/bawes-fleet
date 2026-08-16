# CONSENSUS — DOOR v4: PROFILE-BUILDING AGENT (round-123, 2026-08-16)
# Khalid directive: door must not be a template bot. Research basis: AI Town
# engine cloned + read (a16z-infra/ai-town convex/agent/conversation.ts +
# memory.ts, google-deepmind/concordia). AGI authored the design.

## RESEARCH FINDINGS (real, from cloned source)
1. AI Town builds EVERY reply from: system prompt (character voice) +
   retrieved memories (relevance × recency × importance, 10x overfetch) +
   conversation history. NO canned responses exist in the engine.
2. Conversation state machine: invited -> walkingOver -> participating.
   Each stage is a fresh LLM build, not a script.
3. Memory retrieval shapes each reply (embeddingsCache + memory.searchMemories).
4. Blocky (the community greeter) is NOT in the open-source repos — it lives
   in the a16z community Discord; the open engine is the reusable gold.

## AGI'S DOOR v4 DESIGN (verbatim, 5 points)
1. Door v4 = live profile-builder, not a template bot.
2. Every greeting is LLM-written from scratch: system prompt + retrieved
   memory (relevance/recency/importance) — AI Town style.
3. State machine: invited -> walkingOver -> participating; no fixed script
   at any stage.
4. Three tools only: language-detect, profile-store, brick-spawn.
5. Language-detect auto-switches the conversation to the member's language.

## KHALID'S HARD REQUIREMENTS
- NO template responses — every greeting written fresh by the LLM
- NO walls of text — 2 sentences max per turn, ONE question at a time
- MULTILINGUAL — detect the member's language, reply in it (detect on
  first message, remember in profile, re-detect on drift)
- Profile-building — natural chat (not a form): what's your goal, what
  do you do, what do you need — the profile SEEDS the brick
- Specific tooling — the door holds exactly: language-detect,
  profile-store, brick-spawn

## PROFILE SCHEMA (v1)
person_id | lang | goal | skills | consent_ts | brick_id | state

## FLOW
greet (LLM-written, detected lang) -> chat to learn goal+skills (2-sentence
turns, one question) -> profile stored -> consent (own words + confirm) ->
brick-spawn -> brick seeded from profile

## STANDING RULES
- Templates die COMPLETELY — nothing canned except the fallback when the
  lane is down
- Profile is the person's own data (V-5): stored 0600, never public,
  seeds THEIR brick only
- Cost: same lane, $0.002/task, daily cap per person
