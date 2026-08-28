# ROLLBACK — v14 roles + decision routing (2026-08-25, TS=1787691686)

Shipped by the fleet roles build (2026-08-25). If anything breaks, revert with the
commands below. A second fleet member (any agent with ssh access to 51.75.74.214)
can run these — no special role needed.

## What changed
- users.json: new schema — `role` (owner|decision_maker|contributor|brick_issuer),
  optional `lanes` (decision_maker: studenthub, plugn), optional `discord_id` bind.
  mishari is now decision_maker (lanes studenthub, plugn) — NO LONGER read-only.
- dashboard.py: /api/roles (owner-only grant/revoke + roles-audit.jsonl audit),
  lane-aware approval routing (lane cards -> lane's decision_maker, owner = final
  authority with recorded overrides), /api/approvals/request (notifies the decider
  by name via agent-relay row), roles data in /api/data.
- index.html + approvals.html: Roles & People panel (beat 14) + role-aware
  approvals UI (lane chips, decider names, per-card action buttons).
- gen_user.py: setrole command + --lanes/--discord-id.

## Rollback (exact commands)
TS=1787691686
cd /srv/build/fleet-dashboard
sudo -u ubuntu cp -p dashboard.py.pre-roles-$TS.bak dashboard.py
sudo -u ubuntu cp -p index.html.pre-roles-$TS.bak index.html
sudo -u ubuntu cp -p approvals.html.pre-roles-$TS.bak approvals.html
sudo -u ubuntu cp -p users.json.pre-roles-$TS.bak users.json
sudo -u ubuntu cp -p gen_user.py.pre-roles-$TS.bak gen_user.py
sudo systemctl restart fleet-dashboard

Optional data rollback (approval-cards.jsonl is byte-identical to its backup today;
only restore if test/unknown cards appear):
sudo -u ubuntu cp -p /srv/bricks/orchestrator/approval-cards.jsonl.pre-roles-$TS.bak \
  /srv/bricks/orchestrator/approval-cards.jsonl
# agent-relay + decisions-ledger backups exist too: *.pre-roles-$TS.bak

## Verify after rollback
systemctl is-active fleet-dashboard          # -> active
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3999/healthz   # -> 200
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3999/api/roles # -> 401 (no auth)

## Notes
- roles-audit.jsonl (/srv/build/fleet-dashboard/, 0600, append-only) is NEW — leave it;
  rollback only replaces the 5 files above.
- The Discord developer portal, brick-gateway.py and /srv/vault were NOT touched.
- users.json hashes were NOT changed — khalid/mishari passwords still work after rollback.
