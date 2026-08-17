# ROUND-95 — CORRECTED SCOPE: Discord access + action + automation (not archive-first)

thread: bawes-zeus-001 · khalid correction: the goal is ACTIVE engagement, not archiving.

## khalid's words (binding)
"The goal is to have you guys able to access the discord and take action and capture lost ppl there with automations. Don't make me go back and forth for different functionalities."

## What we got wrong
Round-93/94 framed it as ARCHIVE-first (S1 archive → study → PostHog → adaptive). That's backwards.
Archive is a BYPRODUCT of access, not the mission.

## Corrected scope — one capability, not 6 stages
**Access + Act + Automate**, one bot set, one sign:

1. **ACCESS** — bot reads channels + sees members (Message Content + Read History intents; hashed member ids, V-5).
2. **ACT** — bot responds in channels + DMs: answer questions, route to the right channel/human, close the loop. (AGI drafts, operator posts, or bot posts under caps.)
3. **AUTOMATE — capture lost people:**
   - **Join → welcome + route** (new member is caught the moment they land, routed to their interest before they drift).
   - **Inactivity → re-engage** (member going quiet N days → automated check-in/nudge before they churn).
   - **Question/issue → triage** (unanswered = escalation, never dropped).
4. **RETENTION metric (the number that matters):** `captured = went-quiet → re-engaged → active again`. `lost = went-quiet → no response`. The bot exists to shrink "lost."

## Archive demoted to byproduct
Whatever the bot reads, it already has → durable store (hashed, append-only). No separate "archive stage."

## One honest guard that stays (not a separate approval)
- Raw member content → **AGI study/brain** stays consent-gated (V-5: member's own words). This does NOT block the bot acting — welcome/respond/re-engage is standard server-bot operation.
- Unsolicited DM re-engagement: opt-in or member-initiated only (Discord anti-spam + consent). Welcome/channel nudge is always fine.

## What khalid does (once, not back-and-forth)
1. Create the bot → enable Message Content + Read History + Send Messages → invite (Universe, then Banana Bank).
2. Vault the token (mode-600). Scoped PATs for anything else, per round-94.
3. Sign this ONE scope.

## Sent to Brick for consensus
- Brick: your S1 archive bot + setup guide are still correct — reframe the mission to ACCESS+ACT+AUTOMATE; archive is the byproduct. Respond with your agreement or amendment on the shared surface.
