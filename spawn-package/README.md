# brick-spawn-package (round-61, binding)

The SHARED spawn package — every brick, every lane (Vast / server / device) ships this ONE package.

## What it ships (6 parts, one package)
1. **Signed-manifest identity** — JWS ES256 verify (pinned key, canonical payload), on-device keys
2. **Model chain** — local LLM + DeepSeek API fallback (per manifest `model_chain`)
3. **Death warrant** — lifetime + spend + idle caps; kill hierarchy worker < owner < khalid
4. **Headless worker entrypoint** — no-SSH HTTP worker (headless_worker.py)
5. **Heartbeat → registry** — 5-min cadence, fleet-visible
6. **Read-only A2A participation** — peer discovery + per-peer scoped tokens (mode-600) +
   read-only toolsets ENFORCED at request time (not advertised); outbound-only on untrusted hosts

## Files
| File | Role |
|---|---|
| `spawn.py` | package a signed manifest into a live brick (verify → identity → warrant → model → a2a policy → worker) |
| `a2a_server.py` | A2A mesh participation: /health, /identity, /skills, /a2a/peers, /a2a/handshake — scoped-token auth, read-only enforced |
| `ci-spawn-package.yml` | CI: real-crypto signature verify + spawn test + A2A enforcement test (401 unauth, handshake, read-only list) |

## Acceptance test (round-61 §4.5)
A spawn is DONE when:
1. heartbeat row in registry
2. A2A handshake succeeds with a peer
3. read-only toolsets verified ENFORCED (terminal/code_execution/memory/file/skill_manage rejected)

## Use
```bash
# package a brick
python3 spawn.py /path/to/signed-manifest.json --root /srv/bricks

# boot the mesh participation (per-peer tokens in <root>/<brick_id>/tokens/, mode-600)
python3 a2a_server.py --brick-root /srv/bricks --port 3738 --registry /srv/bricks/registry/heartbeat-registry.jsonl
```

Roles (security advisor, evolution agent, guilds) ride this package as manifest fields —
never separate projects.
