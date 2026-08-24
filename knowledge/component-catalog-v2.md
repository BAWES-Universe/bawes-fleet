# BAWES Reusable Component Catalog

**Org:** `BAWES-Universe` (69 public repos) · **Crawl date:** 2026-08-24 · **Span:** 2017 → 2026
**Method:** GitHub API metadata (all 69 repos) + git trees (18 repos), READMEs (40+), and targeted source inspection of payment/auth/wallet files. Every capability below is backed by observed file paths or repo descriptions — nothing invented. Items inferred from name/language only are marked **(inferred)**.

**Maturity legend:** 🟢 prod/active · 🟡 maintained-but-idle · 🟠 dormant · 🔴 prototype/experiment · ⚫ archive/fork · ⛔ access-blocked

**Context note:** The companion org `BAWES` holds `studenthub-codex` (Next.js + Prisma StudentHub modernization — not in this org's list). Per `UniverseOS` README, the sanctioned direction is "one login, one wallet, one assistant, one world" merging WorkAdventure-universe + Authentik OIDC + StudentHub + Plugn ("the commerce spine, 8,000 stores") + Yo3an ("the food data layer") onto Fly.io.

---

## 1. 💳 Payments: Tap (crown jewel)
**The most battle-tested payment-gateway integration in the fleet.**
- **Repos:** `plugn` (primary), `wallet`
- **Stack:** PHP / Yii2 components
- **Evidence:** `plugn/common/components/TapPayments.php` (test/live switch, direct KNET portal link `src_kw.knet`, ApiLog integration); full merchant-onboarding pipeline: `TapQueue` model+cron table (`m201105_create_tap_queue_table`), `TapRequirements` (+2024 migration), `TapError` (+2025 migration), per-restaurant `create-tap-account.php` views, tap-approved/rejected mail templates; `wallet/common/components/TapPayment.php` + `frontend/controllers/payment/TapController.php`; Tap UI models in `plugn-dashboard-ionic` (`tap-requirements.ts`)
- **Maturity:** 🟢 prod (migrations through 2025-02; Plugn runs 8,000 stores per UniverseOS)
- **Reuse:** Drop-in Yii2 Tap charge/authorize/refund component with merchant onboarding, queue + error handling for any Kuwait-market marketplace.

## 2. 💳 Payments: MyFatoorah
- **Repos:** `plugn`
- **Stack:** PHP / Yii2
- **Evidence:** `common/components/MyFatoorahPayment.php` (test/live switch, KNET `kn` + VISA/MASTER direct links); store views `create-myfatoorah-account.php`, `view-myfatoorah-rates.php`
- **Maturity:** 🟢 prod within plugn
- **Reuse:** Same-shape gateway component as Tap — add MyFatoorah checkout to any Yii2 app in hours.

## 3. 💳 Payments: Stripe (+ refunds & invoicing)
- **Repos:** `plugn`, `pogi`, frontends: `plugn-store*`, `plugn-ionic`, `plugn-dashboard-ionic`
- **Stack:** PHP (Yii2) server-side; TS/Vue client services
- **Evidence:** `plugn/api/modules/v2/controllers/payment/StripeController.php`, `backend/models/payment/Stripe.php`; `pogi/common/models/StripePayment|StripeRefund|StripeSource.php` + `employer/modules/v1/controllers/payment/StripeController.php`; client `services/payment/StripeService.ts` in all three store frontends; `stripe-form` Ionic component ×2
- **Maturity:** 🟢 prod in plugn; 🟠 dormant in pogi (last push 2023)
- **Reuse:** Card payments with refund lifecycle (cron `make-refund`, Refund/RefundedItem models) for any product.

## 4. 💳 Payments: Regional gateways — Moyasar, Tabby, UPayment, Apple Pay, KNET
- **Repos:** `plugn` (server), `plugn-store`, `plugn-store-community`, `plugn-store-sdk`, `plugn-ionic`, `plugn-dashboard-ionic`, `wallet`
- **Stack:** PHP controllers/models + TS/Vue service classes
- **Evidence:** `agent/models/payment/{Moyasar,Stripe,Tabby,UPayment}.php`, `api/modules/v2/controllers/payment/{ApplePay,Moyasar,Tabby,Upayment}Controller.php`; client `MoyasarService.ts`, `TabbyService.ts`, `ApplePayService.ts` in every storefront; KNET icon assets across frontends
- **Maturity:** 🟢 prod (KSA Moyasar + BNPL Tabby + Apple Pay live in storefronts)
- **Reuse:** The complete Gulf-region gateway matrix (KNET/Moyasar/Tabby/UPayment/ApplePay) already abstracted behind a common PaymentMethod model.

## 5. 🛒 E-commerce storefront & checkout platform
- **Repos:** `plugn-store` (Vue, prod), `plugn-store-community` (Vue, open-source edition), `plugn-ionic` (TS mobile), `plugn-store-sdk` (JS/TS SDK), `plugn-microservices` (edge/services)
- **Stack:** Vue 3 / Ionic-Angular / TypeScript SDK / Node+Go edge services
- **Evidence:** Full checkout flow pages (Cart→CustomerInfo→DeliveryTo→ScheduleOrder→Confirm→Payment) identical across store frontends; `PlugnStoreConfig` SDK interface (baseURL/storeId/language/currency/cart/customerInfo) targeting `api.plugn.io/v2`; microservice sidecars `plugn-store-cloudfront/-files/-manifest`
- **Maturity:** 🟢 prod (`plugn-store`) · 🟡 community edition · 🟡 SDK
- **Reuse:** White-label a multi-vendor food/retail store app with payments, scheduling, gifting and delivery zones out of the box.

## 6. 👛 Wallet / balance-ledger service
- **Repos:** `wallet` (service), `studenthub` (consumer), `stencil` (UI kit)
- **Stack:** PHP Yii2 (wallet) · Yii2 HTTP client (consumer) · Stencil web components (UI)
- **Evidence:** wallet exposes REST at `https://webhook.wallet.bawes.net/v1` — consumed by `studenthub/common/components/WalletManager.php` (`addEntry(amount, tags, user_uuid)`); wallet models `BalanceTransaction(+Tag)`, top-up & pay-by-wallet forms, Excel bulk import/distribute, KYC SQL init; Tap+Moyasar top-ups
- **Maturity:** 🟢 prod (live endpoint referenced by active StudentHub code)
- **Reuse:** A working central ledger with top-up, distribution, tagging and bank records — make any product wallet-enabled by calling one API.

## 7. 🧾 Subscriptions, invoices & billing admin
- **Repos:** `plugn`, `wallet`, `pogi`, `studenthub`
- **Stack:** PHP Yii2
- **Evidence:** `Subscription/SubscriptionPayment/StoreDomainSubscription(Payment)` stacks in plugn backend; `Subscription` + `Invoice` models in wallet/pogi/studenthub; invoice PDF layouts in 4 apps; employer job-invoice mail templates in pogi
- **Maturity:** 🟢 prod (plugn/studenthub) · 🟠 pogi
- **Reuse:** Recurring-billing + invoice-PDF machinery proven across two production systems.

## 8. ⏱️ Time-tracking & payroll (StudentHub core)
- **Repos:** `studenthub` (Yii2 monorepo: admin/candidate/company/inspector/manager/staff/status/verification tiers), frontends `studenthub-candidate(-react,-next)`, `-company`, `-staff`, `-admin`, `-manager`, `-finance`, `-team`, `-inspector`, `studenthub-personas`
- **Stack:** PHP Yii2 multi-tier API + Ionic Angular mobile + React/Next.js web
- **Evidence:** README "trainee placement, time tracking, and payment processing"; `time_tracker` + `attendance` migrations, `docs/database/models/work/timesheet.md`, attendance-sheet mail; company app "log hours, generate invoices" (repo desc); finance/team apps for reports
- **Maturity:** 🟢 prod, actively developed (pushed 2026-08; topic `core`); modernization tracks: `studenthub-candidate-react` (Next.js, multi-step registration + doc uploads incl. Civil ID) and external `BAWES/studenthub-codex`
- **Reuse:** End-to-end youth-payroll: placement → hour logging → approval → company invoicing → candidate payout, plus 8 role-specific frontend shells.

## 9. 🎯 Recruitment / candidate CRM
- **Repos:** `studenthub`, `studenthub-mcp`
- **Stack:** PHP Yii2 + Python MCP
- **Evidence:** candidates/requests/applications/universities/companies domain (verified schema notes in studenthub-mcp README: UUID PKs, `request_application`, masked phones); verification tier for document checks
- **Maturity:** 🟢 prod
- **Reuse:** Structured hiring-pipeline data model with university/country dimensions and doc verification flow.

## 10. 🤖 Read-only MCP data-layer pattern
- **Repos:** `studenthub-mcp` (reference implementation), `universe-imagine-mcp` (image-gen MCP)
- **Stack:** Python (Streamable HTTP MCP)
- **Evidence:** SELECT-only safety contract, hard row caps, dedicated read-only MySQL user, probe.py handshake test; imagine-MCP wraps ComfyUI with bearer auth + queue (`designer_mcp.py`)
- **Maturity:** 🟢 active (2026-08)
- **Reuse:** The safest known-good recipe for exposing any BAWES database to AI agents without write risk.

## 11. ☎️ Call-center / PBX integration
- **Repos:** `studenthub-pbx` (Go CDR sync), `studenthub-microservices` (Yeastar services)
- **Stack:** Go + Node.js
- **Evidence:** pbx README: sync call history, save recordings to AWS S3, set S3 path in CDR report, filtered history APIs; microservices tree: `yeastar-websocket-client`, `yeastar-voicemails`, plus `SQS`, `linear`, `process-id-request`, `proxy-manager`
- **Maturity:** 🟠 dormant (pbx 2024) but microservices pushed 2026-08 🟡
- **Reuse:** Yeastar PBX → S3 recordings → queryable call-history API pipeline; also reusable SQS workers and Linear issue sync.

## 12. 💼 Jobs marketplace (Pogi)
- **Repos:** `pogi` (Yii2 backend), `pogi-jobs` (seeker app), `pogi-employer` (employer app), `pogi-admin`, `pogi-postman` (API collections)
- **Stack:** PHP Yii2 + Ionic Angular/Capacitor
- **Evidence:** employer/candidate/admin modules, Stripe billing for employers (see §3), Algolia job search (see §14), Postman backup of full API
- **Maturity:** 🟠 dormant (backend 2023, frontends 2021)
- **Reuse:** Two-sided jobs board with subscriptions, search and signed mobile apps — resurrect as-is or mine its Postman collection.

## 13. 🍔 Food/restaurant ordering (Yo3an)
- **Repos:** `yo3an-yii2`, `yo3an-ionic`
- **Stack:** PHP Yii2 + Ionic Angular + Firebase (firestore rules/functions, FCM)
- **Evidence:** models `Restaurant, Cuisine, DeliveryArea, Item, ExtraOption, Vendor, Area/City/Country`; Firebase config in mobile app; algolia-diag script
- **Maturity:** 🟠 dormant (2020) but named "food/restaurant data layer" in UniverseOS merge plan
- **Reuse:** Restaurant/catalog/delivery-zone schema ready to feed any food product.

## 14. 🔍 Search indexing (Algolia pattern)
- **Repos:** `pogi`, `studenthub`, `yo3an-yii2`
- **Stack:** PHP Yii2 component + console sync
- **Evidence:** identical `common/components/Algolia.php` + console `AlgoliaController` reindexers in all three; staff app uses expiring Algolia keys
- **Maturity:** 🟢 pattern proven in prod (studenthub active)
- **Reuse:** Copy one component + cron controller to give any Yii2 app instant search.

## 15. 🏦 ERP core: banking, RBAC, OpenAPI SDK
- **Repos:** `BAWES-ERP` (NestJS), `BAWES-ERP-sdk` (generated TS SDK), `BAWES-ERP-frontend` (Next.js + shadcn/ui)
- **Stack:** NestJS + Prisma + JWT; TypeScript SDK auto-generated from OpenAPI (`swagger.json` committed)
- **Evidence:** src/auth (21 files), src/rbac (21), person, cache, health modules; docs/integrations/banking incl. ABK account statements/bank-output; seeded banks data; multi-currency + financial reporting per README
- **Maturity:** 🟡 built 2024-25, idle since 2025-06
- **Reuse:** Modern auth/RBAC skeleton + the generate-SDK-from-OpenAPI workflow + banking-statement integration docs.

## 16. 🔐 Identity / SSO (Authentik OIDC)
- **Repos:** `oidc-authentik` (deployment/theme), `universe-matrix-synapse` (consumer), `workadventure-universe-admin` (consumer)
- **Stack:** Authentik + CSS theme; Shell deploy scripts
- **Evidence:** "OIDC implementation using Authentik"; Synapse configured registration-through-OIDC-only; admin API does user authz via OIDC
- **Maturity:** 🟢 prod (chat.bawes.net live per synapse README)
- **Reuse:** One-login-for-everything backbone that UniverseOS designates as the identity lane.

## 17. 🌍 Virtual worlds / spatial collaboration
- **Repos:** `workadventure-universe` (fork, 12 services), `workadventure-universe-admin` (Next.js admin API: rooms, woka avatars, bans, moderation), `universe-maps` (map starter-kit maps), `scripting-api-extra` (fork, map-scripting utils), `hearth` (from-scratch successor)
- **Stack:** TypeScript + Go (hearth: single Go binary + PixiJS PWA + Pion SFU spatial audio + bots-as-peers protocol v0)
- **Maturity:** 🟡 fork maintained · 🟢 hearth very active (2026-08-24) · 🟢 admin active
- **Reuse:** Either adopt hearth's frozen wire protocol + guest-first world engine, or run the WorkAdventure fork with its universe admin/moderation layer.

## 18. 💬 Chat infrastructure
- **Repos:** `universe-matrix-synapse`, `hearth` (in-world chat/DM), `universe-imagine-mcp` n/a
- **Stack:** Matrix Synapse on Railway + PostgreSQL + S3 media + OIDC
- **Maturity:** 🟢 prod
- **Reuse:** Production-ready federated chat with SSO and cheap S3 media store.

## 19. 🧠 AI/LLM microservices
- **Repos:** `plugn-microservices` (`openai-file-search` Node assistant+vector-store API, `store-assistant`/`store-assistant-literalai` Chroma-RAG shopping assistant with LiteralAI observability, `openai-cities` Go prompt service), `universe-imagine-mcp` (ComfyUI image gen), forks: `self-hosted-ai-starter-kit`, `n8n`
- **Stack:** Node/Express + Chroma + OpenAI; Go; ComfyUI
- **Maturity:** 🟠 dormant (2025-02) but complete reference RAG stack · 🟢 imagine-mcp active
- **Reuse:** Working e-commerce AI assistant with vector search + observability; workflow automation via n8n fork.

## 20. 🧩 Framework-agnostic UI components (Stencil)
- **Repo:** `stencil`
- **Stack:** Stencil web components (framework-agnostic, unit+E2E tested)
- **Evidence:** 26 components incl. full wallet suite (balance, send-money, distribute, loan, transactions, login/register/recover…), jira-issues, jira-team, studenthub-stats, team-salary, xero-profit, plugn-stores
- **Maturity:** 🟠 dormant (2022) but tests included
- **Reuse:** Drop `<wallet-send-money>` etc. into any web app to get wallet UI instantly.

## 21. 📊 Reporting: Excel import/export + PDF rendering
- **Repos:** `studenthub` (Excel, PhpExcel, TransferRateExcel, PDF view layouts), `wallet` (WalletExcel/TransferExcel import+distribute UI), `plugn`, `pogi`
- **Stack:** PHP (PhpSpreadsheet-family + mpdf-style layouts)
- **Maturity:** 🟢 prod patterns
- **Reuse:** Bulk money-distribution via uploaded Excel + branded PDF invoices/certificates (incl. candidate appreciation certificates).

## 22. 🌐 Arabic/i18n & RTL commerce UX
- **Repos:** `plugn` family (messages-ar, ar-SA configs in store frontends + dashboard)
- **Maturity:** 🟢 prod (Kuwait market, KWD currency defaults in SDK)
- **Reuse:** Battle-tested bilingual (ar/en) storefront conventions incl. RTL quirks documented in app READMEs.

## 23. 📱 Mobile-app shell & release toolchain (Ionic/Angular/Capacitor)
- **Repos:** `plugn-ionic`, `plugn-dashboard-ionic`, `studenthub-*` mobile apps, `tamr-user/provider/staff/admin`, `wtf-ionic`, `pogi-*`, `yo3an-ionic`, `whitebook-mobile` (Ionic v2)
- **Evidence:** signing-key docs, OneSignal push integration, deep-linking notes, ngsw PWA config, Apple auth keys
- **Maturity:** 🟢 pattern current (studenthub-staff 2026-08)
- **Reuse:** One consistent Capacitor pipeline: push, deeplinks, keystore management, PWA fallback.

## 24. 📣 Marketing sites & programmatic video
- **Repos:** `bawes-new-website` (Next.js WebGL/Framer-motion brand site), `bawes-landing` (v0.app/Vercel), `music-videos-remotion` (Remotion render pipeline), `plugn-landing`, `studenthub-personas` (Vite+Tailwind persona pages, GH Pages Actions deploys)
- **Maturity:** 🟢 new-website/personas active 2026 · 🟡 rest
- **Reuse:** Animated brand-site template and code-driven music-video generation.

## 25. 🐝 Fleet operations meta-platform
- **Repos:** `bawes-fleet` (skill DNS, task cards, claims ledger, rate card, marketplace schemas + CI guardrails), `bawes-knowledge` (public knowledge library + decisions ledger), `bawes-doc-updater` (SpinAI Mintlify doc updater)
- **Stack:** Python validators, JSON schemas, PR-gated workflows
- **Maturity:** 🟢 very active (daily pushes)
- **Reuse:** A complete agent-fleet governance model: who-can-do-what registry, claim→verify→close loop, append-only decision ledger.

## 26. 🖥️ Universe OS / deployment fabric
- **Repos:** `UniverseOS` (compose/deploy/fly.toml + docs + critiques), `orbit-browser` (hardened shell-browser monorepo: Vite/React PWA + macOS/iOS shells), `hearth` (runtime)
- **Maturity:** 🟢 active (2026-08)
- **Reuse:** The merge blueprint (lanes→repos table) + hardened-browser shell scaffolding for kiosk-style Universe clients.

## 27. ⛓️ Blockchain experiment (Cosmos SDK)
- **Repo:** `Bawesnet00-Blockchain`
- **Stack:** Go Cosmos-SDK chain (`app/`, `cmd/`, `proto/`, `x/` modules) + generated `ts-client` + Vue frontend
- **Maturity:** 🔴 prototype/dormant (2022)
- **Reuse:** Skeleton Cosmos chain with TS client generation if tokenization ever returns.

## 28. 🚗 Connected-car integration (smartcar.com)
- **Repo:** `smartcar` (Next.js Netlify app)
- **Evidence:** README TODOs show OAuth window/token-refresh work-in-progress
- **Maturity:** 🔴 prototype/dormant (2024)
- **Reuse:** Starting point only — OAuth connect flow for vehicle data (inferred from name + TODO state).

## 29. 📅 Productivity infra forks (run, don't build)
- **Repos:** `cal.com` (scheduling), `documenso` (e-signature), `n8n` (automation), `self-hosted-ai-starter-kit`, `workadventure-universe`, `scripting-api-extra`
- **Maturity:** ⚫ forks, pinned 2024-25
- **Reuse:** Pre-vetted self-hosted versions of scheduling/e-sign/automation — deploy rather than rebuild these capabilities.

## 30. ❓ Misc / unclassified
- `wtf` + `wtf-ionic` — metaverse Q&A/feedback app (models `Query`, `QuerySolution`); 🟠 dormant 2024
- `whitebook` + `whitebook-mobile` — event-planning platform, Kuwait launch (2017-19, oldest repos); ⚫ legacy
- `plugn-device` — Java-labeled, npm+android structure (inferred: device/companion lib); 🔴 unclear, dormant since 2022
- `universe-maps` — WorkAdventure map starter-kit maps (HTML); 🟡
- `.github` — org-level profile/config; ⚫ housekeeping
- `pogi-postman` — Postman collection backup for Pogi API; ⚫ archive

---

## Appendix A — Capability → Repo matrix (all 71 entries incl. 2 not in crawl brief)

| Repo | Lang | Last push | Capabilities |
|---|---|---|---|
| bawes-fleet | Python | 2026-08-24 | §25 fleet ops |
| hearth | Go | 2026-08-24 | §17 worlds, §18 chat |
| bawes-knowledge | Python | 2026-08-23 | §25 knowledge/decisions |
| workadventure-universe (fork) | TS | 2026-08-22 | §17 |
| studenthub-microservices | JS | 2026-08-20 | §11 PBX/Yeastar, SQS, Linear |
| studenthub-candidate-react | TS | 2026-08-19 | §8 modern frontend |
| studenthub-candidate-next | TS | 2026-08-19 | §8 (inferred: Next.js port) |
| studenthub | PHP | 2026-08-18 | §6,7,8,9,14,21 |
| orbit-browser | Swift/TS | 2026-08-15 | §26 browser shell |
| UniverseOS | Dockerfile | 2026-08-14 | §26 merge blueprint |
| studenthub-staff | TS | 2026-08-13 | §8, §23 |
| studenthub-mcp | Python | 2026-08-11 | §10 read-only MCP |
| bawes-new-website | TS | 2026-08-10 | §24 |
| workadventure-universe-admin | TS | 2026-08-09 | §16,§17 admin/moderation |
| universe-imagine-mcp | Python | 2026-07-17 | §10,§19 ComfyUI |
| studenthub-candidate | TS | 2026-07-06 | §8 mobile (OneSignal push) |
| BAWES-ERP-frontend | TS | 2026-06-21 | §15 |
| studenthub-company | TS | 2026-06-04 | §8 hours+invoices |
| studenthub-admin | TS | 2026-06-04 | §8 admin portal |
| .github | — | 2026-05-18 | org config |
| bawes-landing | TS | 2026-05-15 | §24 |
| plugn-dashboard-ionic | TS | 2026-02-25 | §3,4 commerce admin UI |
| tamr-admin | TS | 2026-02-25 | Tamr admin (Ionic) |
| studenthub-manager | TS | 2026-02-25 | §8 |
| studenthub-personas | JS | 2026-02-12 | §24 |
| music-videos-remotion | TS | 2026-02-12 | §24 Remotion |
| pogi-admin | TS | 2026-01-29 | §12 |
| universe-maps | HTML | 2025-12-29 | §17 maps |
| universe-matrix-synapse | Shell | 2025-12-18 | §16,§18 |
| oidc-authentik | CSS | 2025-12-17 | §16 |
| plugn | PHP | 2025-11-05 | §1-4,7,13-like commerce core,14,21,22 |
| plugn-landing | HTML | 2025-11-04 | §24 |
| scripting-api-extra (fork) | — | 2025-09-24 | §17 map scripting |
| plugn-store | Vue | 2025-08-20 | §3,4,5,22 |
| plugn-ionic | TS | 2025-08-20 | §3,4,5,23 |
| BAWES-ERP-sdk | TS | 2025-06-08 | §15 SDK |
| plugn-store-sdk | JS | 2025-04-07 | §3,4,5 SDK |
| cal.com (fork) | — | 2025-04-06 | §29 |
| documenso (fork) | — | 2025-04-06 | §29 |
| tamr-staff | TS | 2025-03-13 | Tamr staff app |
| tamr-provider | JS | 2025-03-12 | Tamr provider app |
| tamr | PHP | 2025-03-12 | Tamr backend ⛔ ToS-blocked (content inaccessible since 2026-01-20; desc only) |
| tamr-user | TS | 2025-03-12 | Tamr user app |
| wallet | PHP | 2025-03-10 | §1,4,6,7,21 |
| plugn-microservices | JS/Go | 2025-02-20 | §5 edge, §11, §19 AI services |
| bawes-doc-updater | TS | 2025-02-20 | §25 docs automation |
| BAWES-ERP | TS | 2025-01-13 | §15 |
| plugn-shadcn-dashboard | TS | 2024-11-14 | §5 dashboard (prototype scaffold) |
| n8n (fork) | — | 2024-10-07 | §29 |
| self-hosted-ai-starter-kit (fork) | — | 2024-09-24 | §29 |
| smartcar | JS | 2024-08-19 | §28 |
| plugn-store-community | Vue | 2024-07-23 | §5 OSS edition |
| studenthub-pbx | Go | 2024-03-17 | §11 CDR/S3 |
| wtf-ionic | TS | 2024-01-16 | §30 |
| wtf | PHP | 2024-01-15 | §30 |
| pogi | PHP | 2023-12-03 | §3,12,14 |
| studenthub-team | TS | 2023-03-06 | §8 reports/teams |
| studenthub-finance | TS | 2023-03-06 | §8 finance |
| Bawesnet00-Blockchain | TS/Go | 2022-12-29 | §27 |
| stencil | TS | 2022-12-19 | §20, §6 UI |
| plugn-device | Java | 2022-02-26 | §30 (inferred) |
| pogi-jobs | TS | 2021-05-20 | §12 |
| studenthub-inspector | TS | 2021-03-23 | §8 inspections |
| pogi-employer | TS | 2021-02-19 | §12 |
| pogi-postman | — | 2021-02-07 | §12 API collections |
| yo3an-yii2 | PHP | 2020-02-22 | §13,14 |
| yo3an-ionic | TS | 2020-02-22 | §13 (Firebase/FCM) |
| whitebook | JS | 2018-01-02 | §30 events |
| whitebook-mobile | TS | 2017-09-11 | §30 |

## Appendix B — Top reuse picks (if you build only 5 things)
1. **Tap + MyFatoorah + Moyasar/Tabby/UPayment gateway components** (`plugn`, `wallet`) — years of production hardening incl. onboarding queues.
2. **Wallet ledger service + webhook API + Stencil wallet UI** (`wallet`, `stencil`, `studenthub` consumer).
3. **StudentHub payroll/recruitment monorepo + role apps + read-only MCP pattern** (`studenthub*`).
4. **Multi-tenant storefront + checkout + SDK + edge services** (`plugn-store*`, `plugn-microservices`).
5. **Hearth world engine + Authentik OIDC + Synapse chat** (`hearth`, `oidc-authentik`, `universe-matrix-synapse`) — the UniverseOS stack.
