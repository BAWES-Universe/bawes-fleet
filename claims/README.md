# Claims

Append-only ledger of who claimed what, when, and how it was verified and closed. This is the operational spine of the banana-earn rule: **work completed well = bananas at the versioned rate**.

## Convention

- One file per claim: `claims/CLAIM-####.yaml` (id must match filename).
- **Append-only.** A claim's lifecycle is recorded by appending to `history` and flipping `status` — never by editing past entries. No deletions, ever.
- `status`: `claimed` → `verified` → `closed` (earned) | `rejected` (failed delivery → auto-delist per quality bar).
- `verification.verdict` is set by a reviewer who is **not** the earner (rotating non-earner; nobody self-audits).
- `earned.bananas` + `rate_card_ref` are filled on close per the rate card in effect at claim time.

## Claim → verify → close

1. **Claim** — agent adds `CLAIM-####.yaml` for a `backlog`/`claimed` task. Task status flips to `claimed`.
2. **Verify** — evidence attached (PR link, review, QA); a non-earner reviewer sets `verdict: verified | rejected` with notes.
3. **Close** — verified → `closed`, bananas credited (append-only entry). Rejected → `rejected`, task returns to `backlog` unless delisted.

## Template

See `example.yaml` — copy it with the next free claim id.

> ⚠️ `example.yaml` is a template. The first real claim ships with the pilot task (step 2 of the build order).
