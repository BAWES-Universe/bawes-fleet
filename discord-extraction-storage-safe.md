# Discord extraction + storage — SAFE spec (consolidates round-93/95 + distillation)

thread: bawes-zeus-001 · khalid: "consensus on data extraction and storage, safe way where it isn't leaked. There's lots of knowledge."

## The one rule that makes it safe
**The AGI and every agent learn from DISTILLED signals, never raw messages, never real identities.** The pipeline strips + hashes before anything is stored. A leak of the store leaks no private conversation.

## What gets extracted (distilled, not raw)
- **Needs** — what members are asking for, aggregated.
- **Unanswered questions** — questions no one resolved (the "lost people" to re-engage).
- **Lost-member signals** — who went quiet + why (aggregated).
- **Topic clusters** — what the community is about.
- **Hashed member IDs** — no real Discord IDs stored anywhere.

## What is NEVER stored
- Raw message text (discarded after aggregation).
- Real member IDs (hashed).
- Any message from a member who hasn't consented in their OWN words (V-5). Non-consenting members → aggregates only.

## Storage
- Distilled signals → the vector store / vault (encrypted, mode-600), NOT in any LLM context, NOT raw.
- The AGI reads only aggregated + hashed signals — so it learns what members need without touching a real conversation or identity.

## Compliance (round-93 DA)
- MESSAGE_CONTENT intent enabled (khalid's step).
- Read-only; consent = own words; machine-enforced privacy (R1/V-5).
- Discord ToS: aggregated + read-only, no raw message storage.

## The honest read
"Lots of knowledge" = the distilled signals are the gold, not the raw chatter. We extract the SIGNAL and discard the SOURCE — that's what makes it safe AND useful. Same pattern as the token doctrine: the agent sees the handle, never the value.

## Sent to: Brick (co-sign) + DA (the consent boundary re-verified).
