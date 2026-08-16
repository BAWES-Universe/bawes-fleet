# CONSENSUS — DOOR INGEST (round-121, 2026-08-16)
# Khalid: build the auth popup for staff credentials. Built + deployed.
# AGI: CONFIRMED with 5 hardening adds. DA + Rebel: running in parallel.

## BUILT + LIVE
- /srv/door/door_ingest.py, service door-ingest on 127.0.0.1:3744 (systemd, active)
- One-time per-person URL minted after door consent
- Paste-once page, BURNS on first open (second open 404 — verified live)
- POST /put -> vault store DIRECTLY (0600, fail-closed)
- Keys never touch chat / agent context / logs (no request logging)
- Services: openrouter, deepseek, higgfield, gemini, anthropic, openai
- Live-cycle proven: mint -> open(200, burns) -> put(sha) -> second open(404)

## AGI'S 5 HARDENING ADDS (pending)
1. Custody hash receipt linking key to door-consent
2. Provider-side validation call on ingest
3. Explicit revocation/rotation path
4. Parent-dir perms + sticky-bit check
5. Alert on any second-open 404 attempt

## WHO GETS WHAT
- khalid: minted after HIS door consent (citizen #1)
- Chahd: minted after her door consent (citizen #2)
- Mishari: same surface for local AND cloud brick creds
- Staff: same surface, per-person, scoped per service

## STANDING RULES
- Keys NEVER through chat — the ingest URL is the only door
- One-time, auto-destroy — a burned token is a burned token
- Vault-direct write only, 0600, fail-closed
- Zero homework: one tap + one paste, then the vault holds it
