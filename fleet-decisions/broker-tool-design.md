# BROKER TOOL — the real slim (design, from skill ref + 0.20.1 source)
# Core tools never defer. Config ceiling measured: 9,075 tokens even at
# minimal-owner. The ~2K target needs a broker: a small-schema custom
# toolset that RE-ENTERS the existing dispatcher per call.

## How it works (verified in 0.20.1 source)
# model_tools.handle_function_call (model_tools.py:1170) is THE single
# registry dispatcher. Tool Search bridge unwraps to the real tool name
# and RECURSES into handle_function_call — all hooks fire against the
# real name; the bridge is invisible to hooks (model_tools.py:1307-1325).
#
# A broker tool does the same: resolve name -> allow-list check -> recurse
# into handle_function_call with the real name. It is a re-entry point,
# not a re-implementation.
#
# Invariants:
# - The broker only WEAKENS if it reimplements execution — forbidden.
#   It must recurse into the real tool, inheriting approval prompts
#   (terminal approval at tools/approval.py) and all middleware.
# - enabled_toolsets/disabled_toolsets passed through on recursion so
#   the catalog stays scoped to the session (model_tools.py:1293-1300).
# - _AGENT_LOOP_TOOLS reject direct dispatch — broker must not bypass.

## Surface shape
# Discord surface = A2A (web/vision/session_search, ~1,947) + ONE broker
# tool (~300 tokens) with a compact schema: {tool: str, args: object}.
# Total ≈ 2,300 tokens vs 14,342 baseline. ~6x reduction.

## Policy
# - Broker allow-list per brick, signed in the brick manifest (a2a policy
#   shape, per brick-tool-surface-policy.md rule 1: never reinterpret one
#   platform's signed policy as another's).
# - Owner capabilities = full allow-list on the owner's own surface;
#   Mishari's Brock gets the capability-preserving broker list.
# - Audit: every broker call logged with tool, args-hash, caller.
