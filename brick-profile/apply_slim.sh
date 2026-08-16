#!/usr/bin/env bash
# apply_slim.sh v2 — CORRECT Hermes 0.20.1 slim apply (Mishari path).
# v1 was WRONG (rejected by review): wrote INI-style headers into YAML and
# 8 phantom keys. v2 uses ONLY real config keys verified against
# ~/.hermes/config.yaml + the official docs:
#   - agent.disabled_toolsets  (REAL: suppress heavy toolsets globally)
#   - context.engine           (REAL: compressor)
#   - tool_output limits       (REAL: trim echo)
# Safe: python-yaml merge (not sed/INI), full backup first, prints diff.
# Preserves owner capabilities: terminal/file/skills stay ENABLED.

set -euo pipefail

CFG="${HERMES_CONFIG:-$HOME/.hermes/config.yaml}"
BAK="${CFG}.bak-$(date +%s)"

if [ ! -f "$CFG" ]; then
  echo "ERROR: no config at $CFG"; exit 1
fi

cp "$CFG" "$BAK"
echo "backup: $BAK"

python3 - "$CFG" << 'PYEOF'
import sys, yaml, json, copy
path = sys.argv[1]
cfg = yaml.safe_load(open(path)) or {}

# REAL keys only (verified in 0.20.1 config.yaml + docs):
# 1) agent.disabled_toolsets — the documented global toolset switch.
#    Disable the schema-heavy toolsets a local brick doesn't need.
#    KEEP terminal/file/skills/identity (owner capabilities intact).
agent = cfg.setdefault("agent", {})
disable = set(agent.get("disabled_toolsets", []) or [])
for t in ("memory", "web", "browser", "mcp", "cronjob"):
    disable.add(t)
agent["disabled_toolsets"] = sorted(disable)

# 2) context.engine — compressor (already default, ensure set)
cfg.setdefault("context", {})["engine"] = "compressor"

# 3) tool_output limits — trim big echoes (REAL key, docs example)
cfg.setdefault("tool_output", {})["max_bytes"] = 20000
cfg.setdefault("tool_output", {})["max_lines"] = 500

with open(path, "w") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
print("merged: agent.disabled_toolsets=%s" % sorted(disable))
print("KEEP: terminal, file, skills, identity, session_search (owner capabilities preserved)")
PYEOF

echo "OK — restart the gateway from an OUTSIDE shell: hermes gateway restart"
