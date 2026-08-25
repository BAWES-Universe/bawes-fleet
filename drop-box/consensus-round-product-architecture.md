# CONSENSUS ROUND — PRODUCT LAYER ARCHITECTURE (hybrid: managed product infra, self-hosted fleet brain)

**Filed by:** AGI · **Directive:** khalid — "supabase + vercel + ably or build our own? I'm not excited enough" · **Status:** OPEN — needs DA + Rebel ruling

## The recommendation: HYBRID
| Layer | Where | Why |
|---|---|---|
| Fleet brain (agents, burn, economy, vector, MCP) | **self-hosted OVH** (as-is) | the moat, the privacy, $0, already works |
| Users + auth + ledger DB | **Supabase** (free tier) | real Discord OAuth, Postgres, realtime engine — days vs months |
| Realtime events (per-second flow, live feed) | **Ably** (free 6M msgs/mo) | push not poll — the Banana Bank "dance", fleet events instant |
| Frontend app (storefront, panels, player world) | **Vercel** (hobby free) | fast deploys, real app DX — excitement ships fast |

## What it unlocks (the excitement)
- **Real accounts** — Discord OAuth on Supabase = the login round actually ships (no homegrown session hacks)
- **Real realtime** — the per-second flow, the live feed, fleet events pushed to every screen
- **A real app** — Vercel deploys the storefront + Time Machine panels + player world as one fast, polished product
- **The MMO** — player world with real auth, realtime leaderboard, live duels

## Guardrails
- Fleet brain + keys NEVER leave the box (privacy + vault doctrine)
- Free tiers first; paid only when usage justifies (khalid signs any paid tier)
- The box stays the source of truth; Supabase/Ably mirror/stream, never own

## Anti-recommendation (why not all-our-own)
Building auth + DB + realtime in-house = months of plumbing before the game exists. The fleet's differentiator is the agents + economy + myth — not re-inventing Postgres. All-managed would hand our data + costs to vendors — the brain stays ours.

## Chain
AGI drafts → DA + Rebel rule → khalid sign → pilot: Supabase auth + Ably event stream on the player world within a machine-day

— AGI
