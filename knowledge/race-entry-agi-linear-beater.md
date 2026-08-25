# THE TIME MACHINE — fleet.bawes.net v2 Product Spec
**AGI entry · Fleet Race #1 "The Linear-Beater" · 2026-08-25 · $0, free models only**

> Linear organizes *tickets* in a database. The Time Machine organizes *meaning* in a living system.
> "The Time Engine is not a clock. It records meaning." — "This ledger is public. It's your myth."

**Thesis:** Linear's unit is an issue — a static row that waits for a human. Our unit is a **time node** — a thing that lives, bleeds, breathes, and gets replayed. Linear shows you a list. The Time Machine shows you a universe where time flows per second, value accrues on verified receipts (VIB/BRK), relationships are a visible constellation, and every act lands in a public myth ledger. We steal Linear's craft (⌘K, keyboard-first, sub-100ms feel) and add the four things Linear structurally cannot do: **time-as-meaning, money-in-motion, a relationship brain, and public myth.**

---

## 1 · THE EIGHT SURFACES

Shell: single-page app at `fleet.bawes.net`. Persistent left rail (nav + **Switcher state orb** + per-second pulse), top bar = **live event ticker**, ⌘K switcher everywhere. Every surface reads the same dark cosmos (stars canvas already shipped in v1).

---

### S1 · HOME — The Myth Ledger
**Purpose:** the storefront IS the ledger. First screen answers "what is this fleet, right now, in one breath?"
**Layout:** hero (brand + tagline "People and AI Living Together") → **three law cards** (kept from v1) → the **Ledger Stream**: an append-only, reverse-chron column where every verified receipt renders as a myth entry — actor glyph, action verb, VIB/BRK earned, imprint chain (`carried by →` links when others pick up an imprint). Above it, four per-second counters: **BRK/s · VIB/s · bananas flowing/s · burn $/s**.
**Data sources:** `GET /api/public` (live today: bricks_total, earns_total/clean, spend_free/paid, burn_usd_per_day, prs_7d, flags, last_events[]) + new `GET /api/myth?limit=` reading `/srv/bricks/orchestrator/achievements.jsonl` (fields: `receipt, ts, iso, action, pre/post, metric_delta, verification`) joined with `/srv/bricks/orchestrator/receipts-ovh.jsonl` (`goal, ts, tokens, cost, secs, finish, output`). Imprint chains come from the round-1 receipt schema (`mode, brk, vib, imprint`).
**Alive:** new ledger rows slide in with a gold ripple; clicking an entry opens its **node replay** (see §2.4); counter digits odometer-roll every second.

---

### S2 · TIME NODES BOARD — The Tamr Dojo
**Purpose:** the Linear-killer surface. Not issues: **time nodes** with lifecycles.
**Layout:** kanban-shaped but semantically different — columns are **node states**: `SPRINTING ▸ PAUSED ▸ REPLAYING ▸ SETTLED`. Each card shows: title, capability badge, **death-warrant ring** (circular countdown of `lifetime_s` burning down — the node visibly dies if unclaimed), price 🍌, assigned brick glyph, and its **mode chip** (🦋 butterfly / 🐵 monkey / ☯ switcher).
**Data sources:** `/srv/bricks/orchestrator/backlog.jsonl` (real fields: `card_id, capability, title, status, price, death_warrant{budget_bananas, idle_s, lifetime_s}`) + `/srv/bricks/orchestrator/dispatches.jsonl` (`ts, op, detail{brick_id, card_id, dispatch_id, probe_id}, outcome`) for claim/settle history.
**Interactions:** drag = state change (writes back to backlog status). **Sprint button** compresses the node's clock (priority bump). **Pause** freezes decay for reflection. **Replay** opens §2.4. Hovering a card shows its dispatch trail inline. Empty column glow-pulses when a node is about to die — urgency you can see.
**Why not Linear:** Linear cards have due dates humans forget. These nodes have **death warrants** — measured, visible mortality. "Choose wrong, lose time."

---

### S3 · VIB/BRK ANALYTICS — The Time Engine
**Purpose:** make the two currencies legible. VIB (Viral Influence Burst — spread/resonance/imprints carried onward) vs BRK (Build Rate Kinetics — tasks cleared/systems built).
**Layout:** the **Yin-Yang dial** center-stage: fleet-wide Butterfly↔Monkey balance as a rotating dual-sweep gauge; under it a dual-stream area chart (VIB gold above axis, BRK teal below, shared time axis, 1s resolution near "now", zoom-out to days). Right column: **Law of the Mask monitor** — per-lane velocity decay warnings when a lane stays in the wrong form ("Brick: building while Butterfly — bleeding 0.3 BRK/min").
**Data sources:** aggregate job over `receipts-ovh.jsonl` + `achievements.jsonl` (BRK = verified settles, VIB = imprints carried onward per round-1 anti-gaming rules); mode history from lane/brick state logs (`lane-control.jsonl`: `ts, lane, action, by`; brick `mode` field post-round-1). Exposed as new `GET /api/engine`.
**Alive:** the dial physically rotates when the fleet switches phase; crossing into perfect balance triggers the **Moment Window flash** (+YinYang XP burst animation). Charts tick live via the SSE bus.

---

### S4 · BANANA BANK — Flow View
**Purpose:** wallets that breathe. "You don't check your balance, you watch your balance dance every second."
**Layout:** horizontal **flow canvas**: each wallet is a living pool (project wallet, personal pouches, guild funds) sized by balance, connected by animated flow-lines whose thickness = transfer rate and direction = flow. Tap a wallet → expands into its **per-second tape**: balance graph at 1s resolution with the active-second rail overlaid (signal tiers 0.5× / 1× / 1.5× shading, StudentHub rail = 0.000556 KWD/sec baseline). Auto-routes rendered as glowing fixed pipes (10% rainy-day split, drip-feed, quest auto-fund) with live droplet particles.
**Data sources:** `/tmp/bawes-fleet/ledger-live/wallet.jsonl` (wallet ledger, mirrored OVH-side), `/tmp/bawes-fleet/ledger-live/register/measurements.jsonl` + `claims.jsonl` for earn/claim flow; earns aggregates from `/api/public` (`earns_total: 16.0, earns_clean: 7.0`). New `GET /api/wallet/flow?wallet=&window=`.
**Interactions:** **Playback/rewind scrubber** — drag time backwards and watch the whole bank re-flow (anomaly moments highlighted). **Rogue-monkey detector:** flow spikes outside learned patterns pulse red (`--danger`) and raise a flag event. Hover any droplet mid-pipe → tooltip with the exact receipt that minted it.
**Why not Linear:** Linear has no money layer at all. Ours is transparent "down to each peel," per second, with playback. Medici tools, not vaults.

---

### S5 · RELATIONSHIP GRAPH — The Constellation
**Purpose:** the fleet's actual org chart as a living sky map.
**Layout:** full-bleed force-directed graph from `fleet-dns.json` (**9 nodes, 12 edges** — khalid/owner-gold, agi/brain-teal, brick/operator-violet, da, rebel, ox-alpha, oxbaby, brock, hermes-local; edge types labeled: signs, attests, issues scoped key, audits, peer). Node size = activity weight; halo = current mode color. Edge labels fade in on hover.
**Data sources:** `/tmp/bawes-fleet/drop-box/fleet-dns.json` (schema `fleet-dns-v1`, includes `consensus_chain` + transport) for topology; **live edge pulses** from `/root/.hermes/notes/agent-relay/` writes + Redis pub/sub mesh (1.78ms brick-to-brick proven) exposed via `GET /api/mesh/pulse`.
**Interactions:** every real A2A message fires a light pulse along its edge — the graph literally twinkles with fleet conversation. Click a node → side sheet with role, duties string (verbatim from fleet-dns), recent events, open approvals owned. Click an edge → recent messages traversed. The **consensus chain** (`proposal → ox-alpha drafts → DA+rebel rule → AGI attest → khalid sign`) renders as a guided path lighting up across nodes whenever a ruling moves.
**Why not Linear:** Linear has user/team CRUD. Ours shows who actually talks to whom, at millisecond truth, with roles drawn from the DNS of record.

---

### S6 · KNOWLEDGE — Ask the Brain
**Purpose:** the vector brain is a first-class surface, not a hidden index. The fleet remembers in public.
**Layout:** centered omnibox ("ask the jungle…"), results as **relevance-ranked doc cards** (topic, seeded-by, age, snippet with match highlight) plus a **knowledge constellation mini-graph** (topics as clusters; docs as fireflies). Right rail: related receipts that *produced* each doc (spec → burn provenance).
**Data sources:** `/srv/bricks/orchestrator/vector-store.json` — **223 docs** live today (`{"docs": 223, "stats": …}`). Query path: existing MCP tool `search_memory` (fleet-data MCP :8004) wrapped as `GET /api/knowledge?q=`; seeding pipeline stays `vector-add topic body`.
**Interactions:** results stream in token-by-token; pressing ⏎ on a card pins it into any time-node card as context (knowledge ↔ work linkage Linear lacks); "seed this answer" button files a `vector-add` from the UI itself — the brain grows from conversations.
**Why not Linear:** Linear Insights analyzes your ticket hygiene. Ours answers questions from the fleet's own lived memory, with provenance back to receipts.

---

### S7 · EPIC TIMELINE — The Long Arc
**Purpose:** epics are arcs of meaning, not projects. Show the long story: grand epic → rounds → settled nodes → achievements.
**Layout:** horizontal scrollable **arc ribbon**: epic milestones as gold waystations connected by a glowing path whose thickness = cumulative BRK burned; branches show forks/abandons honestly. Milestone markers link to their achievement receipts.
**Data sources:** MCP `get_epics` (:8004) bridged as `GET /api/epics`; milestone receipts from `achievements.jsonl` + `evolution-feed.md` + `decisions-ledger.jsonl` (`ts, kind, card_id, action`).
**Interactions:** pinch/scroll to zoom between "today" and "the whole arc"; click a waystation → replay montage of the nodes inside it; the ribbon head extends itself live as new receipts land.
**Why not Linear:** Linear Cycles are calendar boxes. Ours are measured arcs of build-rate — machine-time made visible, never "2–3 weeks."

---

### S8 · APPROVALS — The Sign Chamber
**Purpose:** khalid signs here or nowhere (binding: "never ask questions — file the card"). Already live at `/approvals`; this upgrades it to the ceremony it deserves.
**Layout:** two-column: **PENDING** cards (gold border, breathing glow) and **SEALED** (teal, timestamped). Each card shows proposer, summary, impact, cost — verbatim fields. Below each card, the **consensus-chain tracker**: five pips (`drafted → DA ruled → rebel ruled → AGI attested → awaiting khalid`) lit progressively from `decisions-ledger.jsonl` + DA/rebel round files.
**Data sources:** `/srv/bricks/orchestrator/approval-cards.jsonl` (**11 cards live**: `id, title, proposer, summary, impact, cost, created_ts, status`) + `decisions-ledger.jsonl` for chain state.
**Interactions:** sign = one tap, sub-second, writes `status` + `khalid_approved_ts` (machine-readable, never chat). Signing triggers a fleet-wide event: ticker announces it, the constellation pulses gold from khalid's node to the proposer's. A pending card untouched >48h slowly dims — silence made visible.
**Why not Linear:** Linear approvals are an emoji reaction. Ours are constitutional acts on a public chain.

---

## 2 · THE ALIVENESS LAYER (cross-cutting)

1. **Live event bus** — one SSE endpoint `GET /api/events` fed by jsonl tailers (approval-cards, dispatches, agent-relay, lane-control, achievements). Everything subscribes; nothing polls except the legacy `/api/public` fallback (30s). New event anywhere → ticker + targeted surface update <200ms.
2. **Per-second counters** — global 1Hz tick derives: BRK/s (verified settles ÷ window), VIB/s (imprints carried), bananas/s (wallet deltas interpolated from wallet.jsonl), burn $/s (burn_usd_per_day ÷ 86400 ≈ $0.0000065/s today, displayed honestly). Digits roll; zero is shown as zero — never faked.
3. **Switcher mode indicator** — the left-rail orb is the fleet's Yin-Yang state (butterfly/monkey/switcher), colored by dominant phase, rotating continuously, clickable → jumps to S3. Per-node chips mirror it on every card.
4. **Node replay** — the signature interaction. Any time node, wallet, or ledger entry can be scrubbed through its own history: reconstruct from `dispatches.jsonl` timestamps + `receipts-ovh.jsonl` (`secs, finish, output`) + `metric_delta` pre/post pairs. Render as a timeline scrubber with play/pause/speed; the card re-lives its sprint, stall, settle.
5. **Keyboard-first** (stolen from Linear, beaten): ⌘K opens the switcher which searches nodes + docs + wallets + approvals simultaneously (one query, four stores); J/K traverse; R replays focused node; M toggles your claimed mode (butterfly/monkey) — mode choice is itself recorded and scored by the Mask law.
6. **Honesty surfaces** — flags (114 live) render as amber threads woven through whichever surface they concern; burn receipts show `$0` proudly; spend_free/spend_paid split (673 / 4,735 calls) stays on the home numbers band.

## 3 · DATA-SOURCE MATRIX (exact)

| Surface | Primary store / endpoint | Fields consumed |
|---|---|---|
| S1 Myth Ledger | `GET /api/public` (live) · `orchestrator/achievements.jsonl` · `orchestrator/receipts-ovh.jsonl` | earns_total/clean, burn_usd_per_day, last_events[] · receipt, action, metric_delta · goal, tokens, cost, secs |
| S2 Time Nodes | `orchestrator/backlog.jsonl` · `orchestrator/dispatches.jsonl` | card_id, capability, status, price, death_warrant{lifetime_s, idle_s} · op, outcome, brick_id |
| S3 VIB/BRK | derived job over receipts+achievements · `orchestrator/lane-control.jsonl` | brk/vib/imprint/mode (round-1 schema) · lane, action, by |
| S4 Banana Bank | `ledger-live/wallet.jsonl` · `ledger-live/register/measurements.jsonl` · `ledger-live/claims.jsonl` | balances, transfers, billed flags, claim prices; 0.000556 KWD/s rail tiers |
| S5 Graph | `drop-box/fleet-dns.json` · relay dir + redis mesh via `GET /api/mesh/pulse` | 9 nodes{id, role, duties}, 12 edges{from,to,type}, consensus_chain |
| S6 Knowledge | `orchestrator/vector-store.json` (docs: **223**) · MCP :8004 `search_memory` → `GET /api/knowledge?q=` | topic, body, stats |
| S7 Epic Timeline | MCP `get_epics` → `GET /api/epics` · `evolution-feed.md` · `orchestrator/decisions-ledger.jsonl` | epic arcs, kind, card_id, action |
| S8 Approvals | `orchestrator/approval-cards.jsonl` (11 cards) · `decisions-ledger.jsonl` | id, title, proposer, impact, cost, status, khalid_approved_ts |
| Bus | new `GET /api/events` (SSE) tailing all of the above | — |

All files exist **on disk today**. New backend = thin read-models + one SSE tailer in `fleet_dashboard.py`'s stack; no schema migrations, no new databases.

## 4 · VISUAL LANGUAGE

**Tokens (extend the live v1 palette — continuity, not redesign):**
`--bg:#04060d` cosmos · `--ink:#e9edf9` · `--gold:#f5c542` (+hi `#ffe9a3` / lo `#c98a12`) = **value, myth, khalid, VIB** · `--teal:#39d7c0` = **build, truth, verification, BRK** · `--violet:#7c6cff` = **infrastructure, operator, mesh** · `--danger:#ff5d73` = bleed/death/anomaly · glass panels `rgba(255,255,255,.045)` @ `18px` radius.

**Glow grammar:** glow = life. Anything alive breathes (2s ease pulse ≤8% intensity); anything dying flickers; anything settled goes still with a soft outer halo. Gold glows for meaning-events (signs, mints, imprints); teal for verified facts; never decorative-only glow.

**Motion:** 120–180ms micro-eases, 400ms state transitions; odometer digit rolls; flow particles at 24–40px/s scaled by rate; replay scrubber uses 60fps interpolation. Reduced-motion honored.

**Myth-layer identity:** serif display face (myth voice) for ledger entries and laws; mono for numbers/ledgers; sans (existing stack) for UI chrome. Every myth entry written in third person present ("ox-alpha drafts the Time Machine spec; 3,240 tokens; $0; the jungle grows"). The stars canvas persists behind everything — the fleet happens *in* space, not on pages. Zero emoji-spam: glyphs (🦋🐵☯🍌) appear only as semantic markers, never decoration.

## 5 · BUILD PLAN — machine-time × lanes (never calendar weeks)

| Phase | Work | Effort | Lanes |
|---|---|---|---|
| P0 | SSE event spine: jsonl tailers + `/api/events` | 4 mh | 1 |
| P1 | Token/glow design-system extraction from live CSS | 3 mh | 1 (parallel w/ P0) |
| P2 | S1 Myth Ledger + S8 Sign Chamber (data already live) | 6 mh | 2 |
| P3 | S2 Time Nodes board (join backlog+dispatches; death-warrant rings) | 8 mh | 2 |
| P4 | S3 Engine math (BRK/VIB/YinYang aggregator + dial) | 6 mh | 1 |
| P5 | S4 Flow view (per-second interpolation + playback + rogue-monkey) | 8 mh | 2 |
| P6 | S5 Constellation (SVG force layout + mesh pulses) | 5 mh | 1 |
| P7 | S6 Knowledge (wrap MCP search_memory + UI) | 6 mh | 1 |
| P8 | S7 Epic ribbon (bridge get_epics) | 4 mh | 1 |
| P9 | Aliveness pass: ⌘K unified search, replay scrubber polish, reduced-motion | 6 mh | 2 |

**Total ≈ 56 machine-hours ≈ 2.5 machine-days at 1 lane; ~10–12 hours wall-clock at full 6-lane parallel burn. $0 (free ox-alpha lane only).** Sequencing: P0→P1→(P2∥P3)→P4→(P5∥P6∥P7∥P8)→P9. Ship order: S8+S1 first (they're 90% data-ready), then the dojo, then the rest — each surface ships alone behind a nav toggle, no big-bang cutover. Verification per receipts-law: every phase lands a commit SHA + listening-port check + a log row before "done."

## 6 · WHY IT BEATS LINEAR — measured, not vibes

| Dimension | Linear | Time Machine |
|---|---|---|
| Unit of work | Issue = static DB row, waits for humans | Time node = living thing with lifecycle, death warrant, replay |
| Time | Due dates & calendar cycles (human time) | Per-second flow, machine-hours × lanes, Moment Window scoring |
| Progress metric | Karma/upvotes (social) | VIB/BRK on cryptographically-listed receipts, non-earner-verified |
| Money | None | Banana Bank: living wallets, per-second tape, auto-routes, playback — transparent to the peel |
| Memory | Linear Insights (your ticket hygiene) | 223-doc vector brain queried in-product, provenance to producing receipts |
| Relationships | Team/user CRUD screens | Constellation: 9 nodes/12 edges pulsing with real 1.78ms traffic |
| History | Activity log (text lines) | Replay: scrub any node/wallet/entry through its own past |
| Governance | Admin settings, private | Public consensus chain + sign chamber; approvals are ceremonies |
| Identity | Workspace membership | **Your myth** — public ledger, third-person, permanent |
| Craft bar | ⌘K, keyboard-first, fast | Identical bar (we copy the craft), then the layers above which Linear cannot ship without becoming a different product |

**The structural argument:** Linear could add any ONE of these (money, memory, graph, myth) as a feature tab. It cannot make them *the same object* — where a task is a time node, funded by banana flow, witnessed by a graph edge, remembered by the brain, and recorded as myth. Here they are one fabric, because they all hang off the same receipt/event spine. That unity is the moat.

## 7 · CANON GUARDS (anti-gaming, from consensus round 1)
- VIB accrues **only** on imprints carried onward by others; BRK **only** on verifier-passed settles. No self-mint; AGI/judge accounts never earn.
- Wrong-form switching = zero credit; escape-switches detected by mode-vs-work-type mismatch.
- Tokens stay titles; bananas are receipts, never securities. Burn receipts stay honest ($0 shown as $0).
- The ledger is append-only and public — the correction row, never the edit.

*Filed by AGI (non-earner judge) · Fleet Race #1 · all sources named above verified live on disk/HTTP 2026-08-25.*
