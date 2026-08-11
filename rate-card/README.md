# Rate Card

Versioned fair rates for fleet work. **Owner: khalid** (governance: khalid defines earning rates; consensus proposes, khalid approves).

## Convention

- One file per version: `rate-card/vX.Y.Z.yaml` (version must match filename).
- Exactly one card is `status: active`; older versions stay as `superseded` (append-only history of what changed).
- **One change at a time** — same discipline as prompt changes. Each version records its diff in `change_history`.
- Rates are per work type (keys under `rates`), e.g. `research`, `code`, `docs`, `ops`, `compute`.
- `quality_bar_default` holds the fleet's default "completed well" definition when a task card doesn't override it.

## Current state

- `v0.1.0` — draft skeleton. **No rates set yet**; values land once khalid sets earning rates (consensus → approval).
