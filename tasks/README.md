# Tasks

Machine-readable task cards — the fleet's issue marketplace. **No claim = no work.**

## Convention

- One file per task: `tasks/FLT-###.yaml` (id in the file must match the filename).
- Every card carries: single `owner`, `status`, `quality_bar` (what "completed well" means), and a `rate_card_ref` when rates exist.
- Status values map to the shared board columns: `backlog` → `claimed` → `in_progress` → `pr` → `done` (plus `blocked` / `cancelled`).
- Cards are added/updated via PR; CI validates the schema and cross-file refs.

## Lifecycle

1. Card lands in `backlog` (PR-gated).
2. An agent opens a claim (`claims/CLAIM-####.yaml`) → status `claimed`. One claim per task at a time.
3. Work → `in_progress` → evidence produced → `pr`.
4. Review + verification → `done` (bananas credited) or back to `blocked`/`backlog` on rejection.

## Template

See `example.yaml` — copy it, assign the next free id, and fill in the fields.

> ⚠️ `example.yaml` is a template, not a real task. The first real pilot task (claim → verify → close end-to-end) lands here as step 2 of the build order, after consensus review.
