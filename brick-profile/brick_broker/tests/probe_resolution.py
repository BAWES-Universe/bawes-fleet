#!/usr/bin/env python3
"""Empirical resolution probe: what does the model-facing discord surface look
like on exact Hermes 0.20.1 with the broker toolset wired?

Runs against the exact 0.20.1 source (PYTHONPATH=/tmp/hermes-0201).
Read-only: mutates nothing, imports the tools_config machinery directly.
"""
import json, os, sys

sys.path.insert(0, os.environ.get("HERMES_SRC", "/tmp/hermes-0201"))
os.environ.setdefault("HERMES_CONFIG_PATH", "/tmp/brock-broker/brick-profile/brick_broker/tests/fake_config.yaml")

from hermes_cli.tools_config import _get_platform_tools, CONFIGURABLE_TOOLSETS
from toolsets import _HERMES_CORE_TOOLS
from tools.registry import registry
from model_tools import get_tool_definitions

def fake_check_fn_ok(name):
    def _cf(*a, **k):
        return {"ok": True, "available": True}
    return _cf

# Register the broker's three tools exactly as the plugin would (same seam:
# registry.register, toolset=brick_broker).
for tname in ("brick_capability_search", "brick_capability_describe", "brick_capability_invoke"):
    if not registry.get_entry(tname):
        registry.register(
            name=tname,
            toolset="brick_broker",
            schema={
                "name": tname,
                "description": f"Broker tool {tname}",
                "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
            },
            handler=lambda args, **kw: json.dumps({"ok": True}),
            check_fn=fake_check_fn_ok(tname),
            description=f"Broker tool {tname}",
        )

def build_config(discord_list):
    return {
        "platform_toolsets": {
            "discord": discord_list,
            "a2a": ["web", "vision", "session_search"],
        },
        "known_builtin_toolsets": {"discord": ["bfl"], "a2a": ["bfl"]},
        "agent": {"disabled_toolsets": ["kanban"]},
        "tools": {"tool_search": {"enabled": "off"}},
    }

def surface(label, cfg, platform="discord"):
    toolsets = _get_platform_tools(cfg, platform)
    defs = get_tool_definitions(
        enabled_toolsets=sorted(toolsets),
        disabled_toolsets=cfg.get("agent", {}).get("disabled_toolsets"),
        quiet_mode=True,
        skip_tool_search_assembly=True,
    )
    tokens = sum(len(json.dumps(d)) // 4 for d in defs)
    names = [d.get("function", {}).get("name", "?") for d in defs]
    return toolsets, tokens, names

# ---- BASELINE: no broker, default discord composite ----
base_cfg = build_config(None)
ts_b, tok_b, names_b = surface("baseline", base_cfg)
print("== BASELINE discord (composite, no broker) ==")
print(f"toolsets({len(ts_b)}): {sorted(ts_b)}")
print(f"tool-def tokens: {tok_b}")
print(f"tools({len(names_b)}): {names_b}")

# ---- BROKER: explicit slim list, with built-in configurable key to flip explicit mode ----
broker_cfg = build_config(["brick_broker", "clarify", "todo"])
ts_k, tok_k, names_k = surface("broker", broker_cfg)
print("\n== BROKER discord (explicit [brick_broker, clarify, todo]) ==")
print(f"toolsets({len(ts_k)}): {sorted(ts_k)}")
print(f"tool-def tokens: {tok_k}")
print(f"tools({len(names_k)}): {names_k}")

# ---- A2A must stay exact ----
ts_a2a = _get_platform_tools(broker_cfg, "a2a")
print("\n== A2A toolsets ==")
print(f"{sorted(ts_a2a)}  (must be exactly ['session_search', 'vision', 'web'])")

# ---- Broker catalog: full baseline surface via get_tool_definitions ----
catalog_defs = get_tool_definitions(
    enabled_toolsets=sorted(ts_b),
    disabled_toolsets=["kanban"],
    quiet_mode=True,
    skip_tool_search_assembly=True,
)
catalog_names = sorted(d.get("function", {}).get("name") for d in catalog_defs)
print("\n== Broker catalog (baseline surface) ==")
print(f"tools({len(catalog_names)}): {catalog_names}")

# Fail-closed invariant: every broker-visible tool must be in the catalog.
broker_only = set(names_k) - {"brick_capability_search", "brick_capability_describe", "brick_capability_invoke"}
print("\n== Invariants ==")
print(f"broker-visible non-broker tools: {sorted(broker_only)} (want [])")
print(f"catalog ⊇ baseline names: {set(names_b) <= set(catalog_names)}")
print(f"a2a exact: {sorted(ts_a2a) == ['session_search', 'vision', 'web']}")
