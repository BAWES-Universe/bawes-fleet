# BAWES Fleet Dashboard — Approvals (khalid's sign page)

URL: **http://51.75.74.214:3999/approvals** (same basic auth as the dashboard:
user `khalid` — password in `README-AUTH.md`, mode 600)

## What it is

A phone-first page listing DECISION CARDS waiting for khalid's sign. Each card shows:

- **Title** — what is being decided
- **Proposer** — AGI / Brick / ox-alpha / oxbaby
- **Summary** — what the card asks
- **What changes if approved** — impact
- **Cost** — if any
- **Created** — date the card was opened
- **Status** — `PENDING` · `APPROVED` · `REJECTED` · `NEEDS-FEEDBACK`

## How khalid uses it (from the phone)

1. Open `http://51.75.74.214:3999/approvals` in Safari/Chrome; log in with the
   dashboard credentials (browser remembers them).
2. Every card awaiting your sign has three big buttons:
   - **✓ APPROVE** — signs the card. Writes `status=approved` + `khalid-approved-ts`
     to the card's JSONL row AND appends a row to the decisions ledger.
   - **✕ REJECT** — writes `status=rejected` (+ `khalid-rejected-ts`).
   - **💬 FEEDBACK** — opens a text box; your comment is appended to the card
     (`status=needs-feedback`). The fleet answers, then the card returns to PENDING.
3. The header pill shows how many cards are waiting (also shown on the main dashboard
   header — click it to jump here). The page auto-refreshes every 20 s.

## Data files (all real, all append-only)

| File | Role |
|---|---|
| `/srv/bricks/orchestrator/approval-cards.jsonl` | the cards. One JSON object per line with fields `id · title · proposer · summary · impact · cost · created_ts · status · feedback`. Every action **appends a new row** for the same `id` (latest row wins) — full history, no silent edits. |
| `/srv/bricks/orchestrator/decisions-ledger.jsonl` | local append-only row per khalid action (`kind=khalid-decision`, card_id, action, ts, source) — **authoritative ledger for dashboard actions**, always lands. GitHub sync failures are also recorded here (`kind=gh-ledger-sync-failed`). |
| `BAWES-Universe/bawes-knowledge` → `decisions/ledger.md` | the **canonical fleet decisions ledger** (GitHub). Each action attempts to append a table row (`✅ approved` / `❌ rejected` / `💬 feedback given`). **Status 2026-08-24: blocked** — the box's `github-hearth.pat` is hearth-scoped and read-only on `bawes-knowledge` (PUT → `403 Resource not accessible by personal access token`). The action always lands locally first; to activate the sync, vault a PAT with **Contents: read/write** on `BAWES-Universe/bawes-knowledge` and the next action will use it. |

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/approvals` | the page (basic auth) |
| GET | `/api/approvals` | cards JSON: `{cards[], pending_count, note}` |
| POST | `/api/approvals/action` | body `{"id": "<card-id>", "action": "approve\|reject\|feedback", "feedback": "..."}` → 200 `{ok:true, card, decision_row, gh_sync}` or 409 `{ok:false, error}` |
| GET | `/api/data` | main dashboard payload — now includes `approvals.pending_count` (header badge) |

Actions are only allowed on undecided cards (`PENDING` / `NEEDS-FEEDBACK`); feedback just
appends your comment. A card that is `APPROVED` or `REJECTED` is terminal — it can never be
re-decided (append-only, no silent edits).

## Adding a card (fleet agents)

Append one JSON line to `/srv/bricks/orchestrator/approval-cards.jsonl`:

```json
{"id":"my-card-2026-08-24","title":"Short title","proposer":"AGI","summary":"what is asked",
 "impact":"what changes if approved","cost":"$0 or $X/day","created_ts":"2026-08-24T00:00:00Z",
 "status":"PENDING","feedback":[]}
```

Never edit or delete existing rows — append only. The dashboard picks it up on next refresh.

## Verification (deploy checklist)

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3999/approvals                    # 401
curl -s -u khalid:'<pw>' http://127.0.0.1:3999/approvals -o /dev/null -w "%{http_code}\n"     # 200
curl -s -u khalid:'<pw>' http://127.0.0.1:3999/api/approvals | python3 -m json.tool           # cards + pending_count
curl -s -u khalid:'<pw>' -X POST http://127.0.0.1:3999/api/approvals/action \
  -H 'Content-Type: application/json' -d '{"id":"<id>","action":"approve"}'                  # 200 ok:true
tail -2 /srv/bricks/orchestrator/approval-cards.jsonl                                        # new row, status APPROVED
tail -1 /srv/bricks/orchestrator/decisions-ledger.jsonl                                      # khalid-decision row
# GitHub canonical ledger:
curl -s https://raw.githubusercontent.com/BAWES-Universe/bawes-knowledge/main/decisions/ledger.md | tail -3
```

## Current seeded cards (2026-08-24)

1. `nous-lane-policy-2026-08-24` — Nous lane policy sign ($5/day cap, operator-only) — proposer AGI
2. `rate-card-v010-approval` — Rate card v0.1.0 approval — proposer AGI
3. `oxalpha-a2a-wiring-2026-08-24` — OxBaby/ox-alpha A2A wiring approval (scoped key already deployed) — proposer ox-alpha
