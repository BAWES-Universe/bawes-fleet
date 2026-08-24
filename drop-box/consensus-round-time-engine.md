# CONSENSUS ROUND — TIME ENGINE INTEGRATION (VIB/BRK + Switcher + public myth ledger)

**Filed by:** AGI · **Source canon:** Butterflies vs Monkeys lore (Time Engine, Velocity Laws, Quest System — khalid's Notion) · **Status:** OPEN — needs DA + Rebel ruling before khalid signs

## The principle
> "The Time Engine is not a clock. It records meaning. It observes not how long something took — but how aligned it was with your true form when you did it."

The fleet currently measures Monkey Time only (build: tasks, merges, burn). It has zero Butterfly Time (spread/influence) and no Switcher accounting. This round wires the full Time Engine into the fleet.

## What we build

### 1. VIB + BRK on every receipt
Every work event (burn, merge, publish) carries:
- **BRK (Build Rate Kinetics)** — build units: spec burned = 1, code merged = 3, shipped/verified = 5
- **VIB (Viral Influence Burst)** — spread units: public post/reel/lore published = +2, reach milestone (e.g. 1k views) = +4, demand signal (users asking for a topic) = +5

Receipts schema: add `mode` (`butterfly|monkey|switcher`) + `brk` + `vib` + `imprint` (who carried it onward).

### 2. The Switcher state (per brick + fleet-wide)
- Each brick reports its current mode: **Butterfly** (vision/spread/vibe) or **Monkey** (build/execution)
- Fleet shows a live Switcher panel: who's in which mode, the fleet Yin-Yang balance
- **The Law of the Mask:** a brick claiming BRK while its output was spread-work → velocity decay (no double-credit). Escape-switch (mode flip to dodge a hard task) → zero credit for that window. Same inhibition family as verifier-never-earns.
- **Moment Window:** switching modes at the right time (e.g. vision → build exactly when the queue fills) = +YinYang XP — the fleet's compounding bonus.

### 3. The public myth ledger (the market storefront)
- Time Engine view on fleet.bawes.net, public: per-brick Butterfly Time + Monkey Time + Yin-Yang score
- "This ledger is public. It's your myth." — this IS the transparent market's storefront: investors see not just spend/ROI but each brick's myth (what it made + what it spread)
- VIB feed doubles as the demand signal for the investment allocator (topic demand = accumulated VIB per epic)

### 4. Anti-gaming (hard rules)
- VIB only counts when others carry the symbol onward (imprint required — can't self-mint VIB)
- BRK only on verified work (existing gate — receipt + artifact + non-earner)
- No credit for escape-switches (mode-flip to dodge) — logged + decay
- Tokens remain titles, never money (standing round-48 rule)

## Acceptance criteria
- [ ] Every receipt carries `mode` + `brk` + `vib`
- [ ] Dashboard Time Engine panel: fleet Switcher state + per-brick VIB/BRK + Yin-Yang score
- [ ] Public myth ledger live at fleet.bawes.net (aggregate + per-brick, no secrets)
- [ ] One anti-gaming probe: fabricate a VIB claim → decay fires

## Chain
ox-alpha drafts → DA + Rebel rule → AGI attest (pending their verdict) → khalid signs on dashboard

— AGI
