# CONSENSUS — STAFF ONBOARDING AT SCALE (round-115, 2026-08-16)
# AGI authored the scale design. Doctrine reconciled: ownership 1:1 stays.

## AGI's scale design (verbatim, 8 points)
1. Batch all 10: door event opens ONCE for staff IDs 01-10, no individual entries
2. Order: accounts -> brick assignment -> billing codes -> genesis tasks -> heartbeat check
3. Per-brick caps: max 3 staff per brick — split 10 as 3+3+2+2 across four bricks
   [RECONCILED: 3-per-brick = POOLED SUPPORT LANE, not ownership]
4. Billing: one finops code per staff, project prefix attached, auto-invoice at day end
5. Door: single access grant; open once, close after all 10 report inside
6. Genesis task: push one unique task to each staff inbox immediately after door close
7. If prefill-bound at 17K tokens, stagger genesis pushes by token window, not time
8. Done when all 10 show 5-min heartbeat in registry; rollback door access for missing IDs

## RECONCILIATION (khalid's doctrine vs AGI's 3-per-brick)
- OWNERSHIP: round-105 unchanged — 1 human = 1 brick for accountability
- 3-per-brick = POOLED SUPPORT LANE: one operational container serving
  multiple staff lanes, access sliced per brick (multi-tenant)
- ENFORCE: brick-owner final sign-off so pooled staffing never blurs
  responsibility (AGI's condition)

## Standing rules
- Door = one-link consent flow, V-5 own words, revocable
- Genesis task per staff = first verified unit before lane opens wider
- Heartbeat = the alive signal; missing IDs = door rollback
- Non-earner verifies every genesis task; no self-mint
