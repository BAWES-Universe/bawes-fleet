# BAWES Fleet Dashboard v3 — OVH box :3999

BAWES-branded fleet command dashboard. Login page + HMAC session auth on every
path (no browser basic-auth popup). Auto-refresh 30s. **Real data only** —
every number comes from a file or API on the box; anything not measurable is
labelled "not yet instrumented".

## Access
- URL: http://51.75.74.214:3999/ (sign in at /login — see README-AUTH.md, 0600)
- Also served at https://fleet.bawes.net (Caddy)
- API: GET /api/data (session cookie required) — full JSON payload
- Health: GET /healthz (session required too — no open unauthenticated access)

## Service
- systemd: `fleet-dashboard.service` (User=ubuntu, Restart=always)
- Deploy: `systemctl restart fleet-dashboard` after replacing files
- Logs: `journalctl -u fleet-dashboard -n 50`

## Data sources (all real, all on the box unless noted)
| Section | Source |
|---|---|
| Money — metered spend | /srv/door/state/door-cost.jsonl (deepseek-flash $0.002/call rows) |
| Money — balances | /srv/fleet-state/register/spend.jsonl (daily snapshots, control-host cron; box copy synced 2026-08-24 — **auto-sync not yet wired, will go stale**) |
| Money — rails | /srv/vault/openrouter.env (ox free key), /srv/vault/nous.env (paid Nous key, control host only), no GLM key on box |
| Bricks — live | /srv/bricks/registry/heartbeat-registry.jsonl (LIVE = ≤5 min, IDLE = ≤7d, SILENT = >7d; incremental tail read) |
| Bricks — registered | /srv/bricks/register/registry.jsonl |
| Wallet / ROI | /srv/bricks/register/wallet.jsonl (earn/credit/founder-seed/dock rows; contested earns excluded from clean ROI) |
| Evolution | vector-store.json per-doc ts, wallet earn ts, GitHub merged_at, spend.jsonl balances, door-cost per day |
| Threads | /home/ubuntu/.hermes/profiles/door/state.db (read-only), gateway_state.json (stale), /proc fleet process scan; spec = Nous Hermes Cloud 8 vCPU/4 GB/20 sessions ≈ $1.09/day |
| Velocity | GitHub API (PAT /srv/vault/github-hearth.pat) — BAWES-Universe/hearth pulls |
| Epics | /srv/bricks/orchestrator/shared-work-queue.md |

## Auth (v3 — login page + session cookie)
- Sign in at /login (username + password). Session cookie `bawes_session`
  (HMAC-signed, 12h, HttpOnly, SameSite=Lax) — secret in session.key (0600).
- Users in users.json (0600): scrypt-hashed passwords, roles `owner` (full
  access incl. approval actions) / `contributor` (read-only).
- Manage users: `python3 /srv/build/fleet-dashboard/gen_user.py add|remove|change|list`
  (add khalid --role owner / add mishari --role contributor, etc.). No restart
  needed — users.json is read per request.
- No open unauthenticated access: HTML routes 302 to /login, /api/* return 401.
- No WWW-Authenticate header anywhere — the browser popup is gone.

## Honest gaps (shown on the dashboard)
- ox/stealth free-tier burn not metered per-model on the box.
- Nous paid usage not instrumented on the box (key lives on control host).
- OVH VPS invoice cost not derivable from box files.
- True concurrent-session count on the Hermes Cloud instance not instrumented
  (cloud MCP needs OAuth browser round-trip the headless box can't complete).
- spend.jsonl box copy is a one-time sync — wire rsync/cron for freshness.
