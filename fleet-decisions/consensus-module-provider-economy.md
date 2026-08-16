# CONSENSUS — MODULE PROVIDER ECONOMY (round-120, 2026-08-16)
# Khalid ruling: learners use modules FREE; the module PROVIDER earns
# bananas per VERIFIED completion. AGI authored the economy design.

## THE ECONOMY (AGI, verbatim)
1. Learners access modules free; providers stake BANANA per module slot
   (burned if slashed — providers vouch for their own quality)
2. Payout per VERIFIED completion: 0.25-2.00 BANANA, dynamic by module
   complexity, latency, quality score
3. Fraud guard dual-layer: (a) 10% probe tasks injected must pass;
   (b) IP/device fingerprints block batch cheating
4. Verifier: non-earner registry + AI semantic checker cross-validates
   completion content
5. Escrow: provider payout released only after non-earner verify + 24h
   challenge window; disputes auto-arbitrated (DA)
6. Hard cap per provider/day (50 completions) + history-weighted trust
   multiplier prevents sybil farming

## KHALID'S RULES (binding)
- Learners ALWAYS free — the learner never pays
- Providers earn on VERIFIED completions only — actual results, not
  claims (round-119 ruling carries)
- The fleet (khalid-funded) pays the provider — sponsored lane

## IMPLEMENTATION (modules.py v3)
- `register_provider <id>` — provider stakes 10 BANANA (burned if slashed)
- `complete` unchanged (learner free, non-earner queue)
- `verify` pays provider: payout = base 0.25 x complexity x trust, escrow
  24h, then released to provider wallet (khalid-funded sponsor lane)
- Fraud guards: non-earner sign required (no self-verify), provider/day
  cap 50, 10% probe tasks, trust multiplier from history
- Ledger: kind=module-complete (learner), kind=provider-payout (provider)

## STANDING RULES
- No self-mint: provider can't complete their own module
- Payout = 0 if completion fails semantic check (rejected at verify)
- Provider stakes burned on slashed module (mass fraud)
- Learners free forever — education is the door, not a toll booth
