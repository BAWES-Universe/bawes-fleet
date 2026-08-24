# BAWES Reusable-Ecosystem Catalog — Component Registry

> **Purpose**: Map every BAWES repo into a reusable-ecosystem catalog so builders can assemble products from existing components instead of greenfielding. Feed for "build tooling → upsell services" strategy.
> **Source**: GitHub API (real data), 2026-08-24. Read-only; no writes to any repo. Credentials redacted throughout.
> **Scope**: BAWES-Universe org (69 repos) + BAWES user account (183 repos, mostly OSS forks = candidate infrastructure).

---

## (a) Repo Inventory

### BAWES-Universe org — 69 repos (exact count from GitHub API, 2026-08-24)

| Repo | Lang | Size KB | Stars/Forks | Last push | What it is |
|---|---|---|---|---|---|
| .github | — | 6 | 0/0 | 2026-05-18 | Org metadata |
| bawes-doc-updater | TypeScript | 63 | 0/0 | 2025-02-20 | Mintlify doc updater by SpinAI |
| BAWES-ERP | TypeScript | 1,893 | 2/1 | 2025-01-13 | ERP for BAWES operations |
| BAWES-ERP-frontend | TypeScript | 501 | 1/1 | 2026-06-21 | ERP frontend |
| BAWES-ERP-sdk | TypeScript | 11,525 | 1/0 | 2025-06-08 | SDK for the ERP API |
| bawes-fleet | Python | 1,132 | 0/0 | 2026-08-24 | Fleet ops: skills/, knowledge/, ledger/, router/, vault/, rate-card/, consensus rounds, brick packages |
| bawes-knowledge | Python | 328 | 1/0 | 2026-08-23 | Shared knowledge library: org docs, skill DNS, agent cards, consensus ledger |
| bawes-landing | TypeScript | 362 | 0/0 | 2026-05-15 | Landing page |
| bawes-new-website | TypeScript | 1,993 | 0/0 | 2026-08-10 | Current website |
| Bawesnet00-Blockchain | TypeScript | 1,485 | 0/0 | 2022-12-29 | Blockchain project (dormant) |
| cal.com ⑂ | TypeScript | 864,827 | 0/0 | 2025-04-06 | Fork — scheduling infra |
| documenso ⑂ | TypeScript | 180,787 | 0/0 | 2025-04-06 | Fork — open DocuSign alternative |
| hearth | Go | 126,029 | 1/0 | 2026-08-24 | Self-hosted spatial universe: Go monolith + PixiJS PWA + built-in Pion SFU (live at hearthapp.bawes.net) |
| music-videos-remotion | TypeScript | 222,965 | 0/0 | 2026-02-12 | Remotion music-video generation |
| n8n ⑂ | TypeScript | 173,586 | 0/0 | 2024-10-07 | Fork — workflow automation |
| oidc-authentik | CSS | 2,322 | 0/0 | 2025-12-17 | Authentik OIDC setup: blueprints, docker-compose, custom assets |
| orbit-browser | Swift | 186 | 1/0 | 2026-08-15 | Hardened shell browser for the Universe (rules UI, AI assist, preloads) |
| plugn | PHP | 60,409 | 1/44 | 2025-11-05 | **Commerce monolith** (Yii2, multi-app: api/agent/backend/frontend/crm/partner/store). ~8k stores. ALL gateway integrations live here |
| plugn-dashboard-ionic | TypeScript | 23,405 | 0/0 | 2026-02-25 | Dashboard app |
| plugn-device | Java | 134 | 0/0 | 2022-02-26 | Device app (dormant) |
| plugn-ionic | TypeScript | 14,620 | 0/0 | 2025-08-20 | Mobile app |
| plugn-landing | HTML | 25,062 | 0/0 | 2025-11-04 | Landing pages |
| plugn-microservices | JavaScript | 35,552 | 0/1 | 2025-02-20 | Store microservices: aws-lambda-s3, kafkajs, openai(-cities/-file-search), plugn-store-cloudfront/files/manifest, status-api, store-assistant |
| plugn-shadcn-dashboard | TypeScript | 1,418 | 0/0 | 2024-11-14 | Shadcn dashboard |
| plugn-store | Vue | 10,701 | 0/0 | 2025-08-20 | Storefront app |
| plugn-store-community | Vue | 6,312 | 0/0 | 2024-07-23 | Open-source version of the Plugn.io store |
| plugn-store-sdk | JavaScript | 47 | 0/0 | 2025-04-07 | Store SDK |
| pogi | PHP | 89,506 | 0/0 | 2023-12-03 | Pogi Jobs backend (Yii2) |
| pogi-admin / pogi-employer / pogi-jobs | TypeScript | 6,753/33,315/33,504 | 0/0 | 2026-01-29/2021-02-19/2021-05-20 | Pogi frontends (Ionic) |
| pogi-postman | — | 1,023 | 0/0 | 2021-02-07 | Postman collections backup |
| scripting-api-extra ⑂ | — | 35,626 | 0/0 | 2025-09-24 | Fork — WorkAdventure map scripting utils |
| self-hosted-ai-starter-kit ⑂ | — | 3,994 | 0/0 | 2024-09-24 | Fork — local AI template |
| smartcar | JavaScript | 91 | 0/0 | 2024-08-19 | Netlify app: smartcar.com integration |
| stencil | TypeScript | 622 | 0/0 | 2022-12-19 | BAWES Stencil web components |
| studenthub | PHP | 55,753 | 1/30 | 2026-08-18 | **Payroll platform** (Yii2 monolith, 10y prod, 600+ stores, ~120 models: Candidate/Company/Store/Mall/Contract/Invoice/Wallet) |
| studenthub-admin / -candidate / -company / -staff | TypeScript | 6,560/13,575/6,474/11,062 | 1/1 etc. | 2026-06/07 | Ionic frontends (payroll portals) |
| studenthub-candidate-next | TypeScript | 2,217 | 0/0 | 2026-08-19 | Next.js candidate app |
| studenthub-candidate-react | TypeScript | 12,663 | 1/3 | 2026-08-19 | React candidate app |
| studenthub-finance / -team | TypeScript | 1,240/1,224 | 0/0 | 2023-03-06 | Finance/team modules (dormant) |
| studenthub-inspector | TypeScript | 117 | 0/0 | 2021-03-23 | Inspector tool |
| studenthub-manager | TypeScript | 840 | 0/0 | 2026-02-25 | Manager app |
| studenthub-mcp | Python | 31 | 1/0 | 2026-08-11 | SELECT-only MCP data layer (search_candidates, get_company_tree, etc.) |
| studenthub-microservices | JavaScript | 12,576 | 0/1 | 2026-08-20 | SQS, linear, process-id-request, proxy-manager, yeastar-voicemails, yeastar-websocket-client |
| studenthub-pbx | Go | 15 | 0/0 | 2024-03-17 | Call-center integration |
| studenthub-personas | JavaScript | 32 | 0/0 | 2026-02-12 | Persona landing pages |
| studenthub-team | TypeScript | 1,224 | 0/0 | 2023-03-06 | Reports/team |
| tamr | PHP | 1,215 | 0/0 | 2025-03-12 | Tamr Yii2 backend (clone returns 403 w/ PAT — restricted) |
| tamr-admin / -staff / -user | TypeScript | 1,275/1,367/2,627 | 0/0 | 2025-03 | Tamr frontends |
| tamr-provider | JavaScript | 1,192 | 0/0 | 2025-03-12 | Service-provider app |
| universe-imagine-mcp | Python | 30 | 1/0 | 2026-07-17 | MCP server for Universe Imagine |
| universe-maps | HTML | 48,092 | 0/0 | 2025-12-29 | Maps for the Universe (default branch master) |
| universe-matrix-synapse | Shell | 34 | 0/0 | 2025-12-18 | Matrix Synapse for WorkAdventure chat |
| UniverseOS | Dockerfile | 27 | 0/0 | 2026-08-14 | Deployable OS stack (fly.toml, compose/, deploy/, src/) |
| wallet | PHP | 1,500 | 0/1 | 2025-03-10 | BAWES wallet app (Yii2 + webhook/ + railway deploy) |
| whitebook | JavaScript | 52,236 | 0/0 | 2018-01-02 | White Book project (dormant) |
| whitebook-mobile | TypeScript | 1,777 | 0/0 | 2017-09-11 | White Book mobile (dormant) |
| workadventure-universe ⑂ | TypeScript | 211,497 | 1/9 | 2026-08-22 | **Prod fork** of WorkAdventure (16-bit virtual office) — livekit/synapse/oidc compose variants, map-storage |
| workadventure-universe-admin | TypeScript | 3,563 | 1/3 | 2026-08-09 | Next.js admin API: user mgmt, room access control, moderation, OIDC |
| wtf / wtf-ionic | PHP/TS | 962/851 | 0/0 | 2024-01 | WTF project (dormant) |
| yo3an-yii2 / yo3an-ionic | PHP/TS | 81,411/155,569 | 0/0 | 2020-02 | Yo3an app (dormant) |

⑂ = fork. Full per-repo metadata cached at `/tmp/audit_cache/bawes-universe-repos.json`.

### BAWES user account (Khalid Al-Mutawa) — 183 repos (exact count via API)

**Original BAWES repos (non-fork) — the ones that matter for the ecosystem:**

| Repo | Lang | Size KB | Last push | What it is |
|---|---|---|---|---|
| **myfatoorah-php** | PHP | 27 | 2018-11-01 | **Standalone MyFatoorah PHP library** (`bawes/myfatoorah-php`, MIT, PSR-4) — getPaymentLinkAndReference, getOrderStatus, setPaymentMode, addProduct, setCustomer |
| **studenthub-codex** | TypeScript | 203,701 | 2026-06-24 | **SH Rebuild with Codex** — Next.js + Prisma modernization target, **129 Prisma models** (candidate_working_hour, appeal, bank_transaction, etc.) |
| studenthub-landing | HTML | 6,122 | 2026-05-14 | StudentHub landing |
| universe-imagine-music-mcp | Python | 33 | 2026-07-31 | Imagine Music via Ace Step |
| map-studio | TypeScript | 249 | 2026-05-19 | Map editor |
| tamr-mvp | TypeScript | 74 | 2025-11-19 | Tamr request collection MVP |
| orchestra-music | TypeScript | 258 | 2025-02-28 | Music app |
| tradesim-ai | JavaScript | 44,682 | 2025-03-20 | Next.js trading simulator |
| volunteer-training-app | TypeScript | 218 | 2025-09-09 | Volunteer training |
| sms-chatbot-ecommerce-yii2 | PHP | 170 | 2020-01-03 | Ecommerce chatbot backend (Yii2) |
| pogi-lambda | JavaScript | 613 | 2018-09-21 | Lambda functions used by Pogi |
| pogi-email-templates | HTML | 4,561 | 2021-09-08 | MJML email templates |
| ping-pong-link | JavaScript | 158 | 2026-05-21 | Real-time link game |
| travelnext | TypeScript | 78,719 | 2019-08 | Travel social app (dormant) |
| smartwealth | TypeScript | 3,931 | 2020-06 | Wealth app (dormant) |
| tribe | TypeScript | 114 | 2025-06 | Small app |
| map-starter-kit ⑂ | — | 4,758 | 2024-10 | WorkAdventure map starter kit |
| BAWES-virtual ⑂ | — | 55,919 | 2025-08 | Virtual office for SH with WorkAdventure |

**Notable infra forks under BAWES user** (candidate infrastructure the org evaluates — the "toolbox"): keycloak, livekit, janus-gateway, coolify, meilisearch, typesense, mem0, n8n, docuseal, documenso, gumroad, money (Shopify money class), nextjs-saas-starter-kit-lite, useSend, postiz-app, twenty, mastra, openpanel, rybbit, outline, penpot, metabase, minio, FerretDB, flaresolverr, firecrawl, scraperai, screenpipe, whisper-stream(ing), silero-vad, element-web, synapse, fluffychat, Rocket.Chat, chatwoot, tldraw, tiptap, lexical, motion, novel, xyflow, excalidraw, SpacetimeDB, keycloak, netbird, wg-easy, tunnelmole, mem0, langchain(js), helicone, langtrace, agentops, kittentts, OmniVoice-Studio, ace-step(+ui), heartlib, orchestra, AppFlowy, AFFiNE, classromio, strapi, twenty, mastra, sam (Sovereign Agent Mesh), paperclip, openpanel, rybbit, scalar, SurfSense, penpot, coolify, useSend, postiz-app(+agent), etc. (183 total; 100+83 paged).

~5 repos appear in both the org and the user account (BAWES-ERP, BAWES-ERP-frontend, documenso, n8n, plugn-landing) → **~247 distinct repos** across both namespaces.

---

## (b) Component Registry

| Component | Repo(s) | Language | API shape | Reusable? | Notes |
|---|---|---|---|---|---|
| **Tap Payments gateway** | plugn `common/components/TapPayments.php` (1,177 lines) | PHP/Yii2 | `setApiKeys(live,test,sandbox)` · `createCharge()` · `createRefund()` · `createBusiness()` · `createMerchantAccount()` · `createAnOperator()` · `createDCC()` · `fromApplePayToken()` · `retrieveCharge/Refund` · `checkTapSignature()` (webhook) | refactor-needed | God-component mixing marketplace merchant onboarding + charging + refunds + DCC. Gateway consts: KNET `src_kw.knet`, VISA/MC `src_card`, MADA `src_sa.mada`, BENEFIT `src_bh.benefit`; per-gateway fee config (knet 1%, mada/benefit 1.5%, cc 2.5%) |
| **MyFatoorah gateway** | plugn `common/components/MyFatoorahPayment.php` (565 lines) + standalone **BAWES/myfatoorah-php** | PHP | `setApiKeys(currency)` · `createCharge()` (w/ platform_fee, warehouse fees) · `makeRefund()` · `createSupplier/editSupplier` · `uploadSupplierDocument()` · `getSupplierDashboard()` · `retrieveCharge()` · `initiatePayment()` | yes (standalone lib) / refactor-needed (plugn comp) | Standalone lib is MIT PSR-4 `bawes/myfatoorah` (PHP≥5.4): `getPaymentLinkAndReference`, `getOrderStatus`. plugn comp adds supplier/payout model. Gateways: KNET, VISA/MC, AMEX, SADAD, MADA, UAE, Qatar, KFAST, Mezza, OmanNet |
| **Gateway abstraction (Stripe/Moyasar/Tabby/UPayment/ApplePay)** | plugn `agent/models/payment/{Stripe,Moyasar,Tabby,UPayment}.php`, `common/components/ApplePay.php`, controllers `api/modules/v2/controllers/payment/*` | PHP/Yii2 | Uniform `init()+save()` model per gateway; webhook controllers per gateway; `PaymentMethod` config views per gateway | refactor-needed | Each gateway = thin model class; clean target for a gateway-interface refactor (Stripe via stripe/stripe-php dep) |
| **Payment ledger** | plugn `common/models/Payment.php` | PHP/Yii2 AR | Fields: payment_uuid, order_uuid, gateway_order_id, gateway_transaction_id, payment_mode, current_status, amount_charged, net_amount, gateway_fee, vat, gateway_name, plugn_fee, payout_status, udf1-5; `SCENARIO_UPDATE_STATUS_WEBHOOK` | refactor-needed | Gateway-agnostic unified payment record; domain-coupled to order/restaurant |
| **Payment queue/retry** | plugn `common/models/PaymentGatewayQueue.php` (`processQueue()`), `TapQueue.php`, `PaymentFailed.php`, `TapError.php` | PHP/Yii2 | Queue AR with `processQueue()` + `afterSave` dispatch; error/retry tables w/ admin CRUD | refactor-needed | Battle-tested retry machinery for webhook/charge reconciliation |
| **Partner payouts** | plugn `common/models/PartnerPayout.php` + `backend/controllers/PartnerPayoutController.php` | PHP/Yii2 | Payout status machine (PENDING→UNPAID→PAID), transfer file upload (IBAN + benef fields), `getPayablePartnerListFormat()` | refactor-needed | Money-movement component; IBAN/transfer-file fields from migrations m210913–m210915 |
| **Wallet engine** | plugn `common/components/WalletManager.php`; studenthub `common/models/WalletUser/WalletTransfer/WalletBank.php` + `common/components/WalletManager.php` | PHP/Yii2 | `addEntry($data)` ledger; transfer status machine (INITIATED→IN_PROGRESS→TRANSFER_COMPLETE), `validateTotal()`, per-user wallets; `yii2tech/balance` dep in studenthub | refactor-needed | Two independent wallet impls — merge into one ledger service |
| **Invoicing** | studenthub `common/models/Invoice.php` + `InvoiceItem/InvoicePayment` (plugn) | PHP/Yii2 | Invoice + items + payments, `unpaidAlert()`, PDF via kartik mpdf, email attachments (`invoice-attachment.php`), console migrations for invoice schema | refactor-needed | studenthub=payroll invoices; plugn=store invoices. Shared shape |
| **Subscription / SaaS billing** | plugn `common/models/SubscriptionPayment.php`, `StoreDomainSubscriptionPayment.php`, `AddonPayment.php`; controllers + generate-invoice views | PHP/Yii2 | Per-store domain subscription payments, addons, subscription payment records w/ partner fee | refactor-needed | Platform monetization spine (plugn sold store subscriptions) |
| **Payroll/salary engine** | studenthub `common/models/StaffSalary.php`, `StaffSalaryProcess.php`, `MonthlySalaryContract.php`; `admin/.../StaffSalaryController.php`; migrations m210426/m220818/m230127 | PHP/Yii2 | Salary + batch process + monthly contracts; candidate working-hour models in codex Prisma (129 models) | refactor-needed | 10 years of payroll logic — the youth-training-program domain spine |
| **Hearth world engine** | hearth `server/` (Go) + `client/` (PixiJS PWA) + `media/` (Pion SFU) | Go/TS | Frozen JSON WS protocol v0 `{v,t,id,ts,d}`; `/ws` hub, 12Hz AOI state, REST `/api/spaces`; SFU w/ 20 pre-negotiated m-lines (12 audio+6 cam+2 screen), Top-K audio; bots speak same protocol | **yes** | Cleanest reusable asset: one binary, SQLite WAL, no SaaS. Live at hearthapp.bawes.net |
| **Spatial world fork** | workadventure-universe ⑂ + workadventure-universe-admin + universe-maps + scripting-api-extra ⑂ | TS | WA map/room model; admin API (OIDC, room access, moderation); LiveKit/Synapse compose variants | refactor-needed | Prod fork being replaced by Hearth; admin API is reusable |
| **Identity / OIDC** | oidc-authentik (blueprints + compose); plugn `common/components/Auth0.php`, `JWT.php`; workadventure-universe-admin OIDC | CSS/PHP/TS | Authentik blueprints, OIDC flows; Auth0 + JWT components for Yii2 | yes (authentik setup) / refactor-needed (components) | Standard OIDC; BAWES/user BAWES fork of keycloak as alternative |
| **Agent-facing data layer (MCP)** | studenthub-mcp (Python FastMCP, SELECT-only, pymysql); universe-imagine-mcp; universe-imagine-music-mcp | Python | MCP stdio/streamable-HTTP tools: `search_candidates`, `get_company_tree`, `search_interviews`…; hard LIMITs, parameterized SQL, read-only user | **yes** | Pattern for exposing legacy DBs to agents safely |
| **Brick onboarding machinery** | bawes-fleet (brick-packages, skills/, router/, vault/, ledger/, rate-card/, marketplace/, spawn-package, register-claim) | Python/md | Skill DNS, claim/ledger append-only, consensus rounds, PAT vault | yes (ops) / entangled (consensus) | Fleet operations stack; vault PAT handling is BAWES-internal |
| **Knowledge/search** | bawes-knowledge (docs library); studenthub Algolia dep (`algolia/algoliasearch-client-php`) | Python/PHP | Docs tree; Algolia search client wiring | yes | Knowledge base is docs-only; Algolia wiring in studenthub is candidate search |
| **Storefront** | plugn-store, plugn-store-community (Vue), plugn-store-sdk, plugn-store-* microservices (cloudfront/files/manifest, status-api, store-assistant) | Vue/JS | Store SDK + storefront + static-store infra microservices | refactor-needed | Multi-tenant storefront for ~8k stores |
| **Frontend shells** | studenthub-candidate-react (Ionic/React), studenthub-candidate-next, orbit-browser (Swift shell), BAWES-ERP-sdk (TS SDK) | TS/Swift | — | partial | ERP SDK = API-SDK pattern to copy |
| **SMS/call infra** | studenthub-pbx (Go), studenthub-microservices (yeastar-voicemails, yeastar-websocket-client, SQS), sms-chatbot-ecommerce-yii2 | Go/JS/PHP | Yeastar PBX websocket client; SQS workers | refactor-needed | Call-center + SMS automation |
| **Email templates** | pogi-email-templates (MJML) | HTML | MJML templates | yes | Copy-paste MJML email system |
| **Map/realtime helpers** | scripting-api-extra ⑂, map-studio, universe-maps | TS/HTML | WA scripting API extras | yes | Reusable for WA maps |

---

## (c) Commerce Integrations Detail — the payment/commerce spine

**Where all gateway code lives: `BAWES-Universe/plugn`** (Yii2 advanced template, PHP ≥8.2, multi-app: `api/ agent/ backend/ frontend/ crm/ partner/ store/ common/`). 273 payment-related paths in the repo tree.

### Gateways (exact paths)

| Gateway | Component class | Controllers | Storefront views | Status |
|---|---|---|---|---|
| **Tap Payments** | `plugn/common/components/TapPayments.php` (1,177 lines) | `backend/controllers/TapQueueController.php`, `TapErrorController.php`, `TapRequirementsController.php` | `frontend/views/store/create-tap-account.php`, `view-tap-rates.php`; `backend/views/restaurant/create_tap_account.php` | Live prod |
| **MyFatoorah** | `plugn/common/components/MyFatoorahPayment.php` (565 lines) + `BAWES/myfatoorah-php` (standalone MIT lib) | `api/modules/v2/controllers/PaymentController.php::actionMyFatoorahWebhook()` | `frontend/views/store/create-myfatoorah-account.php`, `view-myfatoorah-rates.php` | Live prod |
| Stripe | `agent/models/payment/Stripe.php`, `backend/models/payment/Stripe.php` | `api/modules/v2/controllers/payment/StripeController.php`, agent v1 | `backend/views/payment-method/config/stripe.php` | Configured |
| Moyasar | `agent/models/payment/Moyasar.php`, `backend/models/payment/Moyasar.php` | `api/modules/v2/controllers/payment/MoyasarController.php` | `backend/views/payment-method/config/moyasar.php` | Configured |
| Tabby | `agent/models/payment/Tabby.php` | `api/modules/v2/controllers/payment/TabbyController.php`, `agent/modules/v1/controllers/payment/TabbyController.php` | — | BNPL |
| UPayment | `agent/models/payment/UPayment.php` | `api/modules/v2/controllers/payment/UpaymentController.php` | — | Configured |
| Apple Pay | `common/components/ApplePay.php` (`registerMerchant($store)`) | `agent/modules/v1/controllers/payment/ApplePayController.php`, api v2 | — | Via Tap token |
| KNET (via Tap) | const in TapPayments | — | — | Gateway const `src_kw.knet` |

### Tap-specific machinery (the marketplace-grade part)
- **Merchant onboarding for marketplaces**: `TapPayments::createBusiness() → createMerchantAccount(company, currency, business_id, business_entity_id, iban) → createAnOperator(name, wallet_id, developer_id)` + `uploadFileToTap()` (KYC docs) + `updateBankAccount()` — i.e., full "create a seller on Tap and pay them out" flow.
- **Queue/retry/reconciliation**: `common/models/TapQueue.php` + `TapError.php` + `TapRequirements.php` (KYC requirements per country) + `PaymentGatewayQueue.php::processQueue()`; migrations `m201105_154957_create_tap_queue_table`, `m221009_093414_tap_response`, `m231102_100554_tap_merchant`, `m240522_083736_tap_requirements`, `m250129_050921_tap_error`; hotfix deploy script `environments/dev-railway/deployments/04_Aug_2025_tap_fix.sh`.
- **Webhook signature verification**: `TapPayments::checkTapSignature($toBeHashedString, $headerSignature)`.
- **Per-gateway fee engine**: gateway-fee constants (knet 1% min 0.1, mada/benefit 1.5%, creditcard 2.5%, minCharge 4) — platform fee math in `Payment` (plugn_fee + vat fields, migrations m201119_172315, m210621_121716).

### MyFatoorah specifics
- plugn component adds **supplier/payout model** (`createSupplier`, `editSupplier`, `uploadSupplierDocument`, `getSupplierDashboard`, platform_fee + warehouse_fee in `createCharge`) — same shape as Tap's merchant onboarding.
- Standalone `BAWES/myfatoorah-php/src/MyFatoorah.php` (MIT, PHP≥5.4, composer `bawes/myfatoorah-php`): `setPaymentMode`, `setCustomer`, `setReferenceId`, `setReturnUrl`, `setErrorReturnUrl`, `addProduct`, `getPaymentLinkAndReference`, `getOrderStatus` — clean minimal client; the right base for a modernized library.

### Payment orchestration flow
`PaymentController` (api v2) → gateway webhook (`actionMyFatoorahWebhook`) → `Payment` record (status machine w/ webhook scenario) → `PaymentGatewayQueue` retry → payout via `PartnerPayout` (IBAN transfer file) → wallet/settlement. Store-level gateway switching: `frontend/controllers/StoreController.php::actionSwitchToTap/actionSetupOnlinePayments/actionCreatePaymentGatewayAccount/actionViewTapRates`.

### Subscription billing (SaaS spine)
`StoreDomainSubscriptionPayment` + `SubscriptionPayment` + `AddonPayment` + `backend/views/store-domain-subscription/generate-invoice.php` — plugn sold stores domain subscriptions with invoicing; the monetization template for "sell tooling to builders".

---

## (d) TOP 10 Reusable Components — ranked by "build tooling → upsell service" potential

1. **GCC payment gateway layer (Tap + MyFatoorah + Stripe + Moyasar + Tabby + UPayment + Apple Pay)** — plugn. The single most valuable asset: 7 gateways, marketplace merchant onboarding, fee math, webhook verification. Tooling: a gateway-agnostic payments SDK/service → **upsell: payments-as-a-service for regional commerce** (Kuwait/GCC focus; KNET/MADA/BENEFIT/KFAST/Mezza/OmanNet/Qatar/UAE all covered).
2. **Marketplace merchant onboarding + payouts** — TapPayments createBusiness→createMerchantAccount→createAnOperator + PartnerPayout IBAN machinery. Tooling: "onboard a seller & pay them out" API → **upsell: marketplace/multi-vendor enablement**.
3. **Payment ledger + reconciliation queue** — Payment model (gateway fee/VAT/net/payout status, webhook scenario) + PaymentGatewayQueue/TapQueue retry. Tooling: unified payment ledger service → **upsell: reconciliation/finance ops for merchants**.
4. **Wallet & transfer engine** — plugn WalletManager + studenthub WalletUser/WalletTransfer (status machine, validateTotal) + yii2tech/balance. Tooling: wallet API → **upsell: wallet-as-a-service** (payroll, payouts, balances).
5. **Invoicing + PDF + email** — studenthub Invoice/plugn InvoiceItem/InvoicePayment + kartik mpdf + mail templates. Tooling: invoice generator → **upsell: invoicing SaaS**.
6. **Subscription/domain billing** — StoreDomainSubscriptionPayment/SubscriptionPayment/AddonPayment. Tooling: billing engine → **upsell: SaaS subscription management for builders** (plugn's own monetization pattern).
7. **Payroll & salary engine** — StaffSalary/StaffSalaryProcess/MonthlySalaryContract + candidate_working_hour (129-model Prisma schema in studenthub-codex). Tooling: payroll API for gig/youth programs → **upsell: payroll platform** (Kuwait youth-training market).
8. **Hearth spatial engine + embedded Pion SFU** — the cleanest, most modern asset. Tooling: spatial world SDK w/ voice bubbles + bot protocol → **upsell: virtual spaces / events / office products**.
9. **Identity/OIDC stack** — oidc-authentik blueprints + Auth0/JWT components + admin OIDC. Tooling: SSO bootstrap kit → **upsell: managed identity for store builders**.
10. **Agent-facing data layers (MCP pattern)** — studenthub-mcp (SELECT-only FastMCP), universe-imagine-mcp, universe-imagine-music-mcp. Tooling: "legacy DB → MCP" generator → **upsell: AI-readiness layer for enterprises** (khalid's Anthropic/OpenAI-competitor ambition: solid frontends over agent-ready data).

Honorable mentions: storefront SDK (plugn-store-sdk + Vue storefront + static-store microservices), MJML email templates, SMS/PBX infra (studenthub-pbx + yeastar workers), ERP API SDK pattern (BAWES-ERP-sdk), brick/fleet ops (bawes-fleet).

---

## (e) Honest Gaps — what can't be extracted without refactor

- **Yii2 entanglement**: all plugn/studenthub components extend `yii\base\Component` / `ActiveRecord` and are wired via `common/config/main.php` + per-environment `main-local.php` (gateway keys injected per env). Extraction = composer-package refactor with interface layers, not copy-paste.
- **Domain coupling in the ledger**: `Payment` FK to `restaurant_uuid`/`order_uuid` (food-delivery domain); `PartnerPayout` FK to restaurant/partner. The generic core (uuid, gateway fields, fees, status) is separable; the FKs are not.
- **God-components**: `TapPayments.php` (1,177 lines) mixes merchant onboarding, charging, refunds, DCC, tokenization — needs splitting into a client + domain services before reuse.
- **Secret handling**: gateway keys are env-config values (`environments/*/common/config/main-local.php` — redacted here, but present in-repo; treat as compromised for rotation planning). No vault/secret-manager integration in plugn.
- **Test coverage thin**: fixtures exist for Payment/TapQueue/PaymentGatewayQueue, but gateway classes have no unit tests (no mock HTTP). Reuse requires building a test harness.
- **No standalone SDK for plugn APIs**: `plugn-store-sdk` is 47KB and minimal; `BAWES-ERP-sdk` (11MB) shows the desired pattern.
- **tamr** clone returns 403 even with the PAT (repo-level restriction) — metadata only.
- **studenthub-codex is a work-in-progress migration target**, not a shippable product: 129 Prisma models but execution plan (`docs/migration/nextgen-execution-plan.md`) still in flight; Yii2 remains the reference.
- **workadventure-universe fork** (211MB) is being replaced by Hearth; its LiveKit/Synapse/OIDC compose stack is reusable, the app itself is legacy.
- **BAWES user account** (183 repos) is mostly forks — valuable as an evaluated-infrastructure list, but fork provenance means licensing/upstream drift must be checked per repo before productizing.
- **Commerce schema sprawl**: 30+ payment migrations from 2020–2025 with incremental field adds — a clean `commerce_core` schema needs to be designed, not mined.

---

*Catalog generated 2026-08-24 by fleet research subagent. API data cached: `/tmp/audit_cache/bawes-universe-repos.json`, `bawes-user-repos-p2.json`, `*-tree.json`. Shallow clones: `/srv/research/repos/{plugn,studenthub,studenthub-codex,myfatoorah-php,hearth,bawes-fleet,bawes-knowledge,wallet,studenthub-mcp,plugn-microservices,studenthub-microservices,oidc-authentik,stencil,smartcar,orbit-browser,workadventure-universe-admin,universeos}`.*
