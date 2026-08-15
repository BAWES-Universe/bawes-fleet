#!/bin/bash
# entrypoint.sh — the brick boots itself, then earns or dies (death warrant).
# Self-sustain rule: the brick only keeps running while it has work that pays.
# Budget gate: if a lifetime or budget cap is set and hit -> flush -> exit.
set -e

echo "[brick] boot: identity ${BRICK_ID} on $(hostname)"

# 1. sync identity + model chain from the mounted ledger (git-native, read-only)
if [ -d /brick/ledger/.git ]; then
  echo "[brick] ledger present — state rides in"
fi

# 2. probe self (known-answer) — an unverified host never takes real work
python3 /brick/spawn-package/probe_self.py --probe probe-001 || {
  echo "[brick] SELF-PROBE FAILED — refusing real work"; exit 1; }

# 3. start the worker (headless job server, grant-authed)
echo "[brick] worker up on :${WORKER_PORT}"
exec python3 /brick/spawn-package/headless_worker.py
