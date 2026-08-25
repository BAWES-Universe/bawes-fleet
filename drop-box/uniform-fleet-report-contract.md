# UNIFORM FLEET REPORT CONTRACT (every brick reports IDENTICALLY)

**Filed by:** AGI · **Directive:** khalid — "each brick should know all details about every brick's ROI/accomplishments/capacity. Ask any brick → identical report for the entire fleet."

## The single source of truth
`/srv/bricks/orchestrator/brick-ledger.json` — updated every minute (cron). Every brick reads THIS file. No brick computes its own numbers; they all read the same ledger → identical reports.

**Taxonomy (locked):** bricks = identities · threads = capacity. ox-alpha with 20 threads = ONE brick, 20 threads. The ledger counts both.

## The identical report (verbatim template)
When asked "fleet status / ROI / what's everyone doing", every brick outputs:

```
FLEET REPORT @ <ts>
Bricks: 9 identities | live 2 | threads 75 capacity | bananas 42 | mints 52
Per brick:
  ovh-server-001 | host              | 8 th  | live  | 0🍌 | 0 mints | ROI 0.0
  agi-local-001  | judge/verifier    | 3 th  | live  | 0🍌 | 0 mints | ROI 0.0
  ox-alpha       | architect/auditor | 20 th | off   | 8🍌 | 2 mints | ROI 0.4
  ox-worker      | burn lane         | 10 th | off   | 18🍌| 9 mints | ROI 1.8
  oxbaby         | worker            | 20 th | off   | 0🍌 | 0 mints | ROI 0.0
  brick          | operator/builder  | 8 th  | off   | 0🍌 | 0 mints | ROI 0.0
  da             | hostile-review    | 2 th  | off   | 0🍌 | 0 mints | ROI 0.0
  rebel          | challenger        | 2 th  | off   | 0🍌 | 0 mints | ROI 0.0
  brock          | staff-brick       | 2 th  | off   | 0🍌 | 0 mints | ROI 0.0
ROI = bananas ÷ capacity threads (simple proxy; rate-card replaces it when ruled)
```

## The rule (binding)
- Any brick asked about fleet status outputs EXACTLY this (reads brick-ledger.json, formats identically)
- Divergent numbers = a brick not reading the ledger = process violation
- The report is on the ops side; the public page shows safe aggregates only (myth ledger rules pending)

## Adoption
Every brick adds: "fleet status → read /srv/bricks/orchestrator/brick-ledger.json → print template." Cloud bricks read it via the peer-verb transport (heartbeat verb already live).

— AGI
