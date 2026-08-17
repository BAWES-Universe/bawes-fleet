# COMPLETION ATTESTATION POLICY (khalid, 2026-08-17: "I expect the agi and
# any brick to tell me it's perfect too. They all need to be impressed by
# our solution, even if I give an independent third party to audit our work")

## THE BAR
Nothing is "done" on the word of the builder. A change is complete ONLY when
ALL of the following attest independently:
1. The AGI (fleet brain) — rules the change is sound and consistent with
   the ledger/economy.
2. The DA (hostile review) — attacks it and cannot break it.
3. The Rebel — dissents and finds nothing material missed.
4. The scientist verifier — quotes the evidence it audited (hash/excerpt)
   and signs.
5. An INDEPENDENT third party (khalid may bring one) — can audit the work
   from the public artifacts (achievements.jsonl receipts recomputable,
   registry/wallet/ledger rows, feed entries with V-18 accounting) and
   reach the same verdict WITHOUT talking to us.

## WHY
Khalid: "They all need to be impressed by our solution, even if I give an
independent third party to audit our work." Self-verification was the sham;
multi-agent attestation with an external-audit test is the fix.

## MECHANISM
- Every completion report carries an ATTESTATION BLOCK: AGI verdict, DA
  verdict, rebel verdict, scientist signature, and a "third-party audit
  kit" pointer (which public files to check, how to recompute receipts).
- The attestation block is part of the round file and survives in
  fleet-decisions.md.
- If any of the five attestors objects, the change is not complete — it
  goes back to the fix list with the objection attached.
