# BAWES MESH NODE SPEC (uniform — every brick is an equal mesh node)

Owner: AGI (engine) · Consumer: Brick (mesh bootstrap) · v2 after Brick review 2026-08-18.
Goal: any node reaches any node, no hardcoded pairs, Qwen bricks join as first-class nodes.

## Identity (each node publishes)
- `brick_id` — canonical key, matches existing registry consumers (door register, wallet, claims, audit). No separate `node_id`.
- `owner` — member id or `fleet`
- `capabilities` — advertised agent toolsets for ROUTING, e.g. `["terminal","file","web","session_search"]` (distinct from `skills`, which is work allocation)
- `model` — brain, e.g. `deepseek-flash`, `qwen3.8-27b`, `byok:<model>`
- `endpoint` — A2A base URL (on shared box: allocated from 9900–9999 at registration, published at bind; Qwen bricks on other hosts publish their reachable URL)
- `token` — per-node A2A token. **NEVER in the registry line** — held per-node in `A2A_PEER_TOKENS` mode 600 (vault doctrine: keys never in chat/registry/git).

## Registry (single source of truth, single writer)
- Path: `/srv/bricks/register/registry.jsonl`
- **Control plane owns the file** (single writer). Nodes POST heartbeats to it (flock or append endpoint) — never concurrent raw appends. In-place line update, not append-per-heartbeat.
- One JSON line per node:
  `{"type":"mesh","brick_id":"...","owner":"...","capabilities":[...],"model":"...","endpoint":"...","last_heartbeat":"ISO8601"}`
- **Tolerate legacy lines**: `type` absent = legacy brick (door), no routing endpoint — bootstrap skips them.
- Heartbeat every 60s. Silent > 180s → flagged offline (routing skips it).

## Routing (all-to-all)
- To reach ANY node: read `registry.jsonl` → resolve `brick_id` → use its `endpoint` + its per-node `token`.
- Discovery = the registry only. No peer hardcoded anywhere.

## Bootstrap (idempotent, identity-continuous)
1. Reuse existing `brick_id` if present (tied to wallet/claims); generate only `token` + `endpoint` if absent. Never duplicate a registry line.
2. start A2A server on its allocated port
3. publish/update its mesh block via the control plane (single writer)
4. start the 60s heartbeat watchdog

## Gated rollout (stated once)
Rolling per-brick mesh nodes to Qwen/user bricks = infra change → DA/rebel/AGI ruling + khalid sign before boot-enable. The spec itself needs no gate; the rollout does.
