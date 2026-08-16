"""Brick broker seam — turn-scoped current-agent ContextVar.

Hermes 0.20.1 compatibility seam (installed by brick-profile/hermes-seam/
install_seam.py): exposes the active gateway AIAgent to broker invocation.

Guarantees:
  - SET once per gateway turn, right after the agent is built (gateway/run.py
    _run_agent_inner, anchored on ``ctx.agent_holder[0] = agent``).
  - RESET in the turn's ``finally`` (anchored on
    ``reset_current_session_key(_approval_session_token)``), so it is cleared
    on success, exception, cancellation AND tool failure.
  - task/session isolated: ContextVar is per-context; the gateway runs each
    turn in its own task/thread context, so two concurrent sessions can never
    see each other's agent.
  - NEVER stored in a process-global session->agent dict.
  - NEVER exposed to the model, never serialized, never logged.
"""
from __future__ import annotations

import contextvars

_current_agent: contextvars.ContextVar = contextvars.ContextVar(
    "brick_current_gateway_agent", default=None
)


def set_current_gateway_agent(agent) -> contextvars.Token:
    """Bind the current gateway agent for this turn. Returns a reset token."""
    return _current_agent.set(agent)


def reset_current_gateway_agent(token: contextvars.Token) -> None:
    """Unbind the turn-scoped agent binding (call in finally)."""
    _current_agent.reset(token)


def get_current_gateway_agent():
    """Return the agent bound for the current turn, or None (fail closed)."""
    return _current_agent.get()
