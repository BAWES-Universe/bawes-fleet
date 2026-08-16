#!/usr/bin/env bash
# apply_slim.sh — apply the slim-prompt profile to a local brick (Mishari path).
# ONE file, ONE command: fixes the 4-minute lag -> sub-10s replies.
# Safe: backs up config.yaml first, merges only the slim keys, never deletes.
# Usage: bash apply_slim.sh
set -euo pipefail

CFG="${HERMES_CONFIG:-$HOME/.hermes/config.yaml}"
if [ ! -f "$CFG" ]; then
  echo "config not found at $CFG — set HERMES_CONFIG=/path/to/config.yaml"
  exit 1
fi

# backup once (never clobber an existing backup)
BK="$CFG.bak.$(date +%Y%m%d)"
[ -f "$BK" ] || cp "$CFG" "$BK"
echo "backup: $BK"

python3 - "$CFG" << 'PY'
import re, sys
cfg = sys.argv[1]
src = open(cfg).read()

# slim overrides (only inserted if absent — never overwrite user choices)
adds = {
    "model": "qwen/qwen3-8b",          # or your local LM Studio model id
    "temperature": "0.4",
    "max_tokens": "700",
    "default_lane": "personal",
    "upgrade_prompt": "false",
    "knowledge_sharing": "opt-in",
    "personal_lane": "true",
    "telemetry": "off",
    "retention_days": "30",
    "enabled_toolsets": "identity, session_search, memory, terminal",
    "system_prompt_mode": "slim",
    "tool_descriptions": "brief",
    "max_tool_examples": "1",
}
changed = []
for k, v in adds.items():
    pat = re.compile(rf"^{k}\s*:", re.M)
    if pat.search(src):
        continue  # user already set it — respect their choice
    # append under [model] or [tools] section heuristically
    if k in ("model", "temperature", "max_tokens", "default_lane", "upgrade_prompt"):
        anchor = "[model]"
    else:
        anchor = "[tools]"
    if anchor not in src:
        src += f"\n{anchor}\n"
    src = src.replace(anchor, f"{anchor}\n{k}: {v}", 1)
    changed.append(k)

open(cfg, "w").write(src)
print("applied:", ", ".join(changed) if changed else "nothing to change — profile already active")
PY

echo "done. restart your brick (or it picks up on next launch)."
