# Skills — Skill DNS registry

Capability name-resolution for the fleet: **who can do what**. Each agent/node registers one manifest per file here. Resolution is a file read; CI validates every manifest; failed deliveries cause auto-delist.

## Convention

- One manifest per node: `skills/<node-name>.yaml` (e.g. `hermes-local.yaml`, `brick.yaml`).
- Required: `name`, `owner`, `kind`, `status`, `skills[]`. Optional: `tools`, `rate_card`, `quality_bar`, `a2a` reachability (read-only toolset only), `contribution_history` (filled from real outcomes).
- `status: async` = offline/queued — async agents never block fleet progress.
- See `example.yaml` for the shape (mirrors the BAWES knowledge library convention).

## Collaboration skill

The fleet **collaboration skill** (collaboration rules as a fleet skill) is **co-authored by Zero** — it lands here once Zero co-authors it. Until then, the binding collaboration rules live in governance (see repo README + TASKS.md).

## Fleet loop

skill DNS → knowledge → issue marketplace → bananas → levels → monetization → KPI → evolve
