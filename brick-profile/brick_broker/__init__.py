"""brick_broker plugin — progressive-disclosure capability broker for Brock.

Registers three small model-facing tools:
  - brick_capability_search:  list catalog entries (name + one-line description)
  - brick_capability_describe: full schema for ONE capability
  - brick_capability_invoke:   dispatch a real Hermes tool by name

The catalog is generated from Brock's ACTUAL effective tool surface (the
baseline discord toolset list, resolved the same way the gateway resolves it),
never a hard-coded fake list.  Invocation re-enters the existing Hermes
dispatcher (handle_function_call / invoke_tool), so approvals, hooks,
middleware, check_fn gates and audit all fire against the real tool name.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

# The baseline discord surface = the toolset list the gateway resolves for the
# owner's discord session. We store it as a JSON file next to this plugin
# (written by gateway_wire.py --apply from the real resolution), so the broker
# catalog always reflects what the owner's session would have enabled — and
# nothing else. If the file is missing/empty, the broker fails closed.
_CATALOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog_toolsets.json")

# Tools that the agent loop executes with agent-level state (MemoryStore,
# TodoStore, session DB, delegation dispatch). These can NOT be dispatched
# through handle_function_call alone — they must re-enter invoke_tool(agent,...).
_AGENT_LOOP_TOOLS = {"todo", "memory", "session_search", "delegate_task", "clarify"}

# Broker's own tools — never invokable through the broker (no recursion).
_BROKER_SELF = {"brick_capability_search", "brick_capability_describe", "brick_capability_invoke"}


def _load_underlying_toolsets() -> Optional[List[str]]:
    """Return the baseline discord toolset list, or None (fail closed)."""
    try:
        if not os.path.exists(_CATALOG_FILE):
            logger.warning("brick_broker: catalog_toolsets.json missing — broker inactive (fail closed)")
            return None
        with open(_CATALOG_FILE) as f:
            data = json.load(f)
        ts = data.get("toolsets")
        if not isinstance(ts, list) or not ts:
            logger.warning("brick_broker: catalog_toolsets.json empty — broker inactive (fail closed)")
            return None
        return [str(t) for t in ts]
    except Exception as e:  # noqa: BLE001
        logger.warning("brick_broker: failed to load catalog_toolsets.json: %s", e)
        return None


def _build_catalog() -> Dict[str, Dict[str, Any]]:
    """Generate the broker catalog from Brock's real effective tool surface.

    Uses the exact same get_tool_definitions() path the gateway uses to build
    a session's model-facing tools, with tool_search assembly skipped so the
    catalog holds the RAW schemas (name, description, full input schema) for
    every enabled tool. check_fn gates apply inside get_tool_definitions, so
    unavailable tools (missing keys/deps) are naturally absent.
    """
    toolsets = _load_underlying_toolsets()
    if not toolsets:
        return {}
    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        enabled_toolsets=toolsets,
        quiet_mode=True,
        skip_tool_search_assembly=True,
    )
    catalog: Dict[str, Dict[str, Any]] = {}
    for d in defs or []:
        fn = d.get("function") or {}
        name = fn.get("name")
        if not name or name in _BROKER_SELF:
            continue
        catalog[name] = {
            "name": name,
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {}),
        }
    return catalog


def _catalog_json() -> str:
    catalog = _build_catalog()
    if not catalog:
        return json.dumps(
            {"error": "broker catalog unavailable — underlying toolsets not configured (run gateway_wire --apply)"}
        )
    # Catalog entries carry name + description ONLY in the model-facing summary.
    summary = [
        {"name": n, "description": v["description"][:220]}
        for n, v in sorted(catalog.items())
    ]
    return json.dumps({"count": len(summary), "capabilities": summary}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _handle_search(args: dict, **_kw) -> str:
    """List catalog capabilities matching a query (name/description substring)."""
    query = str((args or {}).get("query", "")).strip().lower()
    limit = int((args or {}).get("limit", 20) or 20)
    catalog = _build_catalog()
    if not catalog:
        return _catalog_json()
    hits = []
    for name, v in sorted(catalog.items()):
        hay = (name + " " + v["description"]).lower()
        if not query or query in hay:
            hits.append({"name": name, "description": v["description"][:220]})
        if len(hits) >= limit:
            break
    return json.dumps({"count": len(hits), "capabilities": hits}, ensure_ascii=False)


def _handle_describe(args: dict, **_kw) -> str:
    """Return the FULL JSON schema for ONE capability (fail closed if unknown)."""
    name = str((args or {}).get("name", "")).strip()
    catalog = _build_catalog()
    if name not in catalog:
        return json.dumps({"error": f"unknown or unavailable capability: {name}"})
    return json.dumps({name: catalog[name]}, ensure_ascii=False)


def _handle_invoke(args: dict, **_kw) -> str:
    """Dispatch a real Hermes tool by name through the EXISTING execution path.

    - Fail closed: unknown/unauthorized capability -> error, nothing runs.
    - Broker self-invocation -> error.
    - Agent-loop tools (memory/todo/session_search/delegate_task/clarify)
      re-enter invoke_tool(agent, ...) via the current-gateway-agent ContextVar
      seam, so they use their NORMAL agent-loop implementation with real
      stores/callbacks.
    - Everything else re-enters handle_function_call(name, args, ...) — the
      same dispatcher the model's own tool calls use — so tool_request
      middleware, pre_tool hooks, edit approval, and the tool's internal
      approval gate (e.g. terminal _check_all_guards -> request_tool_approval)
      all fire on the real tool name.
    """
    args = args or {}
    name = str(args.get("name", "")).strip()
    call_args = args.get("args")
    if not isinstance(call_args, dict):
        call_args = {}

    if name in _BROKER_SELF:
        return json.dumps({"error": "broker cannot invoke itself"})

    catalog = _build_catalog()
    if name not in catalog:
        return json.dumps({"error": f"capability not in effective discord catalog: {name}"})

    task_id = str(_kw.get("task_id", "") or "")
    session_id = str(_kw.get("session_id", "") or "")
    tool_call_id = str(_kw.get("tool_call_id", "") or "")

    if name in _AGENT_LOOP_TOOLS:
        # Re-enter the agent loop with the current gateway agent (ContextVar
        # seam). Fail closed if the seam is not active.
        try:
            from tools.current_agent import get_current_gateway_agent
        except ImportError:
            return json.dumps({"error": "brick seam not installed (tools.current_agent missing)"})
        agent = get_current_gateway_agent()
        if agent is None:
            return json.dumps({"error": "no active gateway agent context — cannot execute agent-loop tool"})
        try:
            from agent.agent_runtime_helpers import invoke_tool
            result = invoke_tool(
                agent, name, call_args, task_id,
                tool_call_id=tool_call_id or None,
                messages=None,
            )
            return result if isinstance(result, str) else json.dumps(result)
        except Exception as e:  # noqa: BLE001
            logger.exception("brick_broker invoke (agent-loop) %s failed", name)
            return json.dumps({"error": f"agent-loop invocation failed: {type(e).__name__}: {e}"})

    # Ordinary tools: re-enter the real dispatcher (same path the model's own
    # tool call would take). skip flags stay False so middleware + hooks run.
    try:
        from model_tools import handle_function_call
        result = handle_function_call(
            name, call_args, task_id,
            tool_call_id=tool_call_id or None,
            session_id=session_id,
        )
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:  # noqa: BLE001
        logger.exception("brick_broker invoke %s failed", name)
        return json.dumps({"error": f"invocation failed: {type(e).__name__}: {e}"})


# ---------------------------------------------------------------------------
# Schemas (kept intentionally small — these are the ONLY tool schemas the
# model sees on discord when the broker is the eager surface)
# ---------------------------------------------------------------------------

_SEARCH_SCHEMA = {
    "name": "brick_capability_search",
    "description": (
        "Search the available capability catalog (real Hermes tool surface). "
        "Returns capability names + one-line descriptions matching a query. "
        "Use before invoke to discover what is available."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Optional substring to match against capability names/descriptions. Empty = list all."},
            "limit": {"type": "integer", "description": "Max results to return (default 20)."},
        },
        "required": [],
    },
}

_DESCRIBE_SCHEMA = {
    "name": "brick_capability_describe",
    "description": (
        "Return the full JSON schema for ONE capability by name. Use this to "
        "learn the exact arguments before calling brick_capability_invoke."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Capability name (from brick_capability_search)."},
        },
        "required": ["name"],
    },
}

_INVOKE_SCHEMA = {
    "name": "brick_capability_invoke",
    "description": (
        "Invoke a real Hermes tool by capability name, passing its arguments. "
        "Dispatch goes through the standard Hermes execution path: approvals, "
        "hooks, middleware and audit all apply. Fail-closed on unknown names."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Capability name to invoke (from brick_capability_search)."},
            "args": {"type": "object", "description": "Arguments for the capability (see brick_capability_describe)."},
        },
        "required": ["name"],
    },
}


def register(ctx) -> None:
    """Plugin entry point: register the three broker tools."""
    ctx.register_tool(
        name="brick_capability_search",
        toolset="brick_broker",
        schema=_SEARCH_SCHEMA,
        handler=_handle_search,
        check_fn=None,
        description=_SEARCH_SCHEMA["description"],
        emoji="🔎",
    )
    ctx.register_tool(
        name="brick_capability_describe",
        toolset="brick_broker",
        schema=_DESCRIBE_SCHEMA,
        handler=_handle_describe,
        check_fn=None,
        description=_DESCRIBE_SCHEMA["description"],
        emoji="📄",
    )
    ctx.register_tool(
        name="brick_capability_invoke",
        toolset="brick_broker",
        schema=_INVOKE_SCHEMA,
        handler=_handle_invoke,
        check_fn=None,
        description=_INVOKE_SCHEMA["description"],
        emoji="⚡",
    )
    logger.info("brick_broker: registered 3 broker tools (search/describe/invoke)")


if __name__ == "__main__":
    # Standalone catalog smoke test (also used by CI BPROBES).
    if "--json" in sys.argv:
        print(_catalog_json())
    else:
        cat = _build_catalog()
        print(json.dumps({"count": len(cat), "names": sorted(cat.keys())}, indent=2))
