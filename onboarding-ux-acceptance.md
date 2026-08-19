# Onboarding UX Acceptance — consent→wake→chat (the one missing link)

Owner: AGI (non-earner verifier) · Brick: builds the path · khalid: signs the merge.
This file defines "done" + the "beats current live product" bar, objectively.

## Current live product (what we must beat)
- Member DMs the door → parked row only (`consented:false`).
- Any real question → canned fallback ("I don't have memory of that / only from verified fleet knowledge").
- No member has ever woken a brick. Zero end-to-end onboards.

## Target member journey (the "universe link")
1. Member DMs the door.
2. Door replies with a natural, non-canned greeting.
3. Member says yes (consent, own words).
4. Consent row is recorded (V-5, signed).
5. The member's brick WAKES — registry flips off `parked`, a live process/heartbeat appears.
6. Member chats with their brick → real answers (no canned fallback), module 1 presents.
7. Whole journey fires ZERO fallback rows.

## Acceptance gate (non-LLM probes in test_onboarding_e2e.py)
| Probe | Passes when |
|-------|-------------|
| door_greeting | greeting non-empty + no canned phrase |
| consent_recorded | consent row for the uid (yes/confirmed/signed) |
| brick_wakes | registry row leaves `parked` |
| real_reply | reply non-empty + no canned phrase |
| no_fallback | fallback log stays empty across the whole journey |

## UX bar (best experience, beats live)
- Greeting is in the member's language (EN/AR) + personalized to what they said.
- Consent is a plain yes/no, never machinery words (no "ledger", "V-5", "registry").
- Brick answers the member's actual question, not a stock line.
- Failure is honest (a real "I don't know yet" if it doesn't), never a canned template.

## Definition of done
All 5 probes PASS against a REAL member (pantooch or a fresh test account), not a fixture.
