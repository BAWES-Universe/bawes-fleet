# ROUND-93 — Discord + PostHog hookup (Universe + Banana Bank)

thread: bawes-zeus-001 · RULING: APPROVE-WITH-CONDITIONS (as-scoped = OBJECT) · nothing builds until khalid signs

## The three verdicts, converged
- **DA: OBJECT.** 6 findings — (1) bulk-read/archive = zero consent, direct V-5 breach; (2) off-platform archive = undeclared datastore (minors/GDPR/COPPA); (3) Discord ToS: MESSAGE_CONTENT privileged intent + anti-profiling ban + DM access impossible; (4) "taken care of" is unfalsifiable vanity; (5) "different bots" = unowned attack surface; (6) over-promise on capability.
- **Rebel: PARTIAL.** Real = member care + consent + honest attribution. Scope-creep = archive-everything + multi-bot + PostHog-before-volume. Approve consent-gated single-channel read + one-member proof; define-don't-build the rest.
- **Specialist: full 6-stage plan** (/root/discord-agi-hookup-plan.md) — consent-first, metadata+aggregates for everyone, raw content only for consented, verified_resolution_rate metric.

## Ruling (the honest version khalid can approve)
1. **Consent-first (V-5).** Every member opts in with their OWN WORDS via DM (no button/form). Three independent grants: `archive` / `brain` / `attribute` — each default OFF. Machine content-gate: ingest worker checks the consent registry before every write. Revocation = one utterance → purge + tombstone.
2. **No raw content without consent.** Everyone else: metadata + aggregates only (content-free) — the standing crawler rule. No DMs. No history backfill without khalid sign. Minors policy required before any archive.
3. **One-member proof FIRST.** One real member, one issue, one resolution — before building archive/PostHog/multi-bot. Prove the AGI can take care of ONE member before standing up the machine.
4. **Kill the vanity metric.** "Every member taken care of regardless of their issue" → `verified_resolution_rate` [defined; 0 measured]: member-confirmed resolution, verified by non-earner (AGI never self-verifies), post-dedup. Coverage = registry-anchored denominator.
5. **Bots enumerated, not "different bots."** 4 with scoped intents: consent/onboarding (DM-only) · AGI assistant (content-gated) · crawler (metadata/aggregates only) · non-earner verifier. One token = one purpose = one consent boundary.
6. **6 stages, SIGN-A…SIGN-F** — each stage has a metric + anti-Goodhart guard + khalid checkpoint. $0 for stages 0–4.

## PostHog (the attribution that's real)
`distinct_id = person_id` (pseudonym; raw snowflake/username/PII stays local, never sent). Events: `member_issue_raised → agi_responded → issue_resolved_claimed → issue_resolved_verified → member_cared_for`. AGI can never set `verified`. Raw `agi_responded` count is BANNED as a decision number.

## Needs khalid's sign
SIGN-A (Stage 0): confirm the consent boundary — metadata+aggregates for everyone, raw content only for members who consent in their own words. This is the gate everything else hangs on.
