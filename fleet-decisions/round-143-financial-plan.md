# ROUND-143 — FINANCIAL TRANSPARENCY PLAN (khalid, 2026-08-17)
# "I don't mind paying 5 pots. What I need is full transparency in
# utilization and scale reqs and capacity."

## KHALID'S REQUIREMENT (verbatim):
5 pots are fine (DeepSeek, OpenRouter, Vast, OVH, Hetzner). The deliverable
is FULL TRANSPARENCY:
- per-pot utilization (what's spent, what's left, burn rate)
- what each pot buys / which workloads draw from it
- capacity (what the current capacity supports: users, calls, GPU-hours)
- scale requirements (what must be added WHEN to grow: box RAM, Vast,
  storage — the triggers, not dreams)

## CONTRACT: a single transparency surface (fleet dashboard) showing all 5
pots live — balance, utilization, per-user cost, capacity, and the
next-scale trigger — ledger-derived, never hand-written. Khalid refills
any pot when HE chooses; the fleet guarantees the numbers are true.

## STATUS: awaiting the in-flight pricing round (deleg_6b9100ee) to fold
this requirement in; the consolidated deliverable = pricing ladder +
refill guidance + the 5-pot transparency dashboard.
