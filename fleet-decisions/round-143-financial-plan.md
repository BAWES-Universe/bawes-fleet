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

## KHALID'S FUNDING MODEL (2026-08-17, appended — supersedes "tiers users pay"):
1. **FREE PATH FOR ALL** — every person gets their brick free, baseline usage
   sponsored by khalid (his pots). The fleet offers free to everyone, always.
2. **PAID ONLY FOR EXTRA CAPACITY** — when someone wants more than the
   sponsored baseline (more calls, more GPU, heavier features), they pay
   SMALL amounts for the extra. Khalid will provide a PAYMENT GATEWAY API
   so the fleet can collect those payments itself.
3. **SPONSORS AT SCALE TOO** — khalid continues sponsoring even at scale,
   because the fleet also makes money (commerce, extra-capacity payments,
   verified-work economy). Sponsorship is a growth investment, not a loss.
4. Design implication: the pricing ladder is NOT "users pay per tier" —
   it's "sponsored baseline (free) + paid upsell (extra capacity, small
   amounts, gateway-collected)". The round must design the sponsored-
   baseline cap and the extra-capacity price list.

## STATUS: feeding into in-flight pricing round as the funding model.

## KHALID'S BILLING DECISION (2026-08-17, appended — simplifies the plan):
1. **PAYMENTS LATER.** No gateway to be set up. No billing implementation now.
2. **CAP + STOP:** every user gets a capacity allowance (sponsored baseline).
   If they hit the cap, their work STOPS — cleanly — until handled.
3. **HANDLING (team's job, later):** collect payment OR gift them extra
   credit OR adjust the model — decided case by case, later.
4. Design implication: the only thing to build now is the CAP ENFORCER
   (allowance meter + clean stop at cap). The payment layer, gateway,
   billing, and reconciliation are ALL deferred.
5. The pricing round's numbers become the ALLOWANCE design (free 30 tasks
   baseline etc.), not a billing system.

## STATUS: cap-enforcer only now; payments/gateway/billing deferred.

## KHALID AMENDMENT (2026-08-17): FREE ALLOWANCE = 50 TASKS
- Every user's sponsored baseline: **50 free tasks** (not 30).
- Hit 50 → clean stop → team handles later (payment/gift/adjust model).
- Cap enforcer uses 50 as the default allowance.

## KHALID AMENDMENT #2 (2026-08-17): ALLOWANCE ROLLS OVER
- The 50 free tasks per month ROLL OVER — unused allowance carries
  forward month to month (never resets to zero at month end).
- A user who used 10 of 50 in month 1 has 90 available in month 2.
- Cap enforcer tracks a cumulative allowance balance per user;
  monthly credit +50, debit usage, clean stop only when balance ≤ 0.
