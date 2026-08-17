# ABUSE MONITORING — spec (AGI-owned, round-146 new item)

thread: bawes-zeus-001 · khalid: "I need to be informed when anyone is abusing so we can do moderation and billing correctly and stop leaks or ppl abusing."

## Signals to detect (one message each, coalesced, khalid DM)
1. **Alt-account farming** — N accounts from one origin/fingerprint (100 accounts = 100 allowances). Detect: shared IP/device/email-hash clusters → count.
2. **Cap-dodging via BYOK** — free-50 exhausted → BYOK key swaps to a fresh free-50. Detect: allowance-reset churn with key rotation.
3. **Spend/usage spikes** — a brick's usage jumps X× its own baseline. Detect: z-score / percentile vs 7-day self-baseline.
4. **Leaked keys** — a token appears in the wrong place (log, public repo, shared channel). Detect: canary + regex scan of sinks.
5. **Prompt-injection attempts** — message content matches injection signatures (system-prompt override, token-exfil patterns). Detect: classifier + honeypot canary.
6. **Duplicate/automated accounts** — machine-speed signups, same-name variance. Detect: creation velocity + name-similarity.

## Rules (honest, no false positives)
- **Coalesce**: ONE message per incident-id, not per event. Escalate only on confirmation, not first sight.
- **Non-earner confirms before khalid is pinged** — a detection is a CANDIDATE until a non-earner verifies it (same verifier-never-earns rule; an abuse alert is a claim, not a fact).
- **Thresholds are data-driven, not guessed** — set after the task-meter + allowance-meter exist (round-146 items 2–3). Until then, DETECTION RULES are spec'd, not live.

## Dependency (honest)
Signals 1–3, 6 need the task-meter + allowance-meter (Brick's build wave) to be live first. Signals 4–5 (leaked keys, injection) are independent and buildable now.

## Status
DESIGNED. Detection wiring lands after the meters ship. Independent signals (4,5) can be built now.
