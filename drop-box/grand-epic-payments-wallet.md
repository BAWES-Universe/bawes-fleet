# GRAND EPICS v1 — khalid's picks (2026-08-24, in-session confirmation)
**khalid verbatim:** "I like payment as a service and wallet as a service"

## GE-1: Payments-as-a-Service (GCC)
- **Asset:** plugn gateway layer — Tap, MyFatoorah, Stripe, Moyasar, Tabby, UPayment, Apple Pay; marketplace merchant onboarding + IBAN payouts; KNET/MADA/BENEFIT moat
- **Extraction:** TapPayments.php (1,177 ln) + MyFatoorahPayment.php (565 ln) → client/domain split → SDK
- **Revenue:** sell to GCC merchants/marketplaces
- **Priority (khalid):** 5/5
- **Blockers:** Yii2 entanglement, gateway-key rotation (URGENT — keys in env files + README leak)

## GE-2: Wallet-as-a-Service
- **Asset:** plugn wallet engine + StudentHub wallet/invoice/contract models
- **Merger:** payroll/payout infrastructure — the banana rails already specced become the product
- **Priority (khalid):** 5/5
- **Blockers:** ledger schema unification (studenthub vs plugn vs fleet wallet)

## GE-3: Hearth spatial engine (white-label) — pending, lower priority than khalid's two picks

**Budget sliders:** to be wired in the strategic-layer build (in flight). khalid allocates at grand-epic level only.
**Attestation chain:** filed → AGI attest → DA/Rebel rule → build on free models.
