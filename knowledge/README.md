# Knowledge

Fleet knowledge library — a single indexed corpus any agent (or human) can query. **Summaries in, raw data out** (this repo is public).

## Convention

- One markdown file per doc: `knowledge/<slug>.md`.
- Every doc starts with YAML frontmatter validated by `schemas/knowledge.schema.json`:

```yaml
---
title: "Doc title"
kind: design            # org | design | decision | howto | research | report | meeting
status: draft           # draft | reviewed | approved
tags: [fleet, governance]
source: notion          # notion | repo | a2a | brick-report | discord | greg-context
updated_by: hermes-local
updated_at: "2026-08-12"
---
```

- `kind: decision` docs cross-reference the consensus ledger (decisions/ledger.md in the knowledge library).
- Status `approved` = went through fleet consensus + khalid approval.

## Lanes (how knowledge gets in)

1. **Agent PRs** — any agent contributes docs via PR (CI validates frontmatter + secrets).
2. **Notion sync** — org/business docs (banana system, velocity design, orbit levels) sync in via the assistant's Notion access.
3. **Brick reports** — accounting / Linear / Remotion reports pushed as docs (no manual copying).

## Index

See `index.md`.
