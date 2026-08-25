# RULING — PRODUCT ARCHITECTURE: SELF-HOSTED FIRST (consolidated, ox-alpha research + AGI attest)

**Filed by:** AGI · **Status:** consensus — ox-alpha researched, AGI attests, supersedes hybrid proposal

## The ruling
**Self-hosted first, $0, on the existing box.** Extend Hearth's proven pattern (SQLite WAL + Go websockets + the same dashboard box). No Supabase/Ably/Vercel.

## Why (the evidence)
1. **Capacity:** the box handles 5–10k registered users with the Hearth pattern — proven
2. **Supabase free tier pauses on 7-day inactivity** — wrong tool for a 24/7 fleet (even though a continuously-used project wouldn't pause, why risk it)
3. **Vercel free tier prohibits commercial use** — the investment market is commercial → disqualified
4. **Ably/Pusher redundant** — Go websockets already running on Hearth
5. **Auth already built** — tested Discord auth module + users/sessions live
6. **No vendor can pause, price-gouge, or lock us in**

## The build (ox-alpha greenlit)
- Game tables alongside world tables: players, xp, levels, quests, skills, leaderboard
- Character sheet = an object in the universe (players.html + player-world.json already render it)
- Migration path: SQLite → Postgres when >5–10k users (portable SQL, cheap move — a good problem)

## What stays from the hybrid thinking (the good parts)
- Real Discord OAuth on our own auth (the tested module)
- Realtime push via our own websockets (per-second flow, live feed, duels)
- The app ships as one polished surface at fleet.bawes.net

## Chain
ox-alpha research ✓ → AGI attest ✓ → **khalid sign** → ox-alpha specs game tables → free lanes build → verify on the box

— AGI
