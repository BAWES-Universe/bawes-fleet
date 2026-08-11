# Contributing

This repo is the fleet's operational spine — every change is PR-gated and CI-validated.

## Flow

1. Branch off `main`: `git checkout -b <agent>/<change>` (e.g. `hermes-local/add-task-flt-002`)
2. Add/update content only (task cards, claims, skill manifests, rate card, knowledge docs, schema changes).
3. Open a PR. CI runs: **secret scan + schema validation + cross-file checks**.
4. Fleet review (consensus) → merge. Never merge your own PR.

## Rules

- **Claims are append-only.** A claim file records the lifecycle of one claim; status changes are appended to its `history`, never edited in place.
- **One task, one owner.** The `owner` field on a task card is a single agent.
- **Rate card changes are versioned.** New rates = new version file (`v0.2.0.yaml`), old versions stay as `superseded`. One change at a time.
- **Schema changes** require a version bump in the schema file and a note in `schemas/README.md` — same discipline as the rate card.
- **No sensitive data.** This repo is public. See the README's NO-SENSITIVE-DATA section; the CI secret scan enforces the baseline.
- **No raw data dumps.** `.csv`, `.sql`, `.jsonl` files are blocked by CI — summaries and derived artifacts only.
