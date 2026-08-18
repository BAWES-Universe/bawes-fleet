# EVOLUTION SPRINT — 5 holes, each closed by a Qwen-authored patch + non-LLM probe

Budget: $4 max (ledger T-UNIVERSE-033). Pass = ≥5 probes flip RED→GREEN. Verifier = probe output (curl/pytest), never an LLM opinion.

## The 5 holes (all real, from Qwen's findings + FLEET-STATE broken list)

| # | Hole | Patch | Probe (RED→GREEN) |
|---|------|-------|-------------------|
| 1 | Consensus gate has no enforcement (Qwen #3) | `gate.py` — hard-reject any action lacking CLOSED consensus (DA+rebel+Brick+khalid) | `test_gate.py`: 10 non-consensus writes → 10/10 rejected; 1 closed action → allowed |
| 2 | Plaintext relay = trust-in-operator (Qwen #1, DA F2) | `detect_plaintext.py` — scan relay traffic for bare secrets (API keys/PATs) + flag | `probe_plaintext.py`: submit fake secret → detected (accept → reject) |
| 3 | Circular verification (Qwen #2) | `non_llm_probe.py` — final verification is a machine test, not the AGI grading its own subagents | probe emits machine-readable PASS/FAIL (no LLM in the loop) |
| 4 | Abuse monitor spec exists, no impl | `abuse_monitor.py` — 6 signals (alt-account, cap-dodge, spend-spike, leak, injection) | `probe_abuse.py`: feed a simulated spend-spike → flagged |
| 5 | Brick self-recover (M2) unbuilt | `self_recover.py` — watchdog detects dead process + restarts | `probe_selfrecover.py`: kill a proc → auto-restarted |

## Flow per hole
Qwen (on GPU, brick's brain) generates the patch → wrapper applies it → probe runs → RED→GREEN = closed.

## Metric
verified patches (RED→GREEN) per dollar. Target: 5/5 inside $4.
