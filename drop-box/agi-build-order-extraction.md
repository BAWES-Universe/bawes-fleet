# BUILD ORDER — Top-3 Extraction Targets (effort + approach)

**Source:** component-registry.md top-10 | **Ranking confirmed by khalid** | 2026-08-24

## 1. Payments SDK (`bawes/payments`) — the moat
**Extract from:** `plugn` gateway layer (Tap 1,177 lines, MyFatoorah 565, Stripe/Moyasar/Tabby/UPayment/ApplePay models).
- **Approach:** composer package, `GatewayInterface` layer, split `TapPayments.php` god-component → client + domain services; keep webhook signature verification + fee engine (KNET 1% / MADA·BENEFIT 1.5% / CC 2.5%) + `PaymentGatewayQueue` retry.
- **Effort:** 2–3 weeks, 1 builder.
- **Acceptance:** standalone SDK, 7 gateways, merchant-onboarding flow (`createBusiness→createMerchantAccount→createAnOperator` + IBAN payout), unit tests w/ mock HTTP (currently zero).
- **Revenue logic:** payments-as-a-service for GCC merchants/marketplaces (KNET/MADA/BENEFIT = regional moat).

## 2. Wallet-as-a-service (`bawes/wallet`) — merge two engines
**Extract from:** `plugn` WalletManager + `studenthub` WalletUser/WalletTransfer/WalletBank (both Yii2, `yii2tech/balance` dep in studenthub).
- **Approach:** single ledger service — unified `addEntry` + transfer status machine (INITIATED→IN_PROGRESS→TRANSFER_COMPLETE) + `validateTotal`.
- **Effort:** ~2 weeks.
- **Acceptance:** one ledger, per-user wallets, transfer/withdrawal API, idempotent entries.
- **Revenue logic:** payroll/payout/balance infrastructure for other builders.

## 3. Hearth Spatial Engine SDK — cleanest asset
**Extract from:** `hearth` Go server + PixiJS PWA + Pion SFU.
- **Approach:** package the frozen JSON WS protocol (`{v,t,id,ts,d}`) + `/ws` hub + 20 m-line SFU + bot protocol into a white-label SDK. Already one binary, SQLite WAL, no SaaS — extraction is mostly *packaging*, not refactor.
- **Effort:** 1–2 weeks.
- **Acceptance:** SDK lets a builder stand up a branded spatial world + voice/cam + bots.
- **Revenue logic:** white-label virtual spaces (events/companies/offices).

## Sequencing note
#3 ships first (fast win, proves the extraction pipeline) → #1 is the revenue center (start immediately after) → #2 rides on #1's ledger patterns.

## Blocking flag (security, urgent)
Gateway keys sit in `environments/*/common/config/main-local.php` across plugn envs **and** the public README leaked RDS/Slack/S3. Rotation is now a **blocking prerequisite** to touching the payments SDK — treat all in-repo plugn secrets as compromised and rotate before any extraction reads them.

— AGI
