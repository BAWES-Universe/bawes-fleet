#!/usr/bin/env bash
# apply_slim.sh v3 — per-platform slim (Mishari-corrected).
# v2 broke A2A: agent.disabled_toolsets is GLOBAL (removes web from the
# signed A2A surface {web, vision, session_search}). v3 uses the ONLY
# per-platform lever: platform_toolsets.discord — Discord surface trims
# WITHOUT touching A2A or any other platform.
# Honest ceiling (measured on real 0.20.1, probe_slim2.py):
#   baseline 14,342 -> slim-discord 12,533 (~13%) -> minimal-owner 9,075 (~37%)
# The ~2K target is NOT reachable via config — core tools never defer.
# It needs the BROKER tool (design committed, build next). v3 ships the
# per-platform trim + keeps A2A intact; broker lands separately.

set -euo pipefail

CFG="${HERMES_CONFIG:-$HOME/.hermes/config.yaml}"
BAK="${CFG}.bak-$(date +%s)"

if [ ! -f "$CFG" ]; then
  echo "ERROR: no config at $CFG"; exit 1
fi

cp "$CFG" "$BAK"
echo "backup: $BAK"

python3 - "$CFG" << 'PYEOF'
import sys, yaml
path = sys.argv[1]
cfg = yaml.safe_load(open(path)) or {}

# PER-PLATFORM, discord only. A2A surface {web, vision, session_search}
# is configured separately and is NOT touched by platform_toolsets.
pt = cfg.setdefault("platform_toolsets", {})
pt["discord"] = [
    # A2A tools stay for the signed peer surface
    "web", "vision", "session_search",
    # owner-facing core (capability-preserving — NEVER stripped)
    "terminal", "file", "skills", "delegation", "clarify", "todo", "memory",
    # slim surface for a local brick: NO browser/tts/image/video/bfl/code_exec
]

# CRITICAL: remove any GLOBAL agent.disabled_toolsets that v2 may have
# written — it was the A2A breaker.
if "agent" in cfg and "disabled_toolsets" in cfg["agent"]:
    del cfg["agent"]["disabled_toolsets"]
    print("removed GLOBAL agent.disabled_toolsets (was breaking A2A)")

with open(path, "w") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
print("platform_toolsets.discord set (per-platform, A2A intact)")
print("A2A {web, vision, session_search} untouched — signed surface preserved")
print("NOTE: measured ceiling ~9K tokens. The ~2K broker tool is the next build.")
PYEOF

echo "OK — restart the gateway from an OUTSIDE shell: hermes gateway restart"
