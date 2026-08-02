# MS2.0 Master Live Testing Sequence

Canonicalized: 2026-07-28

This is the single authoritative roadmap for all MS2.0 owner live validation. Future Codex chats and ChatGPT/Codex Bridges must derive checkpoint order and status only from this document. Project Brain, Engineering Memory, architecture documents, handoffs and historical plans provide evidence; they must point here and must not maintain a competing sequence.

Allowed capability classifications are exactly: `PASS / PROTECTED`, `Implemented — awaiting owner live test`, `Partial implementation`, `Planned / approved`, `External qualification`, `Deprecated with repository evidence`, and `Intentionally out of scope with repository evidence`. Numbered checkpoints use the first six states; an out-of-scope item is recorded in the completeness ledger below and is never silently converted into a checkpoint. A PASS requires owner evidence. Automated tests alone never create protected status.

Evidence abbreviations: `CVS` = `docs/engineering-memory/current-live-validation-state.md`; `LATP` = `ms20-main-app/LIVE_APP_TEST_PLAN.md`; `ARCH` = `ms20-main-app/CURRENT_ARCHITECTURE_SNAPSHOT.md`; `OI` = `docs/engineering-memory/operating-intelligence-program.md`; `TCE` = `docs/engineering-memory/transaction-completion-engine.md`; `OM` = `ms20-main-app/MS20_ONBOARDING_AND_OPERATIONS_INTELLIGENCE.md`; `TRAIN` = `training/LIVE_TEST_PLAN.md` and `training/PHASE_STATUS.md`.

## 1. Core Functional Validation

| # | Checkpoint | Objective | Prerequisite(s) | Implementation state | Owner validation | Protected | Est. live test | Evidence/document source |
|---:|---|---|---|---|---|---|---|---|
| 1 | Main App shell and navigation | Open Home, Assistant, Notifications, Catalog and Payment Queue without unintended mutation. | None | PASS / PROTECTED | Passed | Yes | 5 min | CVS; ARCH; `verify-architecture.mjs` |
| 2 | First-run owner setup | Complete the short owner/pharmacy setup and enter medicine onboarding safely. | 1 | PASS / PROTECTED | Passed | Yes | 8 min | CVS; OM; `pharmacy_onboarding.py`; onboarding tests |
| 3 | Invoice onboarding and local OCR | Capture/read invoices, review every row, correct, approve once and preserve row/order/provenance. | 2 | PASS / PROTECTED | Passed | Yes | 15 min | CVS; `invoice-table-ocr.md`; invoice fixtures/tests |
| 4 | Bulk paste onboarding | Parse clean, mixed and all-existing lists; review before save and prevent duplicates. | 2 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; LATP; paste fixtures; catalog verifiers |
| 5 | CSV onboarding | Import canonical CSV, map fields, reorder rows, review and persist without duplicates. | 2 | PASS / PROTECTED | Passed | Yes | 12 min | CVS; CSV fixture/verifier |
| 6 | XLSX onboarding | Read modern XLSX locally, review, approve, refresh and reject repeat duplicates; fail honestly for XLS. | 2 | PASS / PROTECTED | Passed | Yes | 12 min | CVS; Test 5 fixture/verifier |
| 7 | Barcode onboarding | Resolve registered Source Brain barcodes, block unknown barcodes and preserve canonical traceability. | 2 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; barcode fixtures/verifiers |
| 8 | Shelf-photo onboarding | Support gallery and camera, orientation/retry, multi-row review, approval and duplicate safety. | 2 | PASS / PROTECTED | Passed | Yes | 15 min | CVS; shelf fixtures/verifier |
| 9 | Medicine-pack photo onboarding | Capture upright/sideways pack evidence, retain provenance, unknowns and approval safety. | 2 | PASS / PROTECTED | Passed | Yes | 12 min | CVS; medicine-photo fixture/verifier |
| 10 | Catalog browse/search/edit | Browse 35 canonical medicines, search safely, edit one draft, approve/discard, persist and retain compact audited activity history. | 2 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; Catalog Search Mic and Activity Compaction evidence; catalog/activity verifiers |
| 11 | Shared medicine review integrity | Preserve canonical fields, progressive mobile cards, row controls, validation and review-before-mutation. | 3–10 | PASS / PROTECTED | Passed | Yes | 12 min | CVS; shared-field/readiness/reordering verifiers |
| 12 | Shared voice capture and review | Handle permission/start/listen/transcript/recovery and produce deterministic review-first commands. | 1 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; Mic Test 2; voice verifiers |
| 13 | Editable-card voice viewport/focus | Keep an inline Mic reachable beside any field and preserve the exact target/viewport through transcription. | 10–12 | PASS / PROTECTED | Passed 2026-07-29: owner screenshots prove upper Strength 10 mg to 5 mg, middle-field listening, lower Buying price 120 to 121, and Expiry 2028-09 to 2026 May to restored 2028-09 all retained the selected field in view; each review changed only one field and discard restored baseline | Yes | 5 min | CVS; LATP; two owner mobile screenshot sets; `voiceViewportAnchor.js`; viewport verifier; 2026-07-29 owner mobile regression screenshots after 67cfcac; earlier failed attempts remain recorded in CVS, LATP and Engineering Memory |
| 14 | Known-medicine sales | Record typed/voice known sales, canonical identity, quantity, payment, receipt and stock exactly once. | 10–12 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; TCE Fast Record evidence; sales tests |
| 15 | Restocking and delivery details | Review typed/voice restocks, quantity/bonus/cost/supplier/batch/expiry and add stock once. | 10–12 | PASS / PROTECTED | Passed | Yes | 12 min | CVS; voice-restock verifier; intake tests |
| 16 | Stock enquiry | Answer saved stock locally and truthfully without creating a draft or mutation. | 10 | PASS / PROTECTED | Passed | Yes | 4 min | CVS; `localIntelligence.js`; stock tests |
| 17 | Manual stock correction | Review trusted current stock, corrected stock and optional reason; apply idempotently. | 10 | PASS / PROTECTED | Passed | Yes | 8 min | CVS; `stock-fix-workflow.md`; stock-correction verifiers |
| 18 | Stock Fix acquisition parity | Converge Photo, Camera, File and guided Mic into the same correction/execution boundary. | 17 | PASS / PROTECTED | Passed | Yes | 15 min | CVS; stock-fix evidence/UI verifiers |
| 19 | Corrections, cancellation and undo | Correct pending work, cancel safely and create linked reversal/undo history without deletion. | 14–18 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; TCE; issue-return/intake tests |
| 20 | Offline operation and synchronization | Queue text/media/actions offline, recover, retry, deduplicate and reconcile stock safely. | 14–19 | PASS / PROTECTED | Passed | Yes | 15 min | TRAIN; offline app/sync/queue tests |

## 2. Pharmacy Operating Intelligence Validation

| # | Checkpoint | Objective | Prerequisite(s) | Implementation state | Owner validation | Protected | Est. live test | Evidence/document source |
|---:|---|---|---|---|---|---|---|---|
| 21 | Daily operational metrics | Show sales, payment totals, cost, gross profit, items, best seller, peak time, missed demand and low stock from truthful records. | 14, 20 | PASS / PROTECTED | Passed | Yes | 10 min | CVS report evidence; `reports.py`; report verifier |
| 22 | Direct analytics commands | Answer cash/M-Pesa today, payment split/top method, best seller, peak hours, missed demand and profit locally. | 21 | Implemented — awaiting owner live test | Not yet owner-tested in Main App | No | 12 min | OI; `intake.py`; analytics/token tests |
| 23 | Decision-support summary | State what happened, why it matters and a deterministic next action without routine LLM use. | 21–22 | Partial implementation | Not passed | No | 10 min | OI; `deterministic_recommendations()`; current renderer gap |
| 24 | Low/out-of-stock intelligence | Prioritize actual low/out conditions, explain the risk and clear the action when stock is restored. | 10, 14 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; notification lifecycle evidence |
| 25 | Expiry intelligence | Interpret canonical expiry, prioritize expired/near-expiry stock and clear safely after restoration. | 10 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; expiry lifecycle evidence |
| 26 | Missed-demand and lost-opportunity intelligence | Aggregate no-stock/not-sold demand and recommend a truthful response. | 14, 21 | Partial implementation | Not passed as intelligence | No | 10 min | OM future rules; `reports.py`; intake/training tests |
| 27 | Fast/slow/dead-stock intelligence | Detect movement patterns, inactivity and value tied up, then recommend owner action. | 14, 21, 49 | Planned / approved | Not started | No | 15 min | OM; OI; historical Operational Intelligence continuation |
| 28 | Stock-out and demand-risk prediction | Anticipate likely stock-outs using canonical movement, lead time and confirmed unit truth. | 21, 27, 49 | Planned / approved | Not started | No | 15 min | OI; LATP approved improvements |
| 29 | Reorder-level and supplier-order intelligence | Suggest truthful reorder quantities, allow owner control/grouping/sending and track sourced fulfilment. | 24, 27–28, 49 | Planned / approved | Not started | No | 20 min | LATP Improvement 1; OI |
| 30 | Operational dashboard and action prioritization | Rank urgent/value-at-risk work and expose calm next-best actions with measurable outcomes. | 23–29 | Partial implementation | Not passed | No | 15 min | notification center; deployment dashboard; OM/OI |

## 3. AI / Learning Validation

| # | Checkpoint | Objective | Prerequisite(s) | Implementation state | Owner validation | Protected | Est. live test | Evidence/document source |
|---:|---|---|---|---|---|---|---|---|
| 31 | Source Brain and shared medicine matcher | Resolve canonical names, brands, aliases, spelling/phonetic/OCR variants and safe ambiguity locally. | 2 | PASS / PROTECTED | Passed through onboarding/search evidence | Yes | 10 min | CVS; OM; matcher verifier/tests |
| 32 | Pharmacy Catalog learning boundary | Save only owner-approved pharmacy facts and keep global Source Brain separate. | 31 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; OM; catalog persistence evidence |
| 33 | Pharmacy alias/shorthand learning | Learn repeated confirmed local shorthand safely, retain review and avoid dangerous promotion. | 31–32 | Partial implementation | Manual alias path passed; adaptive path untested | No | 12 min | OI; `AdaptiveAliasLearner`; training tests |
| 34 | Operational memory and reusable commands | Reuse recent approved transaction context and owner commands within safe local boundaries. | 14, 31 | Implemented — awaiting owner live test | Implemented paths lack decisive owner evidence | No | 8 min | `OperationalMemory`; reuse UI; intake/training tests |
| 35 | Trusted-result/cache reuse | Reuse verified invoice/photo/barcode evidence before AI and keep corrections medicine/pharmacy scoped. | 3, 7–9, 31 | Partial implementation | Controlled fixtures passed; general cache programme incomplete | No | 12 min | `trusted-result-consistency.md`; fixture history |
| 36 | Media classification and extraction routing | Classify invoice, receipt, shelf, pack, barcode and unclear media; preserve review and safe fallback. | 3, 7–9 | Partial implementation | Core routes passed; full general classifier untested | No | 12 min | `operational_intelligence.py`; photo/intake tests |
| 37 | AI fallback approval boundary | Use AI only for explicitly approved unresolved voice/command/media cases with privacy, timeout, cache and cost controls. | 31, 35–36 | Implemented — awaiting owner live test | Zero-AI paths passed; fallback not owner-qualified | No | 10 min | `ai_policy.py`; AI policy/token tests; ARCH |
| 38 | Learning effectiveness and rollback | Measure whether approved learning/recommendations helped and allow safe correction/forgetting without cross-pharmacy leakage. | 23, 33–37 | Planned / approved | Not started | No | 15 min | OI; training/reliability/learning architecture |

## 4. Reporting & Export Validation

| # | Checkpoint | Objective | Prerequisite(s) | Implementation state | Owner validation | Protected | Est. live test | Evidence/document source |
|---:|---|---|---|---|---|---|---|---|
| 39 | Report periods, refresh and Read | Generate Today/historical/custom reports, preserve freshness/source truth and read aloud reliably. | 21 | PASS / PROTECTED | Passed | Yes | 12 min | CVS; LATP report history; report verifier/tests |
| 40 | CSV Technical Data Transfer | Export canonical 35×12 machine data with safe encoding, quoting and spreadsheet protections. | 10 | PASS / PROTECTED | Passed | Yes | Repository evidence not yet available. | CVS; CSV compatibility memory |
| 41 | Excel Operations Workbook | Produce purpose-built operational sheets with reconciled metrics and complete canonical inventory. | 10, 21 | PASS / PROTECTED | Passed | Yes | Repository evidence not yet available. | CVS; Export Hub verifier |
| 42 | PDF Owner Copy | Produce readable portrait overview and complete medicine cards without clipping. | 10, 21 | PASS / PROTECTED | Passed | Yes | Repository evidence not yet available. | CVS; Export Hub evidence |
| 43 | Word Owner Copy | Produce editable owner notes/corrections document with all medicines and stable page flow. | 10, 21 | PASS / PROTECTED | Passed | Yes | Repository evidence not yet available. | CVS; Export Hub evidence |
| 44 | Presentation Owner Briefing | Produce a readable nine-slide decision briefing with correct identity and no invented claims. | 10, 21 | PASS / PROTECTED | Passed | Yes | Repository evidence not yet available. | CVS; Export Hub evidence |
| 45 | Print Working Inventory | Show mobile review/finder and complete native print preview without claiming physical completion. | 10 | PASS / PROTECTED | Passed | Yes | Repository evidence not yet available. | CVS; Print evidence |
| 46 | Export Hub status/history | Maintain one pharmacy-scoped status card, deduplicated history and no operations-feed spam. | 40–45 | PASS / PROTECTED | Passed | Yes | Repository evidence not yet available. | CVS; export history memory/verifier |
| 47 | Cross-format canonical integrity | Keep one immutable snapshot, all records/fields, valid packages, filenames and readable layouts across formats. | 40–46 | PASS / PROTECTED | Passed | Yes | Repository evidence not yet available. | CVS; consistency/export verifiers |
| 48 | Future operational documents | Generate supplier orders, GRNs, cash/finance reconciliation, expiry and supplier reports from stored truth. | 29, 39–47 | Planned / approved | Not started | No | 20 min | OM Documents/Future rules; LATP Improvement 1 |

## 5. Financial & Payment Validation

| # | Checkpoint | Objective | Prerequisite(s) | Implementation state | Owner validation | Protected | Est. live test | Evidence/document source |
|---:|---|---|---|---|---|---|---|---|
| 49 | Exact form/unit/pack/price truth | Prevent unit/strength price leakage and preserve conversions across all inputs and consumers. | 10–15 | PASS / PROTECTED | Passed 2026-07-31: owner screenshots of the typed `Ibuprofen 1 tablet cash` review proved exact tablet form/unit, KES 18 unit/total, cash, projected stock 27 → 26, strength 200 mg, buying price KES 9, supplier Afya Wholesale Ltd, batch IBU-200C, expiry 2028-12, truthful absent optional traceability, all three Production Sales Card tabs, and no confirmed or persisted mutation. | Yes | 20 min | Owner screenshot package supplied through CODEX BRIDGE v5.0; protected Production Sales Card standard; focused production-sale-card and sale-fixture verifiers |
| 50 | Payment modes, splits and discounts | Handle Cash, M-Pesa, Card, Credit, Mixed, payment corrections and supported discounts truthfully. | 14, 49 | PASS / PROTECTED | Passed 2026-07-31: owner screenshots of the Septrin one-bottle Credit review proved suspension/bottle identity, KES 180 unit price and total, selected Credit payment, projected stock 12 → 11, buying price KES 120, supplier MedSource Kenya Ltd, batch SEP-100S, expiry 2028-09, truthful Not recorded values, all three protected Production Sales Card tabs, and no confirmed or persisted mutation. | Yes | 15 min | Owner screenshot package supplied 2026-07-31; protected Production Sales Card standard; focused production-sale-card and sale-fixture verifiers |
| 51 | TCE Fast Record | Record owner-confirmed transactions immediately with daily numbering and exact one-time stock/finance effects. | 14 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; TCE |
| 52 | Request & Verify success | Queue non-cash request, continue serving and complete only after verified success. | 51 | PASS / PROTECTED | Passed | Yes | 12 min | CVS; TCE; TCE/UI verifiers |
| 53 | Concurrent payment completion | Keep multiple waiting payments isolated, support out-of-order success and prevent duplicate stock effects. | 52 | PASS / PROTECTED | Passed | Yes | 12 min | TCE quiet-concurrency evidence |
| 54 | Payment failure/cancellation notification | Preserve stock/paid records and create one durable action-needed Notification without chat noise. | 52–53 | PASS / PROTECTED | Passed 2026-07-29: owner mobile screenshots prove Zinc Sale 1 supporting flow evidence and authoritative Septrin Sale 2 stock-preservation evidence. Septrin began and ended at numeric stock 12, quantity 1, bottle/suspension, KES 180 selling price and M-Pesa; Waiting became failed after one Simulate failed action, Payment Queue returned to 0 waiting, history retained one failed not paid/completed sale, one distinct unread actionable Sale 2 notification stated stock and paid records were unchanged, and Review payment returned to the same failed record. Zinc had blank stock and is supporting flow evidence only; its separate Sale 1 alert is not a duplicate of Septrin Sale 2. | Yes | 8 min | TCE; ARCH; `notificationCenter.js`; `verify-payment-failure-notification.mjs`; 2026-07-29 owner 24-screenshot chronological package; Septrin 12-to-12 authoritative stock proof; Zinc preliminary fixture correction preserved; a76215e |
| 55 | Refunds, returns and credits | Record linked financial/stock adjustments without deleting original history, then validate approved status-card and direct-command improvements without replacing the tappable route. | 51–54 | Implemented — awaiting owner live test | Original 055-A through 055-F and post-original 055-G/Direct Command 1 are owner-verified passed/frozen/protected. The 2026-08-02 055-G evidence proves `open sale 1` and `sale 1` open immutable fully-adjusted Sale 1 with Return #9, `open sale 4` opens immutable Sale 4 with Returns #7/#8, ordinary sale review remains intact, stock remains 16, queue remains 0 and navigation causes no mutation. MS2.0 permanently uses Voice first → fast tap/action second → typing last, with typed/voice parity through shared deterministic routing. Checkpoint 055 remains open only for later ordered post-original cases. | No | Staged | 2026-07-31 through 2026-08-02 owner screenshots; shared Sale Adjustment and Sale Direct Command verifiers; Production Sales Card; TCE; offline queue/sync; consistency gate; LATP ordered 055 programme |
| 56 | Undo/reversal reconciliation | Reconcile stock, finance, receipt, reports and audit exactly once for visible sale numbers. | 51–55 | Partial implementation | Basic cancellation/undo passed; full TCE reconciliation untested | No | 15 min | TCE; ledger/intake tests |
| 57 | Supplier/restock payments | Support supplier payment, credit and future settlement flows through the adapter/TCE boundary. | 29, 50, 55 | Planned / approved | Not started | No | 15 min | TCE permanent scope; supplier workflows |

## 6. Integration Validation

| # | Checkpoint | Objective | Prerequisite(s) | Implementation state | Owner validation | Protected | Est. live test | Evidence/document source |
|---:|---|---|---|---|---|---|---|---|
| 58 | Main App/backend adapter gateway | Serve `/main-app/`, probe backend safely and keep writes behind explicit adapters/queues. | 1 | PASS / PROTECTED | Passed on Replit | Yes | 8 min | CVS; ARCH; backend adapter/route tests |
| 59 | Google Sheets pharmacy persistence | Provision/read/write isolated pharmacy sheets and recover safely when unavailable. | 2, 20 | Implemented — awaiting owner live test | Earlier onboarding evidence exists; full production parity unqualified | No | 15 min | onboarding/sheets tests; TRAIN |
| 60 | WhatsApp/Baileys optional channel | Route text/voice/media through shared pharmacy logic without making it the Main App proof path. | 31, 58–59 | Implemented — awaiting owner live test | Historical bridge tests; current optional channel not requalified | No | 15 min | bridge docs/tests; commit history |
| 61 | Offline PWA and media bridge | Save offline actions/media, resume, synchronize and deliver confirmations to the correct owner. | 20, 58 | PASS / PROTECTED | Passed during offline programme | Yes | 15 min | TRAIN; offline/bridge tests |
| 62 | Meta/Twilio legacy webhook channels | Preserve historical webhook compatibility without treating it as the active product channel. | 58 | Deprecated with repository evidence | Historical only | No | 5 min | README; Meta webhook tests; Baileys migration commits |
| 63 | Local WhatsApp Web MVP bridge | Preserve the superseded local bridge for historical/optional compatibility. | 58 | Deprecated with repository evidence | Historical only | No | 5 min | WhatsApp Web docs/tests; Baileys migration |
| 64 | Share/email/document delivery routes | Send supported outputs/orders through safe device/share/email routes with truthful receipt state. | 29, 46, 48 | Planned / approved | Not started | No | 15 min | LATP Improvement 1; export metadata |

## 7. Security / Privacy / Compliance Validation

| # | Checkpoint | Objective | Prerequisite(s) | Implementation state | Owner validation | Protected | Est. live test | Evidence/document source |
|---:|---|---|---|---|---|---|---|---|
| 65 | Pharmacy/branch isolation | Prevent cross-pharmacy catalog, learning, notification, payment, export and credential leakage. | Implemented pharmacy-scoped data workflows | PASS / PROTECTED | Passed in protected workflows and automated gates | Yes | 15 min | CVS; ARCH; isolation tests/verifiers |
| 66 | Idempotency, audit and duplicate prevention | Ensure retries/callbacks/imports/actions cannot duplicate mutations and every protected correction remains traceable. | 14–20, 51–53 | PASS / PROTECTED | Passed across protected workflows | Yes | 15 min | CVS; TCE; activity/export/offline verifiers |
| 67 | Authentication, roles and access controls | Enforce owner/admin/branch authorization and minimum-necessary access across UI, routes and downloads. | 2, 58–65 | Partial implementation | Not owner-qualified end to end | No | 15 min | registry/admin/routes; ARCH; compliance plan |
| 68 | Export IP/privacy/compliance safeguards | Register assets/licences, fail closed, redact/anonymize, control IDs/sharing/retention and avoid false endorsement. | 40–48, 65–67 | Planned / approved | Not started | No | Repository evidence not yet available. | LATP Improvement 3 |
| 69 | Product-secrecy and quiet-UI audit | Remove unnecessary internal implementation disclosures while preserving legal/safety/privacy truth. | All functional/intelligence tests | Planned / approved | Not started | No | Repository evidence not yet available. | CVS; LATP future audit |

## 8. Production Qualification

| # | Checkpoint | Objective | Prerequisite(s) | Implementation state | Owner validation | Protected | Est. live test | Evidence/document source |
|---:|---|---|---|---|---|---|---|---|
| 70 | Replit deployment and health | Pull/restart authoritative code, serve backend/Main App and verify health/public route without secret exposure. | 58 | PASS / PROTECTED | Repeatedly passed | Yes | 8 min | CVS; Replit handoff; production tests |
| 71 | Startup/report observability | Warm shared sources, expose truthful readiness markers and avoid false ready claims. | 39, 70 | PASS / PROTECTED | Passed | Yes | 8 min | CVS; startup/warmup tests |
| 72 | Architecture/consistency regression gate | Prove zero-token defaults, protected contracts, fixtures and canonical consistency before deployment. | All implemented checkpoints | Implemented — awaiting owner live test | Automated gate passes; no separate owner qualification | No | 10 min | all `verify-*.mjs`; regression tests |
| 73 | Autonomous pharmacy provisioning | Create isolated profile/owner/branch/catalog/queue/monitoring configuration and recover failed onboarding. | 2, 59, 65–67 | Implemented — awaiting owner live test | Automated phases pass; real production owner qualification pending | No | 20 min | TRAIN Phases 12–13; provisioning tests |
| 74 | Production payment-provider qualification | Confirm merchant onboarding model, tenant identity, credentials, authenticated callbacks, reconciliation and official adapters. | 49–57, 65–68 | External qualification | Blocked on direct provider/commercial confirmation | No | Multi-session | TCE; Safaricom unresolved question |
| 75 | Professional legal/regulatory qualification | Obtain Kenya IP, trademark, ODPC/privacy, pharmacy, payments, terms/DPA, security and retention review. | 68–69 | External qualification | Not performed | No | Multi-session | LATP Improvement 3 pre-launch gates |
| 76 | Production channel/scale qualification | Qualify official messaging/channel operations, multi-pharmacy scale, backup/recovery, monitoring and incident response. | 60–61, 65–73 | External qualification | Automated stress evidence only | No | Multi-session | TRAIN; deployment/provisioning/bridge tests |

## 9. Launch Program Validation

These owner-approved checkpoints were registered by the 2026-07-29 launch-roadmap reorganization. Their active priority is governed by `docs/engineering-memory/launch-readiness-roadmap.md`; their stable IDs, status, prerequisites, evidence and protection remain governed here.

| # | Checkpoint | Objective | Prerequisite(s) | Implementation state | Owner validation | Protected | Est. live test | Evidence/document source |
|---:|---|---|---|---|---|---|---|---|
| 77 | Multiuser Pharmacy Version 1 | Let owner-approved staff join one pharmacy with fixed roles, shared truth, attribution, safe sync, device controls and consolidated reporting. | 59, 66–67, 73 | Planned / approved | Not started | No | 20 min | Launch roadmap; multiuser locked improvement |
| 78 | Impala Loyalty Program Version 1 | Provide a deterministic pharmacy-pooled coin wallet, earning/referral history, anti-abuse caps and owner-controlled renewal redemption. | 77, 84 | Planned / approved | Not started | No | 15 min | Launch roadmap; Impala Loyalty locked improvement |
| 79 | Impala Community Version 1 | Provide one moderated pharmacy identity with feed, posts/photos, questions, comments, appreciation, reporting and restriction controls. | 67, 77 | Planned / approved | Not started | No | 20 min | Launch roadmap; Impala Community locked improvement |
| 80 | Low-data, low-resource and desktop reliability | Measure and qualify weak-network, background-data, queue recovery, battery/memory/heat, suspension/restart and responsive desktop behavior. | 20, 61, 66, 72 | Planned / approved | Not started | No | Multi-session | Launch roadmap; Intelligence + Reliability locked improvement |
| 81 | Multi-medicine photo onboarding | Detect distinct packs into one compact expandable shared review, preserve uncertainty/provenance and deduplicate before save. | 8–11, 31, 35–36 | Planned / approved | Not started | No | 15 min | Launch roadmap; Intelligence + Reliability locked improvement; future fixture plan |
| 82 | Daily intelligent assistant Version 1 | Give neutral deterministic morning/evening summaries and capture one privacy-minimized feedback item without automatic product changes. | 21, 24–25 | Planned / approved | Not started | No | 12 min | Launch roadmap; Intelligence + Reliability locked improvement |
| 83 | Demo Mode certification | Certify a truthful 5–10-step owner walkthrough with real workflows, no hidden intervention and no launch-blocking regression. | 54, 77–82, 84 | Planned / approved | Not started | No | 20 min | Launch roadmap; Demo Mode certification plan |
| 84 | Subscription and multiuser billing clarity | Define packages, included seats, active-device/replacement rules, expiry/grace behavior, renewal totals and loyalty redemption truth. | 50, 67, 74 | Planned / approved | Not started | No | 15 min | Launch roadmap; owner commercial decisions; provider qualification |

## Repository completeness ledger

This ledger deliberately accounts for owner-facing domains discovered across current and historical Project Brain/Engineering Memory, plans, architecture, handoffs, commits/diffs, implementation, tests and fixtures. It does not create parallel checkpoints or change checkpoint counts.

| Capability/domain | Classification | Accounted by | Repository evidence boundary |
|---|---|---|---|
| Sales, receipts and daily numbering | PASS / PROTECTED | 14, 51 | Sales/TCE owner evidence and tests |
| Catalog, medicine editing, search and Activity History | PASS / PROTECTED | 10–11, 31–32, 66 | Catalog Search Mic and Activity Compaction owner evidence; catalog/activity verifiers |
| Stock management, stock checks, fixes and restocking | PASS / PROTECTED | 15–18, 24–25 | Stock Fix owner sequence; stock/restock tests |
| Exact unit, form, pack, conversion and price truth | PASS / PROTECTED | 49 | 2026-07-31 owner Ibuprofen known-unit screenshot package; Production Sales Card regression verifiers |
| Supplier ordering, fulfilment and supplier payments | Planned / approved | 29, 48, 57 | LATP ordered Improvement 1; TCE permanent scope |
| Reorder, stock-out, demand, fast/slow/dead-stock and expiry intelligence | Planned / approved | 26–30 | OI; OM Future rules |
| Operational metrics, analytics, dashboard and decision support | Partial implementation | 21–23, 30 | Protected reports plus unqualified/partial intelligence renderers |
| Notifications, unread/action routing and quiet state | PASS / PROTECTED | 24–25, 54 | Inventory, expiry and payment-failure lifecycles owner-validated and protected |
| Payment modes, split/mixed payments and discounts | PASS / PROTECTED | 50 | 2026-07-31 owner Septrin one-bottle Credit screenshot package; Production Sales Card regression verifiers |
| Payment failure/cancellation | PASS / PROTECTED | 54 | Owner Septrin 12-to-12 failure evidence; durable distinct alert and Review payment routing |
| Refunds, returns, credits and undo/reversal | Partial implementation | 19, 55–56 | Basic cancellation protected; full financial reconciliation remains unqualified |
| Cash/finance reconciliation | Planned / approved | 48, 56–57 | OM Future rules; TCE reconciliation hooks |
| Reports, periods, speech controls and performance | PASS / PROTECTED | 21, 39, 71 | Report owner evidence, zero-AI latency/warmup history and tests |
| CSV, Excel/XLSX, PDF, Word, Presentation and Print | PASS / PROTECTED | 40–47 | Export Hub owner evidence and cross-format verifiers |
| Future operational document generation | Planned / approved | 48 | OM Documents; LATP |
| Export and Activity history | PASS / PROTECTED | 10, 46, 66 | Activity/Export History owner evidence and verifiers |
| Voice and contextual microphone editing | PASS / PROTECTED | 12–13 | Shared voice and contextual viewport/focus are owner-validated and protected |
| Barcode | PASS / PROTECTED | 7 | Known/unknown fixture and owner evidence |
| OCR, camera, gallery, shelf and medicine-pack intake | PASS / PROTECTED | 3, 8–9, 18 | Invoice/photo/Stock Fix owner evidence and fixtures |
| Bulk paste, CSV, XLSX and file imports | PASS / PROTECTED | 4–6, 11 | Owner evidence and import verifiers |
| Source Brain, canonical matching and Catalog boundary | PASS / PROTECTED | 31–32 | Matcher/catalog owner evidence and tests |
| Alias learning, operational memory, cache reuse and rollback | Partial implementation | 33–35, 38 | Manual alias path protected; adaptive/general programme incomplete |
| Media classification and approved AI fallback | Partial implementation | 36–37 | Core media routes exist; general classification/fallback unqualified |
| Offline operation and synchronization | PASS / PROTECTED | 20, 61 | Offline programme owner evidence and sync tests |
| Google Sheets persistence | Implemented — awaiting owner live test | 59 | Sheets/onboarding implementation and historical evidence |
| WhatsApp/Baileys optional channel | Implemented — awaiting owner live test | 60 | Current bridge implementation and historical tests |
| Meta/Twilio and local WhatsApp Web legacy channels | Deprecated with repository evidence | 62–63 | Channel migration commits and legacy tests/docs |
| Sharing, email and delivery receipts | Planned / approved | 64 | LATP supplier/export requirements |
| Authentication, roles and access control | Partial implementation | 67 | Actor/registry/admin/routes implementation; end-to-end qualification absent |
| Tenant/branch isolation, idempotency and audit | PASS / PROTECTED | 65–66 | Protected workflows and automated isolation/idempotency gates |
| Privacy, IP, retention and product-secrecy safeguards | Planned / approved | 68–69 | LATP Improvement 3 and future audit |
| Professional legal/regulatory qualification | External qualification | 75 | Explicit professional pre-launch gate |
| Deployment, health, readiness and observability | PASS / PROTECTED | 70–71 | Replit evidence and health/startup/report gates |
| Architecture/consistency regression qualification | Implemented — awaiting owner live test | 72 | Automated gate passes; separate owner qualification remains |
| Autonomous pharmacy provisioning | Implemented — awaiting owner live test | 73 | Phases 12–13 and provisioning tests |
| Production payment providers and merchant onboarding | External qualification | 74 | TCE unresolved provider/commercial gate |
| Multi-pharmacy scale, backup/recovery and incident response | External qualification | 76 | TRAIN/deployment evidence; production qualification outstanding |
| Multiuser pharmacy, fixed roles and shared truth | Planned / approved | 77 | Launch roadmap locked improvement; depends on persistence, audit, access and provisioning |
| Impala Loyalty Program Version 1 | Planned / approved | 78 | Launch roadmap locked improvement; pharmacy-pooled deterministic wallet and renewal redemption |
| Impala Community Version 1 | Planned / approved | 79 | Launch roadmap locked improvement; separate moderated pharmacy-focused community |
| Low-data, low-resource and desktop reliability | Planned / approved | 80 | Launch roadmap measurable reliability budgets |
| Multi-medicine photo onboarding | Planned / approved | 81 | Launch roadmap compact shared-review and deterministic-first fixture plan |
| Daily intelligent assistant Version 1 | Planned / approved | 82 | Launch roadmap neutral deterministic summaries and controlled feedback |
| Demo Mode certification | Planned / approved | 83 | Launch roadmap truthful owner walkthrough gate |
| Subscription and multiuser billing clarity | Planned / approved | 84 | Launch roadmap package/seat/device/renewal/provider truth |
| Subscription collection | External qualification | 74 | TCE separates the MS2.0 merchant account; production merchant qualification is externally gated |
| Insurance settlements and branch transfers | Intentionally out of scope with repository evidence | None | TCE names them only as future extension points; no approved owner workflow or test programme exists |
| Generic anomaly engine beyond named rules | Intentionally out of scope with repository evidence | None | OI explicitly records no approved standalone anomaly programme |
| Legacy XLS parsing | Intentionally out of scope with repository evidence | 6 | Current XLSX checkpoint explicitly requires an honest unsupported-XLS result |

## Canonical status totals

- Total checkpoints: **84**
- PASS / PROTECTED: **46**
- Implemented — awaiting owner live test: **8**
- Partial implementation: **8**
- Planned / approved: **17**
- External qualification: **3**
- Deprecated with repository evidence: **2**

## Current execution pointer

The only current open checkpoint is **#55 Refunds, returns and credits**. MS2-LT-050 passed owner validation on 2026-07-31 from the Septrin one-bottle Credit screenshot package and is protected together with MS2-LT-049 and the Production Sales Card regression contract. None may be repeated without regression evidence. MS2-LT-055 is selected by the dependency-aware Exact Transaction Truth route because prerequisites #51–#54 are protected; the former automatic linear progression is historical and must never resume. Issue only its first focused owner test, then stop and wait for evidence.

## Canonical synchronization invariants

1. No Project Brain, Engineering Memory, architecture snapshot, test plan, handoff, bridge or synchronization package may publish an independent checkpoint list, count, order, prerequisite or status.
2. Every future Codex chat and ChatGPT/Codex Bridge must read this file before reporting or selecting live validation and must treat all embedded historical “next” statements as evidence only.
3. Any approved capability discovered later must be reconciled here in the same commit as its supporting-document reference; it may not be inserted only into a bridge or secondary plan.
4. A checkpoint may change status only here, with owner evidence for `PASS / PROTECTED`; dependent documents may record detail but cannot override it.
5. A deletion, merge, split, renumbering, prerequisite change or deprecation requires repository evidence, updated totals, an updated completeness-ledger row and same-commit synchronization of directly affected references.
6. Before push, validate unique checkpoint numbers/names, allowed states, totals, acyclic prerequisites, one current pointer and canonical-reference headers in every tracked Markdown governance/support document.
7. Active implementation priority comes only from `docs/engineering-memory/launch-readiness-roadmap.md`; the historical table order cannot select the next milestone.

## Living validation contract

Every approved owner-visible improvement, workflow, intelligence programme, integration, compliance requirement or production qualification must be registered incrementally in this master in the same commit as its implementation evidence. Use the next numeric checkpoint ID, place it in the correct category, declare prerequisites, evidence, commits and primary modules, and default to `Implemented — awaiting owner live test` unless repository evidence supports another state.

Owner PASS transitions require explicit live-test evidence, set `Protected` to `Yes`, retain traceability and prevent routine retesting. Cancellation, merge, supersession or deprecation changes the lifecycle state without deleting the checkpoint; the evidence must retain the reason and replacement ID where applicable.

Governance commands:

- Register, protect, explicitly reopen or retire from an explicit JSON payload: `node scripts/govern-validation-checkpoint.mjs <register|protect|reopen|retire> <payload.json>`.
- Regenerate the traceability index, synchronized Project Brain/Engineering Memory references and Bridge manifest: `npm run validation:sync`.
- Validate IDs, names, states, totals, prerequisite graph, dependents, protected evidence, synchronized references and Bridge compatibility: `npm run validation:check`.

Future Codex chats must load this master and `docs/engineering-memory/bridge-validation-contract.json`; they must never reconstruct the sequence manually. CODEX BRIDGE and CHATGPT BRIDGE generation must consume the same manifest and master traceability index.

## Permanent API-token and execution rule

Token policy: **ACTIVE**

MS2.0 execution order is permanently: local deterministic logic → Pharmacy Catalog → Source Brain → local OCR → verified cache → AI/external LLM only as a documented and justified last resort. Routine operational workflows must not invoke an LLM without a repository-recorded engineering justification.

Codex must inspect targeted authority first, reuse shared roots and Engineering Memory, avoid repeated large reads/history/explanations/searches/summaries, prefer focused tests with minimum safety coverage, keep routine owner reports compact, and stop on a real blocker rather than loop. When a chat becomes slow, context-heavy or repetitive, recommend a CODEX BRIDGE. The full inherited rule lives in `docs/engineering-memory/token-execution-policy.md`.

<!-- TRACEABILITY_INDEX_START -->

## Engineering traceability index



This generated index is part of the canonical master. Run `node scripts/sync-validation-contract.mjs` after an evidence, status, prerequisite, dependency, implementation-file or checkpoint change. Commit this file and all synchronized Project Brain/Engineering Memory/Bridge references together.



### MS2-LT-001 — Main App shell and navigation

- **Checkpoint ID:** MS2-LT-001
- **Name:** Main App shell and navigation
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; ARCH; `verify-architecture.mjs`
- **Implementation commit(s):** ed1d316 Automate transaction completion and simplify payment navigation
- **Primary implementation files/modules:** `ms20-main-app/src/app.js`; `ms20-main-app/src/routes/routeRegistry.js`
- **Owner live-test evidence:** Passed; source: CVS; ARCH; `verify-architecture.mjs`
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** None
- **Dependent checkpoints:** MS2-LT-002, MS2-LT-012, MS2-LT-058

### MS2-LT-002 — First-run owner setup

- **Checkpoint ID:** MS2-LT-002
- **Name:** First-run owner setup
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; OM; `pharmacy_onboarding.py`; onboarding tests
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `app/services/pharmacy_onboarding.py`; `app/pharmacy_registry.py`
- **Owner live-test evidence:** Passed; source: CVS; OM; `pharmacy_onboarding.py`; onboarding tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 1
- **Dependent checkpoints:** MS2-LT-003, MS2-LT-004, MS2-LT-005, MS2-LT-006, MS2-LT-007, MS2-LT-008, MS2-LT-009, MS2-LT-010, MS2-LT-031, MS2-LT-059, MS2-LT-067, MS2-LT-073

### MS2-LT-003 — Invoice onboarding and local OCR

- **Checkpoint ID:** MS2-LT-003
- **Name:** Invoice onboarding and local OCR
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; `invoice-table-ocr.md`; invoice fixtures/tests
- **Implementation commit(s):** efaeebb Read ambiguous invoice cells directly; 342bf5e Refine ambiguous invoice cells locally; 59eec84 Preserve complete invoice evidence and pricing
- **Primary implementation files/modules:** `app/services/local_invoice_ocr.py`; `app/services/medicine_onboarding.py`
- **Owner live-test evidence:** Passed; source: CVS; `invoice-table-ocr.md`; invoice fixtures/tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 2
- **Dependent checkpoints:** MS2-LT-011, MS2-LT-035, MS2-LT-036

### MS2-LT-004 — Bulk paste onboarding

- **Checkpoint ID:** MS2-LT-004
- **Name:** Bulk paste onboarding
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; LATP; paste fixtures; catalog verifiers
- **Implementation commit(s):** 7a6335c Prepare local Excel catalog onboarding; 8c22f10 Require explicit paste input before catalog review; e4a4cfa Prepare clean paste onboarding fixture
- **Primary implementation files/modules:** `ms20-main-app/src/services/catalogOnboarding.js`
- **Owner live-test evidence:** Passed; source: CVS; LATP; paste fixtures; catalog verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 2
- **Dependent checkpoints:** MS2-LT-011

### MS2-LT-005 — CSV onboarding

- **Checkpoint ID:** MS2-LT-005
- **Name:** CSV onboarding
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; CSV fixture/verifier
- **Implementation commit(s):** 7a6335c Prepare local Excel catalog onboarding; c663670 Preserve strength through CSV review; e4a4cfa Prepare clean paste onboarding fixture
- **Primary implementation files/modules:** `ms20-main-app/src/services/catalogOnboarding.js`
- **Owner live-test evidence:** Passed; source: CVS; CSV fixture/verifier
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 2
- **Dependent checkpoints:** MS2-LT-011

### MS2-LT-006 — XLSX onboarding

- **Checkpoint ID:** MS2-LT-006
- **Name:** XLSX onboarding
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; Test 5 fixture/verifier
- **Implementation commit(s):** 7a6335c Prepare local Excel catalog onboarding; e4a4cfa Prepare clean paste onboarding fixture; df18086 Add local-first catalog onboarding foundation
- **Primary implementation files/modules:** `ms20-main-app/src/services/catalogOnboarding.js`
- **Owner live-test evidence:** Passed; source: CVS; Test 5 fixture/verifier
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 2
- **Dependent checkpoints:** MS2-LT-011

### MS2-LT-007 — Barcode onboarding

- **Checkpoint ID:** MS2-LT-007
- **Name:** Barcode onboarding
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; barcode fixtures/verifiers
- **Implementation commit(s):** 0d7ce83 Add Loperamide barcode live-test fixture; 3de02cb Add controlled barcode live-test fixture
- **Primary implementation files/modules:** `ms20-main-app/src/data/barcodeTestFixtures.js`; `ms20-main-app/src/services/medicineMatcher.js`
- **Owner live-test evidence:** Passed; source: CVS; barcode fixtures/verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 2
- **Dependent checkpoints:** MS2-LT-011, MS2-LT-035, MS2-LT-036

### MS2-LT-008 — Shelf-photo onboarding

- **Checkpoint ID:** MS2-LT-008
- **Name:** Shelf-photo onboarding
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; shelf fixtures/verifier
- **Implementation commit(s):** df18086 Add local-first catalog onboarding foundation; cc5d3e3 Add photo invoice intake infrastructure
- **Primary implementation files/modules:** `app/services/photo_intake.py`; `ms20-main-app/src/services/visualPipeline.js`
- **Owner live-test evidence:** Passed; source: CVS; shelf fixtures/verifier
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 2
- **Dependent checkpoints:** MS2-LT-011, MS2-LT-035, MS2-LT-036, MS2-LT-081

### MS2-LT-009 — Medicine-pack photo onboarding

- **Checkpoint ID:** MS2-LT-009
- **Name:** Medicine-pack photo onboarding
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; medicine-photo fixture/verifier
- **Implementation commit(s):** df18086 Add local-first catalog onboarding foundation; cc5d3e3 Add photo invoice intake infrastructure
- **Primary implementation files/modules:** `app/services/photo_intake.py`; `ms20-main-app/src/services/visualPipeline.js`
- **Owner live-test evidence:** Passed; source: CVS; medicine-photo fixture/verifier
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 2
- **Dependent checkpoints:** MS2-LT-011, MS2-LT-035, MS2-LT-036, MS2-LT-081

### MS2-LT-010 — Catalog browse/search/edit

- **Checkpoint ID:** MS2-LT-010
- **Name:** Catalog browse/search/edit
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; Catalog Search Mic and Activity Compaction evidence; catalog/activity verifiers
- **Implementation commit(s):** 87a15ca Compact catalog activity history; 3a57f18 Protect out-of-stock pass and add catalog search mic; 937cc3f Normalize expiry months and repeat catalog search
- **Primary implementation files/modules:** `ms20-main-app/src/services/catalogWorkspace.js`; `ms20-main-app/src/services/activityHistory.js`
- **Owner live-test evidence:** Passed; source: CVS; Catalog Search Mic and Activity Compaction evidence; catalog/activity verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 2
- **Dependent checkpoints:** MS2-LT-011, MS2-LT-013, MS2-LT-014, MS2-LT-015, MS2-LT-016, MS2-LT-017, MS2-LT-024, MS2-LT-025, MS2-LT-040, MS2-LT-041, MS2-LT-042, MS2-LT-043, MS2-LT-044, MS2-LT-045, MS2-LT-049, MS2-LT-081

### MS2-LT-011 — Shared medicine review integrity

- **Checkpoint ID:** MS2-LT-011
- **Name:** Shared medicine review integrity
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; shared-field/readiness/reordering verifiers
- **Implementation commit(s):** 6476f7c Share medicine review row controls; 1dff3b2 Centralize editable medicine fields
- **Primary implementation files/modules:** `ms20-main-app/src/cards/editableCards.js`; `ms20-main-app/src/services/catalogReviewPolicy.js`
- **Owner live-test evidence:** Passed; source: CVS; shared-field/readiness/reordering verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 3–10
- **Dependent checkpoints:** MS2-LT-013, MS2-LT-014, MS2-LT-015, MS2-LT-049, MS2-LT-081

### MS2-LT-012 — Shared voice capture and review

- **Checkpoint ID:** MS2-LT-012
- **Name:** Shared voice capture and review
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; Mic Test 2; voice verifiers
- **Implementation commit(s):** 464674f Make card voice editing reachable inline; 09cb128 Preserve editable card voice viewport; 9afd4e4 Close unread review checkpoint and route notification actions
- **Primary implementation files/modules:** `app/transcription.py`; `ms20-main-app/src/app.js`
- **Owner live-test evidence:** Passed; source: CVS; Mic Test 2; voice verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 1
- **Dependent checkpoints:** MS2-LT-013, MS2-LT-014, MS2-LT-015, MS2-LT-049

### MS2-LT-013 — Editable-card voice viewport/focus

- **Checkpoint ID:** MS2-LT-013
- **Name:** Editable-card voice viewport/focus
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; LATP; two owner mobile screenshot sets; `voiceViewportAnchor.js`; viewport verifier; 2026-07-29 owner mobile regression screenshots after 67cfcac; earlier failed attempts remain recorded in CVS, LATP and Engineering Memory
- **Implementation commit(s):** 464674f Make card voice editing reachable inline; 09cb128 Preserve editable card voice viewport; 1dff3b2 Centralize editable medicine fields; b7ba547 Stabilize voice field viewport across mobile layout; 67cfcac Suspend chat rerenders during field voice
- **Primary implementation files/modules:** `ms20-main-app/src/services/voiceViewportAnchor.js`; `ms20-main-app/src/cards/editableCards.js`
- **Owner live-test evidence:** Passed 2026-07-29: owner screenshots prove upper Strength 10 mg to 5 mg, middle-field listening, lower Buying price 120 to 121, and Expiry 2028-09 to 2026 May to restored 2028-09 all retained the selected field in view; each review changed only one field and discard restored baseline; source: CVS; LATP; two owner mobile screenshot sets; `voiceViewportAnchor.js`; viewport verifier; 2026-07-29 owner mobile regression screenshots after 67cfcac; earlier failed attempts remain recorded in CVS, LATP and Engineering Memory
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed 2026-07-29: owner screenshots prove upper Strength 10 mg to 5 mg, middle-field listening, lower Buying price 120 to 121, and Expiry 2028-09 to 2026 May to restored 2028-09 all retained the selected field in view; each review changed only one field and discard restored baseline; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10–12
- **Dependent checkpoints:** MS2-LT-049

### MS2-LT-014 — Known-medicine sales

- **Checkpoint ID:** MS2-LT-014
- **Name:** Known-medicine sales
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; TCE Fast Record evidence; sales tests
- **Implementation commit(s):** a639e3c Harden phone medicine selector readiness; 543ddf3 Require confirmation for WhatsApp medicine selector; 78ad94d Complete Kenya medicine brain architecture pass
- **Primary implementation files/modules:** `app/intake.py`; `ms20-main-app/src/services/transactionCompletionEngine.js`
- **Owner live-test evidence:** Passed; source: CVS; TCE Fast Record evidence; sales tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10–12
- **Dependent checkpoints:** MS2-LT-019, MS2-LT-020, MS2-LT-021, MS2-LT-024, MS2-LT-026, MS2-LT-027, MS2-LT-034, MS2-LT-049, MS2-LT-050, MS2-LT-051, MS2-LT-066

### MS2-LT-015 — Restocking and delivery details

- **Checkpoint ID:** MS2-LT-015
- **Name:** Restocking and delivery details
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; voice-restock verifier; intake tests
- **Implementation commit(s):** 67560ab Fix offline confirmation delivery diagnostics and stock safety; 46f8d32 Fix offline confirmation delivery and stock safety
- **Primary implementation files/modules:** `app/intake.py`; `app/services/image_restock.py`
- **Owner live-test evidence:** Passed; source: CVS; voice-restock verifier; intake tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10–12
- **Dependent checkpoints:** MS2-LT-019, MS2-LT-020, MS2-LT-049, MS2-LT-066

### MS2-LT-016 — Stock enquiry

- **Checkpoint ID:** MS2-LT-016
- **Name:** Stock enquiry
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; `localIntelligence.js`; stock tests
- **Implementation commit(s):** d6901b9 Fix voice restock review and recovery; 5e3ee33 Answer medicine stock checks instantly; 616fda4 Keep mobile chat fixed and normalize restocks
- **Primary implementation files/modules:** `ms20-main-app/src/services/localIntelligence.js`; `app/intake.py`
- **Owner live-test evidence:** Passed; source: CVS; `localIntelligence.js`; stock tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10
- **Dependent checkpoints:** MS2-LT-019, MS2-LT-020, MS2-LT-066

### MS2-LT-017 — Manual stock correction

- **Checkpoint ID:** MS2-LT-017
- **Name:** Manual stock correction
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; `stock-fix-workflow.md`; stock-correction verifiers
- **Implementation commit(s):** 1b4de86 Stabilize guided Stock Fix conversation; c86cfc8 Stabilize Stock Fix OCR and optional reason; b5ffd6a Unify Stock Fix evidence inputs
- **Primary implementation files/modules:** `ms20-main-app/src/services/stockCorrectionExecution.js`; `ms20-main-app/src/services/stockCorrectionPolicy.js`
- **Owner live-test evidence:** Passed; source: CVS; `stock-fix-workflow.md`; stock-correction verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10
- **Dependent checkpoints:** MS2-LT-018, MS2-LT-019, MS2-LT-020, MS2-LT-066

### MS2-LT-018 — Stock Fix acquisition parity

- **Checkpoint ID:** MS2-LT-018
- **Name:** Stock Fix acquisition parity
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; stock-fix evidence/UI verifiers
- **Implementation commit(s):** 74f7f69 Focus Stock Fix OCR on package region; b9aea88 Harden Stock Fix package recognition; c86cfc8 Stabilize Stock Fix OCR and optional reason
- **Primary implementation files/modules:** `ms20-main-app/src/services/stockFixEvidencePipeline.js`; `app/services/local_stock_fix_ocr.py`
- **Owner live-test evidence:** Passed; source: CVS; stock-fix evidence/UI verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 17
- **Dependent checkpoints:** MS2-LT-019, MS2-LT-020, MS2-LT-066

### MS2-LT-019 — Corrections, cancellation and undo

- **Checkpoint ID:** MS2-LT-019
- **Name:** Corrections, cancellation and undo
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; TCE; issue-return/intake tests
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `app/intake.py`; `ms20-main-app/src/services/transactionCompletionEngine.js`
- **Owner live-test evidence:** Passed; source: CVS; TCE; issue-return/intake tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 14–18
- **Dependent checkpoints:** MS2-LT-020, MS2-LT-066

### MS2-LT-020 — Offline operation and synchronization

- **Checkpoint ID:** MS2-LT-020
- **Name:** Offline operation and synchronization
- **Category:** Core Functional Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** TRAIN; offline app/sync/queue tests
- **Implementation commit(s):** 911a830 Fix Replit startup and offline static routes
- **Primary implementation files/modules:** `app/services/offline_sync.py`; `ms20-main-app/src/services/offlineQueue.js`
- **Owner live-test evidence:** Passed; source: TRAIN; offline app/sync/queue tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 14–19
- **Dependent checkpoints:** MS2-LT-021, MS2-LT-059, MS2-LT-061, MS2-LT-066, MS2-LT-080

### MS2-LT-021 — Daily operational metrics

- **Checkpoint ID:** MS2-LT-021
- **Name:** Daily operational metrics
- **Category:** Pharmacy Operating Intelligence Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS report evidence; `reports.py`; report verifier
- **Implementation commit(s):** 9fbf0d2 Make daily report refresh truthful and read-only
- **Primary implementation files/modules:** `app/reports.py`; `ms20-main-app/src/services/localIntelligence.js`
- **Owner live-test evidence:** Passed; source: CVS report evidence; `reports.py`; report verifier
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 14, 20
- **Dependent checkpoints:** MS2-LT-022, MS2-LT-023, MS2-LT-026, MS2-LT-027, MS2-LT-028, MS2-LT-039, MS2-LT-041, MS2-LT-042, MS2-LT-043, MS2-LT-044, MS2-LT-082

### MS2-LT-022 — Direct analytics commands

- **Checkpoint ID:** MS2-LT-022
- **Name:** Direct analytics commands
- **Category:** Pharmacy Operating Intelligence Validation
- **Current status:** Implemented — awaiting owner live test
- **Repository evidence:** OI; `intake.py`; analytics/token tests
- **Implementation commit(s):** 1498960 Add POS parity commands and bridge startup hardening; 7691591 Simplify pharmacy commands and voice fallback
- **Primary implementation files/modules:** `app/intake.py`; `app/services/operational_intelligence.py`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete decisive owner live validation for: Answer cash/M-Pesa today, payment split/top method, best seller, peak hours, missed demand and profit locally.
- **Prerequisite checkpoints:** 21
- **Dependent checkpoints:** MS2-LT-023

### MS2-LT-023 — Decision-support summary

- **Checkpoint ID:** MS2-LT-023
- **Name:** Decision-support summary
- **Category:** Pharmacy Operating Intelligence Validation
- **Current status:** Partial implementation
- **Repository evidence:** OI; `deterministic_recommendations()`; current renderer gap
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `app/services/operational_intelligence.py`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the unimplemented portion and owner-validate: State what happened, why it matters and a deterministic next action without routine LLM use.
- **Prerequisite checkpoints:** 21–22
- **Dependent checkpoints:** MS2-LT-030, MS2-LT-038

### MS2-LT-024 — Low/out-of-stock intelligence

- **Checkpoint ID:** MS2-LT-024
- **Name:** Low/out-of-stock intelligence
- **Category:** Pharmacy Operating Intelligence Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; notification lifecycle evidence
- **Implementation commit(s):** dd05778 Close low stock and harden notification edits; d6901b9 Fix voice restock review and recovery; 5e3ee33 Answer medicine stock checks instantly
- **Primary implementation files/modules:** `ms20-main-app/src/services/notificationCenter.js`; `ms20-main-app/src/services/localIntelligence.js`
- **Owner live-test evidence:** Passed; source: CVS; notification lifecycle evidence
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10, 14
- **Dependent checkpoints:** MS2-LT-029, MS2-LT-030, MS2-LT-082

### MS2-LT-025 — Expiry intelligence

- **Checkpoint ID:** MS2-LT-025
- **Name:** Expiry intelligence
- **Category:** Pharmacy Operating Intelligence Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; expiry lifecycle evidence
- **Implementation commit(s):** 937cc3f Normalize expiry months and repeat catalog search
- **Primary implementation files/modules:** `ms20-main-app/src/services/notificationCenter.js`; `ms20-main-app/src/services/localIntelligence.js`
- **Owner live-test evidence:** Passed; source: CVS; expiry lifecycle evidence
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10
- **Dependent checkpoints:** MS2-LT-030, MS2-LT-082

### MS2-LT-026 — Missed-demand and lost-opportunity intelligence

- **Checkpoint ID:** MS2-LT-026
- **Name:** Missed-demand and lost-opportunity intelligence
- **Category:** Pharmacy Operating Intelligence Validation
- **Current status:** Partial implementation
- **Repository evidence:** OM future rules; `reports.py`; intake/training tests
- **Implementation commit(s):** b397234 Add media intelligence training layer; ad79c52 Add pharmacy training simulation intelligence
- **Primary implementation files/modules:** `app/reports.py`; `app/services/operational_intelligence.py`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the unimplemented portion and owner-validate: Aggregate no-stock/not-sold demand and recommend a truthful response.
- **Prerequisite checkpoints:** 14, 21
- **Dependent checkpoints:** MS2-LT-030

### MS2-LT-027 — Fast/slow/dead-stock intelligence

- **Checkpoint ID:** MS2-LT-027
- **Name:** Fast/slow/dead-stock intelligence
- **Category:** Pharmacy Operating Intelligence Validation
- **Current status:** Planned / approved
- **Repository evidence:** OM; OI; historical Operational Intelligence continuation
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Detect movement patterns, inactivity and value tied up, then recommend owner action.
- **Prerequisite checkpoints:** 14, 21, 49
- **Dependent checkpoints:** MS2-LT-028, MS2-LT-029, MS2-LT-030

### MS2-LT-028 — Stock-out and demand-risk prediction

- **Checkpoint ID:** MS2-LT-028
- **Name:** Stock-out and demand-risk prediction
- **Category:** Pharmacy Operating Intelligence Validation
- **Current status:** Planned / approved
- **Repository evidence:** OI; LATP approved improvements
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Anticipate likely stock-outs using canonical movement, lead time and confirmed unit truth.
- **Prerequisite checkpoints:** 21, 27, 49
- **Dependent checkpoints:** MS2-LT-029, MS2-LT-030

### MS2-LT-029 — Reorder-level and supplier-order intelligence

- **Checkpoint ID:** MS2-LT-029
- **Name:** Reorder-level and supplier-order intelligence
- **Category:** Pharmacy Operating Intelligence Validation
- **Current status:** Planned / approved
- **Repository evidence:** LATP Improvement 1; OI
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Suggest truthful reorder quantities, allow owner control/grouping/sending and track sourced fulfilment.
- **Prerequisite checkpoints:** 24, 27–28, 49
- **Dependent checkpoints:** MS2-LT-030, MS2-LT-048, MS2-LT-057, MS2-LT-064

### MS2-LT-030 — Operational dashboard and action prioritization

- **Checkpoint ID:** MS2-LT-030
- **Name:** Operational dashboard and action prioritization
- **Category:** Pharmacy Operating Intelligence Validation
- **Current status:** Partial implementation
- **Repository evidence:** notification center; deployment dashboard; OM/OI
- **Implementation commit(s):** 9afd4e4 Close unread review checkpoint and route notification actions; ed1d316 Automate transaction completion and simplify payment navigation
- **Primary implementation files/modules:** `ms20-main-app/src/services/notificationCenter.js`; `app/services/operational_intelligence.py`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the unimplemented portion and owner-validate: Rank urgent/value-at-risk work and expose calm next-best actions with measurable outcomes.
- **Prerequisite checkpoints:** 23–29
- **Dependent checkpoints:** None

### MS2-LT-031 — Source Brain and shared medicine matcher

- **Checkpoint ID:** MS2-LT-031
- **Name:** Source Brain and shared medicine matcher
- **Category:** AI / Learning Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; OM; matcher verifier/tests
- **Implementation commit(s):** aed9819 Block generic-only medicine voice matches; 6cc6ac7 Centralize local medicine recognition
- **Primary implementation files/modules:** `app/medicine_brain.py`; `ms20-main-app/src/services/medicineMatcher.js`
- **Owner live-test evidence:** Passed through onboarding/search evidence; source: CVS; OM; matcher verifier/tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed through onboarding/search evidence; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 2
- **Dependent checkpoints:** MS2-LT-032, MS2-LT-033, MS2-LT-034, MS2-LT-035, MS2-LT-037, MS2-LT-060, MS2-LT-081

### MS2-LT-032 — Pharmacy Catalog learning boundary

- **Checkpoint ID:** MS2-LT-032
- **Name:** Pharmacy Catalog learning boundary
- **Category:** AI / Learning Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; OM; catalog persistence evidence
- **Implementation commit(s):** 3a57f18 Protect out-of-stock pass and add catalog search mic; 937cc3f Normalize expiry months and repeat catalog search; 6ea68bb Require complete catalog search intent
- **Primary implementation files/modules:** `app/services/medicine_catalog.py`; `ms20-main-app/src/services/catalogWorkspace.js`
- **Owner live-test evidence:** Passed; source: CVS; OM; catalog persistence evidence
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 31
- **Dependent checkpoints:** MS2-LT-033

### MS2-LT-033 — Pharmacy alias/shorthand learning

- **Checkpoint ID:** MS2-LT-033
- **Name:** Pharmacy alias/shorthand learning
- **Category:** AI / Learning Validation
- **Current status:** Partial implementation
- **Repository evidence:** OI; `AdaptiveAliasLearner`; training tests
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `app/correction_learning.py`; `app/services/pharmacy_alias_store.py`
- **Owner live-test evidence:** Manual alias path passed; adaptive path untested; source: OI; `AdaptiveAliasLearner`; training tests
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the unimplemented portion and owner-validate: Learn repeated confirmed local shorthand safely, retain review and avoid dangerous promotion.
- **Prerequisite checkpoints:** 31–32
- **Dependent checkpoints:** MS2-LT-038

### MS2-LT-034 — Operational memory and reusable commands

- **Checkpoint ID:** MS2-LT-034
- **Name:** Operational memory and reusable commands
- **Category:** AI / Learning Validation
- **Current status:** Implemented — awaiting owner live test
- **Repository evidence:** `OperationalMemory`; reuse UI; intake/training tests
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `app/services/operational_intelligence.py`; `app/training_store.py`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete decisive owner live validation for: Reuse recent approved transaction context and owner commands within safe local boundaries.
- **Prerequisite checkpoints:** 14, 31
- **Dependent checkpoints:** MS2-LT-038

### MS2-LT-035 — Trusted-result/cache reuse

- **Checkpoint ID:** MS2-LT-035
- **Name:** Trusted-result/cache reuse
- **Category:** AI / Learning Validation
- **Current status:** Partial implementation
- **Repository evidence:** `trusted-result-consistency.md`; fixture history
- **Implementation commit(s):** e158ec9 Add trusted result consistency gate
- **Primary implementation files/modules:** `app/services/medicine_onboarding.py`; `ms20-main-app/src/services/brainAdapters.js`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the unimplemented portion and owner-validate: Reuse verified invoice/photo/barcode evidence before AI and keep corrections medicine/pharmacy scoped.
- **Prerequisite checkpoints:** 3, 7–9, 31
- **Dependent checkpoints:** MS2-LT-037, MS2-LT-038, MS2-LT-081

### MS2-LT-036 — Media classification and extraction routing

- **Checkpoint ID:** MS2-LT-036
- **Name:** Media classification and extraction routing
- **Category:** AI / Learning Validation
- **Current status:** Partial implementation
- **Repository evidence:** `operational_intelligence.py`; photo/intake tests
- **Implementation commit(s):** a4262e2 Strengthen local-first media and voice architecture; b397234 Add media intelligence training layer
- **Primary implementation files/modules:** `app/services/operational_intelligence.py`; `app/services/photo_intake.py`
- **Owner live-test evidence:** Core routes passed; full general classifier untested; source: `operational_intelligence.py`; photo/intake tests
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the unimplemented portion and owner-validate: Classify invoice, receipt, shelf, pack, barcode and unclear media; preserve review and safe fallback.
- **Prerequisite checkpoints:** 3, 7–9
- **Dependent checkpoints:** MS2-LT-037, MS2-LT-038, MS2-LT-081

### MS2-LT-037 — AI fallback approval boundary

- **Checkpoint ID:** MS2-LT-037
- **Name:** AI fallback approval boundary
- **Category:** AI / Learning Validation
- **Current status:** Implemented — awaiting owner live test
- **Repository evidence:** `ai_policy.py`; AI policy/token tests; ARCH
- **Implementation commit(s):** 9917fd2 Polish voice media trust and token guardrails; bbe3c73 Add pharmacy assistant training guardrails; 43ad769 Add media quota fallbacks and photo intake skeleton
- **Primary implementation files/modules:** `app/ai_policy.py`; `app/ai.py`
- **Owner live-test evidence:** Zero-AI paths passed; fallback not owner-qualified; source: `ai_policy.py`; AI policy/token tests; ARCH
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete decisive owner live validation for: Use AI only for explicitly approved unresolved voice/command/media cases with privacy, timeout, cache and cost controls.
- **Prerequisite checkpoints:** 31, 35–36
- **Dependent checkpoints:** MS2-LT-038

### MS2-LT-038 — Learning effectiveness and rollback

- **Checkpoint ID:** MS2-LT-038
- **Name:** Learning effectiveness and rollback
- **Category:** AI / Learning Validation
- **Current status:** Planned / approved
- **Repository evidence:** OI; training/reliability/learning architecture
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Measure whether approved learning/recommendations helped and allow safe correction/forgetting without cross-pharmacy leakage.
- **Prerequisite checkpoints:** 23, 33–37
- **Dependent checkpoints:** None

### MS2-LT-039 — Report periods, refresh and Read

- **Checkpoint ID:** MS2-LT-039
- **Name:** Report periods, refresh and Read
- **Category:** Reporting & Export Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; LATP report history; report verifier/tests
- **Implementation commit(s):** 94c535e Remove AI latency from MS2.0 reports; 4f9f7e0 Speed historical reports and repair speech resume; 9942219 Add deterministic historical reports and speech controls
- **Primary implementation files/modules:** `app/reports.py`; `ms20-main-app/src/services/localIntelligence.js`
- **Owner live-test evidence:** Passed; source: CVS; LATP report history; report verifier/tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 21
- **Dependent checkpoints:** MS2-LT-048, MS2-LT-071

### MS2-LT-040 — CSV Technical Data Transfer

- **Checkpoint ID:** MS2-LT-040
- **Name:** CSV Technical Data Transfer
- **Category:** Reporting & Export Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; CSV compatibility memory
- **Implementation commit(s):** c072675 Remove visible CSV byte order mark; c38ee07 Harden CSV mobile compatibility; 01cdcff Protect Export Hub workflows and advance CSV validation
- **Primary implementation files/modules:** `ms20-main-app/src/services/documentGenerator.js`; `ms20-main-app/src/services/exportFormatMetadata.js`
- **Owner live-test evidence:** Passed; source: CVS; CSV compatibility memory
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10
- **Dependent checkpoints:** MS2-LT-046, MS2-LT-047, MS2-LT-048, MS2-LT-068

### MS2-LT-041 — Excel Operations Workbook

- **Checkpoint ID:** MS2-LT-041
- **Name:** Excel Operations Workbook
- **Category:** Reporting & Export Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; Export Hub verifier
- **Implementation commit(s):** 7a6335c Prepare local Excel catalog onboarding
- **Primary implementation files/modules:** `ms20-main-app/src/services/excelInventory.js`; `ms20-main-app/src/services/ooxmlPackage.js`
- **Owner live-test evidence:** Passed; source: CVS; Export Hub verifier
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10, 21
- **Dependent checkpoints:** MS2-LT-046, MS2-LT-047, MS2-LT-048, MS2-LT-068

### MS2-LT-042 — PDF Owner Copy

- **Checkpoint ID:** MS2-LT-042
- **Name:** PDF Owner Copy
- **Category:** Reporting & Export Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; Export Hub evidence
- **Implementation commit(s):** 7a8995d Pass PDF owner copy and begin Word validation; 623a9dc Pass Excel compatibility and start phone-first PDF
- **Primary implementation files/modules:** `ms20-main-app/src/services/documentGenerator.js`
- **Owner live-test evidence:** Passed; source: CVS; Export Hub evidence
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10, 21
- **Dependent checkpoints:** MS2-LT-046, MS2-LT-047, MS2-LT-048, MS2-LT-068

### MS2-LT-043 — Word Owner Copy

- **Checkpoint ID:** MS2-LT-043
- **Name:** Word Owner Copy
- **Category:** Reporting & Export Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; Export Hub evidence
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `ms20-main-app/src/services/documentGenerator.js`; `ms20-main-app/src/services/ooxmlPackage.js`
- **Owner live-test evidence:** Passed; source: CVS; Export Hub evidence
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10, 21
- **Dependent checkpoints:** MS2-LT-046, MS2-LT-047, MS2-LT-048, MS2-LT-068

### MS2-LT-044 — Presentation Owner Briefing

- **Checkpoint ID:** MS2-LT-044
- **Name:** Presentation Owner Briefing
- **Category:** Reporting & Export Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; Export Hub evidence
- **Implementation commit(s):** d993c82 Fix Presentation briefing and export history; c561003 Pass Word owner copy and prepare Presentation briefing
- **Primary implementation files/modules:** `ms20-main-app/src/services/documentGenerator.js`; `ms20-main-app/src/services/ooxmlPackage.js`
- **Owner live-test evidence:** Passed; source: CVS; Export Hub evidence
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10, 21
- **Dependent checkpoints:** MS2-LT-046, MS2-LT-047, MS2-LT-048, MS2-LT-068

### MS2-LT-045 — Print Working Inventory

- **Checkpoint ID:** MS2-LT-045
- **Name:** Print Working Inventory
- **Category:** Reporting & Export Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; Print evidence
- **Implementation commit(s):** f8fe088 Fix same-context Print Finder capture; db1709c Fix shared Print Finder capture and reset; 6600418 Make print inventory review compact and searchable
- **Primary implementation files/modules:** `ms20-main-app/src/services/documentGenerator.js`; `ms20-main-app/src/services/medicineFinder.js`
- **Owner live-test evidence:** Passed; source: CVS; Print evidence
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10
- **Dependent checkpoints:** MS2-LT-046, MS2-LT-047, MS2-LT-048, MS2-LT-068

### MS2-LT-046 — Export Hub status/history

- **Checkpoint ID:** MS2-LT-046
- **Name:** Export Hub status/history
- **Category:** Reporting & Export Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; export history memory/verifier
- **Implementation commit(s):** 87a15ca Compact catalog activity history; 01cdcff Protect Export Hub workflows and advance CSV validation; d993c82 Fix Presentation briefing and export history
- **Primary implementation files/modules:** `ms20-main-app/src/services/exportFormatMetadata.js`; `ms20-main-app/src/app.js`
- **Owner live-test evidence:** Passed; source: CVS; export history memory/verifier
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 40–45
- **Dependent checkpoints:** MS2-LT-047, MS2-LT-048, MS2-LT-064, MS2-LT-068

### MS2-LT-047 — Cross-format canonical integrity

- **Checkpoint ID:** MS2-LT-047
- **Name:** Cross-format canonical integrity
- **Category:** Reporting & Export Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; consistency/export verifiers
- **Implementation commit(s):** 9b49581 Finish Export Hub layout integrity
- **Primary implementation files/modules:** `ms20-main-app/src/services/documentGenerator.js`; `ms20-main-app/tools/verify-export-hub.mjs`
- **Owner live-test evidence:** Passed; source: CVS; consistency/export verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 40–46
- **Dependent checkpoints:** MS2-LT-048, MS2-LT-068

### MS2-LT-048 — Future operational documents

- **Checkpoint ID:** MS2-LT-048
- **Name:** Future operational documents
- **Category:** Reporting & Export Validation
- **Current status:** Planned / approved
- **Repository evidence:** OM Documents/Future rules; LATP Improvement 1
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Generate supplier orders, GRNs, cash/finance reconciliation, expiry and supplier reports from stored truth.
- **Prerequisite checkpoints:** 29, 39–47
- **Dependent checkpoints:** MS2-LT-064, MS2-LT-068

### MS2-LT-049 — Exact form/unit/pack/price truth

- **Checkpoint ID:** MS2-LT-049
- **Name:** Exact form/unit/pack/price truth
- **Category:** Financial & Payment Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** Owner screenshot package supplied through CODEX BRIDGE v5.0; protected Production Sales Card standard; focused production-sale-card and sale-fixture verifiers
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Passed 2026-07-31: owner screenshots of the typed `Ibuprofen 1 tablet cash` review proved exact tablet form/unit, KES 18 unit/total, cash, projected stock 27 → 26, strength 200 mg, buying price KES 9, supplier Afya Wholesale Ltd, batch IBU-200C, expiry 2028-12, truthful absent optional traceability, all three Production Sales Card tabs, and no confirmed or persisted mutation.; source: Owner screenshot package supplied through CODEX BRIDGE v5.0; protected Production Sales Card standard; focused production-sale-card and sale-fixture verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed 2026-07-31: owner screenshots of the typed `Ibuprofen 1 tablet cash` review proved exact tablet form/unit, KES 18 unit/total, cash, projected stock 27 → 26, strength 200 mg, buying price KES 9, supplier Afya Wholesale Ltd, batch IBU-200C, expiry 2028-12, truthful absent optional traceability, all three Production Sales Card tabs, and no confirmed or persisted mutation.; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 10–15
- **Dependent checkpoints:** MS2-LT-027, MS2-LT-028, MS2-LT-029, MS2-LT-050, MS2-LT-074

### MS2-LT-050 — Payment modes, splits and discounts

- **Checkpoint ID:** MS2-LT-050
- **Name:** Payment modes, splits and discounts
- **Category:** Financial & Payment Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** Owner screenshot package supplied 2026-07-31; protected Production Sales Card standard; focused production-sale-card and sale-fixture verifiers
- **Implementation commit(s):** 6f91b2a Save selector quantity payment choices immediately; ad15a4f Fix deterministic routing payments and media AI wiring; ab334cf Add simple payment modes and receipt fallback UX
- **Primary implementation files/modules:** `app/intake.py`; `ms20-main-app/src/services/paymentAdapters.js`
- **Owner live-test evidence:** Passed 2026-07-31: owner screenshots of the Septrin one-bottle Credit review proved suspension/bottle identity, KES 180 unit price and total, selected Credit payment, projected stock 12 → 11, buying price KES 120, supplier MedSource Kenya Ltd, batch SEP-100S, expiry 2028-09, truthful Not recorded values, all three protected Production Sales Card tabs, and no confirmed or persisted mutation.; source: Owner screenshot package supplied 2026-07-31; protected Production Sales Card standard; focused production-sale-card and sale-fixture verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed 2026-07-31: owner screenshots of the Septrin one-bottle Credit review proved suspension/bottle identity, KES 180 unit price and total, selected Credit payment, projected stock 12 → 11, buying price KES 120, supplier MedSource Kenya Ltd, batch SEP-100S, expiry 2028-09, truthful Not recorded values, all three protected Production Sales Card tabs, and no confirmed or persisted mutation.; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 14, 49
- **Dependent checkpoints:** MS2-LT-057, MS2-LT-074, MS2-LT-084

### MS2-LT-051 — TCE Fast Record

- **Checkpoint ID:** MS2-LT-051
- **Name:** TCE Fast Record
- **Category:** Financial & Payment Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; TCE
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `ms20-main-app/src/services/transactionCompletionEngine.js`
- **Owner live-test evidence:** Passed; source: CVS; TCE
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 14
- **Dependent checkpoints:** MS2-LT-052, MS2-LT-055, MS2-LT-056, MS2-LT-066, MS2-LT-074

### MS2-LT-052 — Request & Verify success

- **Checkpoint ID:** MS2-LT-052
- **Name:** Request & Verify success
- **Category:** Financial & Payment Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; TCE; TCE/UI verifiers
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `ms20-main-app/src/services/transactionCompletionEngine.js`; `ms20-main-app/src/services/paymentAdapters.js`
- **Owner live-test evidence:** Passed; source: CVS; TCE; TCE/UI verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 51
- **Dependent checkpoints:** MS2-LT-053, MS2-LT-054, MS2-LT-055, MS2-LT-056, MS2-LT-066, MS2-LT-074

### MS2-LT-053 — Concurrent payment completion

- **Checkpoint ID:** MS2-LT-053
- **Name:** Concurrent payment completion
- **Category:** Financial & Payment Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** TCE quiet-concurrency evidence
- **Implementation commit(s):** ed1d316 Automate transaction completion and simplify payment navigation; 2e64e41 Prepare transaction completion engine
- **Primary implementation files/modules:** `ms20-main-app/src/services/transactionCompletionEngine.js`
- **Owner live-test evidence:** Passed; source: TCE quiet-concurrency evidence
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 52
- **Dependent checkpoints:** MS2-LT-054, MS2-LT-055, MS2-LT-056, MS2-LT-066, MS2-LT-074

### MS2-LT-054 — Payment failure/cancellation notification

- **Checkpoint ID:** MS2-LT-054
- **Name:** Payment failure/cancellation notification
- **Category:** Financial & Payment Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** TCE; ARCH; `notificationCenter.js`; `verify-payment-failure-notification.mjs`; 2026-07-29 owner 24-screenshot chronological package; Septrin 12-to-12 authoritative stock proof; Zinc preliminary fixture correction preserved; a76215e
- **Implementation commit(s):** a76215e Route failed payment notifications to queue; dd05778 Close low stock and harden notification edits; 9afd4e4 Close unread review checkpoint and route notification actions; c63f687 Fix pending-review notifications and Paste List capture
- **Primary implementation files/modules:** `ms20-main-app/src/services/transactionCompletionEngine.js`; `ms20-main-app/src/services/notificationCenter.js`; `ms20-main-app/src/services/saleTestFixture.js`; `ms20-main-app/tools/verify-payment-failure-notification.mjs`; `ms20-main-app/tools/verify-sale-test-fixture.mjs`
- **Owner live-test evidence:** Passed 2026-07-29: owner mobile screenshots prove Zinc Sale 1 supporting flow evidence and authoritative Septrin Sale 2 stock-preservation evidence. Septrin began and ended at numeric stock 12, quantity 1, bottle/suspension, KES 180 selling price and M-Pesa; Waiting became failed after one Simulate failed action, Payment Queue returned to 0 waiting, history retained one failed not paid/completed sale, one distinct unread actionable Sale 2 notification stated stock and paid records were unchanged, and Review payment returned to the same failed record. Zinc had blank stock and is supporting flow evidence only; its separate Sale 1 alert is not a duplicate of Septrin Sale 2.; source: TCE; ARCH; `notificationCenter.js`; `verify-payment-failure-notification.mjs`; 2026-07-29 owner 24-screenshot chronological package; Septrin 12-to-12 authoritative stock proof; Zinc preliminary fixture correction preserved; a76215e
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed 2026-07-29: owner mobile screenshots prove Zinc Sale 1 supporting flow evidence and authoritative Septrin Sale 2 stock-preservation evidence. Septrin began and ended at numeric stock 12, quantity 1, bottle/suspension, KES 180 selling price and M-Pesa; Waiting became failed after one Simulate failed action, Payment Queue returned to 0 waiting, history retained one failed not paid/completed sale, one distinct unread actionable Sale 2 notification stated stock and paid records were unchanged, and Review payment returned to the same failed record. Zinc had blank stock and is supporting flow evidence only; its separate Sale 1 alert is not a duplicate of Septrin Sale 2.; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 52–53
- **Dependent checkpoints:** MS2-LT-055, MS2-LT-056, MS2-LT-074, MS2-LT-083

### MS2-LT-055 — Refunds, returns and credits

- **Checkpoint ID:** MS2-LT-055
- **Name:** Refunds, returns and credits
- **Category:** Financial & Payment Validation
- **Current status:** Implemented — awaiting owner live test
- **Repository evidence:** 2026-07-31 through 2026-08-02 owner screenshots; shared Sale Adjustment and Sale Direct Command verifiers; Production Sales Card; TCE; offline queue/sync; consistency gate; LATP ordered 055 programme
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `app/intake.py`; `ms20-main-app/src/services/transactionCompletionEngine.js`; `ms20-main-app/src/services/saleAdjustmentReview.js`; `ms20-main-app/src/app.js`
- **Owner live-test evidence:** Original 055-A through 055-F and post-original 055-G/Direct Command 1 are owner-verified passed/frozen/protected. The 2026-08-02 055-G evidence proves `open sale 1` and `sale 1` open immutable fully-adjusted Sale 1 with Return #9, `open sale 4` opens immutable Sale 4 with Returns #7/#8, ordinary sale review remains intact, stock remains 16, queue remains 0 and navigation causes no mutation. MS2.0 permanently uses Voice first → fast tap/action second → typing last, with typed/voice parity through shared deterministic routing. Checkpoint 055 remains open only for later ordered post-original cases.; source: 2026-07-31 through 2026-08-02 owner screenshots; shared Sale Adjustment and Sale Direct Command verifiers; Production Sales Card; TCE; offline queue/sync; consistency gate; LATP ordered 055 programme
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete decisive owner live validation for: Record linked financial/stock adjustments without deleting original history, then validate approved status-card and direct-command improvements without replacing the tappable route.
- **Prerequisite checkpoints:** 51–54
- **Dependent checkpoints:** MS2-LT-056, MS2-LT-057, MS2-LT-074

### MS2-LT-056 — Undo/reversal reconciliation

- **Checkpoint ID:** MS2-LT-056
- **Name:** Undo/reversal reconciliation
- **Category:** Financial & Payment Validation
- **Current status:** Partial implementation
- **Repository evidence:** TCE; ledger/intake tests
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `app/intake.py`; `ms20-main-app/src/services/transactionCompletionEngine.js`
- **Owner live-test evidence:** Basic cancellation/undo passed; full TCE reconciliation untested; source: TCE; ledger/intake tests
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the unimplemented portion and owner-validate: Reconcile stock, finance, receipt, reports and audit exactly once for visible sale numbers.
- **Prerequisite checkpoints:** 51–55
- **Dependent checkpoints:** MS2-LT-074

### MS2-LT-057 — Supplier/restock payments

- **Checkpoint ID:** MS2-LT-057
- **Name:** Supplier/restock payments
- **Category:** Financial & Payment Validation
- **Current status:** Planned / approved
- **Repository evidence:** TCE permanent scope; supplier workflows
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Support supplier payment, credit and future settlement flows through the adapter/TCE boundary.
- **Prerequisite checkpoints:** 29, 50, 55
- **Dependent checkpoints:** MS2-LT-074

### MS2-LT-058 — Main App/backend adapter gateway

- **Checkpoint ID:** MS2-LT-058
- **Name:** Main App/backend adapter gateway
- **Category:** Integration Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; ARCH; backend adapter/route tests
- **Implementation commit(s):** 1b06cdb Serve MS2 main app through Replit backend
- **Primary implementation files/modules:** `app/main.py`; `ms20-main-app/src/services/liveBackendGateway.js`
- **Owner live-test evidence:** Passed on Replit; source: CVS; ARCH; backend adapter/route tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed on Replit; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 1
- **Dependent checkpoints:** MS2-LT-060, MS2-LT-061, MS2-LT-062, MS2-LT-063, MS2-LT-067, MS2-LT-070

### MS2-LT-059 — Google Sheets pharmacy persistence

- **Checkpoint ID:** MS2-LT-059
- **Name:** Google Sheets pharmacy persistence
- **Category:** Integration Validation
- **Current status:** Implemented — awaiting owner live test
- **Repository evidence:** onboarding/sheets tests; TRAIN
- **Implementation commit(s):** c306c33 Wire production pharmacy registry onboarding; e0a23f3 Complete pre-demo pharmacy engine upgrade; 6b9c37c Use admin workbook tabs for pharmacy onboarding
- **Primary implementation files/modules:** `app/sheets.py`; `app/services/pharmacy_onboarding.py`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete decisive owner live validation for: Provision/read/write isolated pharmacy sheets and recover safely when unavailable.
- **Prerequisite checkpoints:** 2, 20
- **Dependent checkpoints:** MS2-LT-060, MS2-LT-067, MS2-LT-073, MS2-LT-077

### MS2-LT-060 — WhatsApp/Baileys optional channel

- **Checkpoint ID:** MS2-LT-060
- **Name:** WhatsApp/Baileys optional channel
- **Category:** Integration Validation
- **Current status:** Implemented — awaiting owner live test
- **Repository evidence:** bridge docs/tests; commit history
- **Implementation commit(s):** dfda7c6 Route Baileys text through live runtime endpoint; 0ebac5b Fix Baileys LID phone identity for live onboarding; 7545006 Polish WhatsApp voice selector recovery
- **Primary implementation files/modules:** `baileys-bridge.js`; `app/whatsapp.py`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete decisive owner live validation for: Route text/voice/media through shared pharmacy logic without making it the Main App proof path.
- **Prerequisite checkpoints:** 31, 58–59
- **Dependent checkpoints:** MS2-LT-067, MS2-LT-076

### MS2-LT-061 — Offline PWA and media bridge

- **Checkpoint ID:** MS2-LT-061
- **Name:** Offline PWA and media bridge
- **Category:** Integration Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** TRAIN; offline/bridge tests
- **Implementation commit(s):** 8a27db6 Improve offline Tap and Talk first-attempt selector; cf1e787 Harden WhatsApp selector and offline Tap Talk parity; ca386fd Fix offline parity tap talk and bridge health
- **Primary implementation files/modules:** `app/services/offline_sync.py`; `offline_app/app.js`
- **Owner live-test evidence:** Passed during offline programme; source: TRAIN; offline/bridge tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed during offline programme; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 20, 58
- **Dependent checkpoints:** MS2-LT-067, MS2-LT-076, MS2-LT-080

### MS2-LT-062 — Meta/Twilio legacy webhook channels

- **Checkpoint ID:** MS2-LT-062
- **Name:** Meta/Twilio legacy webhook channels
- **Category:** Integration Validation
- **Current status:** Deprecated with repository evidence
- **Repository evidence:** README; Meta webhook tests; Baileys migration commits
- **Implementation commit(s):** 722d9e7 Add Meta callback webhook alias; 840e6dc Prepare Meta WhatsApp Cloud API webhook
- **Primary implementation files/modules:** `app/routes/meta_webhook.py`; `app/providers/meta_whatsapp.py`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** None; retain only for evidence-backed historical compatibility.
- **Prerequisite checkpoints:** 58
- **Dependent checkpoints:** MS2-LT-067

### MS2-LT-063 — Local WhatsApp Web MVP bridge

- **Checkpoint ID:** MS2-LT-063
- **Name:** Local WhatsApp Web MVP bridge
- **Category:** Integration Validation
- **Current status:** Deprecated with repository evidence
- **Repository evidence:** WhatsApp Web docs/tests; Baileys migration
- **Implementation commit(s):** d05c30f Add Windows local WhatsApp bridge setup; 995661b Migrate MVP channel to WhatsApp Web bridge; a5022ae Add WhatsApp Web MVP bridge
- **Primary implementation files/modules:** `local_whatsapp_bridge.js`; `whatsapp-web-bridge.js`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** None; retain only for evidence-backed historical compatibility.
- **Prerequisite checkpoints:** 58
- **Dependent checkpoints:** MS2-LT-067

### MS2-LT-064 — Share/email/document delivery routes

- **Checkpoint ID:** MS2-LT-064
- **Name:** Share/email/document delivery routes
- **Category:** Integration Validation
- **Current status:** Planned / approved
- **Repository evidence:** LATP Improvement 1; export metadata
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Send supported outputs/orders through safe device/share/email routes with truthful receipt state.
- **Prerequisite checkpoints:** 29, 46, 48
- **Dependent checkpoints:** MS2-LT-067

### MS2-LT-065 — Pharmacy/branch isolation

- **Checkpoint ID:** MS2-LT-065
- **Name:** Pharmacy/branch isolation
- **Category:** Security / Privacy / Compliance Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; ARCH; isolation tests/verifiers
- **Implementation commit(s):** c306c33 Wire production pharmacy registry onboarding
- **Primary implementation files/modules:** `app/pharmacy_registry.py`; `app/actor_context.py`
- **Owner live-test evidence:** Passed in protected workflows and automated gates; source: CVS; ARCH; isolation tests/verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed in protected workflows and automated gates; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** Implemented pharmacy-scoped data workflows
- **Dependent checkpoints:** MS2-LT-067, MS2-LT-068, MS2-LT-073, MS2-LT-074, MS2-LT-076

### MS2-LT-066 — Idempotency, audit and duplicate prevention

- **Checkpoint ID:** MS2-LT-066
- **Name:** Idempotency, audit and duplicate prevention
- **Category:** Security / Privacy / Compliance Validation
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; TCE; activity/export/offline verifiers
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `ms20-main-app/src/services/activityHistory.js`; `ms20-main-app/src/services/transactionCompletionEngine.js`
- **Owner live-test evidence:** Passed across protected workflows; source: CVS; TCE; activity/export/offline verifiers
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed across protected workflows; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 14–20, 51–53
- **Dependent checkpoints:** MS2-LT-068, MS2-LT-073, MS2-LT-074, MS2-LT-076, MS2-LT-077, MS2-LT-080

### MS2-LT-067 — Authentication, roles and access controls

- **Checkpoint ID:** MS2-LT-067
- **Name:** Authentication, roles and access controls
- **Category:** Security / Privacy / Compliance Validation
- **Current status:** Partial implementation
- **Repository evidence:** registry/admin/routes; ARCH; compliance plan
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `app/actor_context.py`; `app/routes/admin.py`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the unimplemented portion and owner-validate: Enforce owner/admin/branch authorization and minimum-necessary access across UI, routes and downloads.
- **Prerequisite checkpoints:** 2, 58–65
- **Dependent checkpoints:** MS2-LT-068, MS2-LT-073, MS2-LT-074, MS2-LT-076, MS2-LT-077, MS2-LT-079, MS2-LT-084

### MS2-LT-068 — Export IP/privacy/compliance safeguards

- **Checkpoint ID:** MS2-LT-068
- **Name:** Export IP/privacy/compliance safeguards
- **Category:** Security / Privacy / Compliance Validation
- **Current status:** Planned / approved
- **Repository evidence:** LATP Improvement 3
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Register assets/licences, fail closed, redact/anonymize, control IDs/sharing/retention and avoid false endorsement.
- **Prerequisite checkpoints:** 40–48, 65–67
- **Dependent checkpoints:** MS2-LT-074, MS2-LT-075, MS2-LT-076

### MS2-LT-069 — Product-secrecy and quiet-UI audit

- **Checkpoint ID:** MS2-LT-069
- **Name:** Product-secrecy and quiet-UI audit
- **Category:** Security / Privacy / Compliance Validation
- **Current status:** Planned / approved
- **Repository evidence:** CVS; LATP future audit
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Remove unnecessary internal implementation disclosures while preserving legal/safety/privacy truth.
- **Prerequisite checkpoints:** All functional/intelligence tests
- **Dependent checkpoints:** MS2-LT-075, MS2-LT-076

### MS2-LT-070 — Replit deployment and health

- **Checkpoint ID:** MS2-LT-070
- **Name:** Replit deployment and health
- **Category:** Production Qualification
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; Replit handoff; production tests
- **Implementation commit(s):** 0823d58 Disable Replit user installs inside virtualenv; 63b25d6 Use dedicated writable Replit virtualenv; 10612b3 Use project virtualenv for Replit dependencies
- **Primary implementation files/modules:** `app/main.py`; `start.sh`
- **Owner live-test evidence:** Repeatedly passed; source: CVS; Replit handoff; production tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Repeatedly passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 58
- **Dependent checkpoints:** MS2-LT-071, MS2-LT-076

### MS2-LT-071 — Startup/report observability

- **Checkpoint ID:** MS2-LT-071
- **Name:** Startup/report observability
- **Category:** Production Qualification
- **Current status:** PASS / PROTECTED
- **Repository evidence:** CVS; startup/warmup tests
- **Implementation commit(s):** 94c535e Remove AI latency from MS2.0 reports; 4081134 Retain and expose MS2.0 report source warmup; b8d738e Improve MS2.0 shared data reads and report performance
- **Primary implementation files/modules:** `app/main.py`; `app/reports.py`
- **Owner live-test evidence:** Passed; source: CVS; startup/warmup tests
- **PASS / PROTECTED confirmation:** Confirmed — Owner validation: Passed; Protected: Yes.
- **Remaining implementation work:** None; preserve against regression.
- **Prerequisite checkpoints:** 39, 70
- **Dependent checkpoints:** MS2-LT-076

### MS2-LT-072 — Architecture/consistency regression gate

- **Checkpoint ID:** MS2-LT-072
- **Name:** Architecture/consistency regression gate
- **Category:** Production Qualification
- **Current status:** Implemented — awaiting owner live test
- **Repository evidence:** all `verify-*.mjs`; regression tests
- **Implementation commit(s):** e158ec9 Add trusted result consistency gate; 48c6d47 Consolidate invoice reviews and integrate consistency gate; 5c78e1d Merge repeated invoice scans without regression
- **Primary implementation files/modules:** `ms20-main-app/tools/verify-consistency-gate.mjs`; `ms20-main-app/tools/verify-architecture.mjs`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete decisive owner live validation for: Prove zero-token defaults, protected contracts, fixtures and canonical consistency before deployment.
- **Prerequisite checkpoints:** All implemented checkpoints
- **Dependent checkpoints:** MS2-LT-076, MS2-LT-080

### MS2-LT-073 — Autonomous pharmacy provisioning

- **Checkpoint ID:** MS2-LT-073
- **Name:** Autonomous pharmacy provisioning
- **Category:** Production Qualification
- **Current status:** Implemented — awaiting owner live test
- **Repository evidence:** TRAIN Phases 12–13; provisioning tests
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** `app/provisioning.py`; `app/deployment.py`
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete decisive owner live validation for: Create isolated profile/owner/branch/catalog/queue/monitoring configuration and recover failed onboarding.
- **Prerequisite checkpoints:** 2, 59, 65–67
- **Dependent checkpoints:** MS2-LT-076, MS2-LT-077

### MS2-LT-074 — Production payment-provider qualification

- **Checkpoint ID:** MS2-LT-074
- **Name:** Production payment-provider qualification
- **Category:** Production Qualification
- **Current status:** External qualification
- **Repository evidence:** TCE; Safaricom unresolved question
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the externally gated qualification: Confirm merchant onboarding model, tenant identity, credentials, authenticated callbacks, reconciliation and official adapters.
- **Prerequisite checkpoints:** 49–57, 65–68
- **Dependent checkpoints:** MS2-LT-084

### MS2-LT-075 — Professional legal/regulatory qualification

- **Checkpoint ID:** MS2-LT-075
- **Name:** Professional legal/regulatory qualification
- **Category:** Production Qualification
- **Current status:** External qualification
- **Repository evidence:** LATP Improvement 3 pre-launch gates
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the externally gated qualification: Obtain Kenya IP, trademark, ODPC/privacy, pharmacy, payments, terms/DPA, security and retention review.
- **Prerequisite checkpoints:** 68–69
- **Dependent checkpoints:** None

### MS2-LT-076 — Production channel/scale qualification

- **Checkpoint ID:** MS2-LT-076
- **Name:** Production channel/scale qualification
- **Category:** Production Qualification
- **Current status:** External qualification
- **Repository evidence:** TRAIN; deployment/provisioning/bridge tests
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Complete the externally gated qualification: Qualify official messaging/channel operations, multi-pharmacy scale, backup/recovery, monitoring and incident response.
- **Prerequisite checkpoints:** 60–61, 65–73
- **Dependent checkpoints:** None

### MS2-LT-077 — Multiuser Pharmacy Version 1

- **Checkpoint ID:** MS2-LT-077
- **Name:** Multiuser Pharmacy Version 1
- **Category:** Launch Program Validation
- **Current status:** Planned / approved
- **Repository evidence:** Launch roadmap; multiuser locked improvement
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Let owner-approved staff join one pharmacy with fixed roles, shared truth, attribution, safe sync, device controls and consolidated reporting.
- **Prerequisite checkpoints:** 59, 66–67, 73
- **Dependent checkpoints:** MS2-LT-078, MS2-LT-079, MS2-LT-083

### MS2-LT-078 — Impala Loyalty Program Version 1

- **Checkpoint ID:** MS2-LT-078
- **Name:** Impala Loyalty Program Version 1
- **Category:** Launch Program Validation
- **Current status:** Planned / approved
- **Repository evidence:** Launch roadmap; Impala Loyalty locked improvement
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Provide a deterministic pharmacy-pooled coin wallet, earning/referral history, anti-abuse caps and owner-controlled renewal redemption.
- **Prerequisite checkpoints:** 77, 84
- **Dependent checkpoints:** MS2-LT-083

### MS2-LT-079 — Impala Community Version 1

- **Checkpoint ID:** MS2-LT-079
- **Name:** Impala Community Version 1
- **Category:** Launch Program Validation
- **Current status:** Planned / approved
- **Repository evidence:** Launch roadmap; Impala Community locked improvement
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Provide one moderated pharmacy identity with feed, posts/photos, questions, comments, appreciation, reporting and restriction controls.
- **Prerequisite checkpoints:** 67, 77
- **Dependent checkpoints:** MS2-LT-083

### MS2-LT-080 — Low-data, low-resource and desktop reliability

- **Checkpoint ID:** MS2-LT-080
- **Name:** Low-data, low-resource and desktop reliability
- **Category:** Launch Program Validation
- **Current status:** Planned / approved
- **Repository evidence:** Launch roadmap; Intelligence + Reliability locked improvement
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Measure and qualify weak-network, background-data, queue recovery, battery/memory/heat, suspension/restart and responsive desktop behavior.
- **Prerequisite checkpoints:** 20, 61, 66, 72
- **Dependent checkpoints:** MS2-LT-083

### MS2-LT-081 — Multi-medicine photo onboarding

- **Checkpoint ID:** MS2-LT-081
- **Name:** Multi-medicine photo onboarding
- **Category:** Launch Program Validation
- **Current status:** Planned / approved
- **Repository evidence:** Launch roadmap; Intelligence + Reliability locked improvement; future fixture plan
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Detect distinct packs into one compact expandable shared review, preserve uncertainty/provenance and deduplicate before save.
- **Prerequisite checkpoints:** 8–11, 31, 35–36
- **Dependent checkpoints:** MS2-LT-083

### MS2-LT-082 — Daily intelligent assistant Version 1

- **Checkpoint ID:** MS2-LT-082
- **Name:** Daily intelligent assistant Version 1
- **Category:** Launch Program Validation
- **Current status:** Planned / approved
- **Repository evidence:** Launch roadmap; Intelligence + Reliability locked improvement
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Give neutral deterministic morning/evening summaries and capture one privacy-minimized feedback item without automatic product changes.
- **Prerequisite checkpoints:** 21, 24–25
- **Dependent checkpoints:** MS2-LT-083

### MS2-LT-083 — Demo Mode certification

- **Checkpoint ID:** MS2-LT-083
- **Name:** Demo Mode certification
- **Category:** Launch Program Validation
- **Current status:** Planned / approved
- **Repository evidence:** Launch roadmap; Demo Mode certification plan
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Certify a truthful 5–10-step owner walkthrough with real workflows, no hidden intervention and no launch-blocking regression.
- **Prerequisite checkpoints:** 54, 77–82, 84
- **Dependent checkpoints:** None

### MS2-LT-084 — Subscription and multiuser billing clarity

- **Checkpoint ID:** MS2-LT-084
- **Name:** Subscription and multiuser billing clarity
- **Category:** Launch Program Validation
- **Current status:** Planned / approved
- **Repository evidence:** Launch roadmap; owner commercial decisions; provider qualification
- **Implementation commit(s):** Repository evidence not yet available.
- **Primary implementation files/modules:** Repository evidence not yet available.
- **Owner live-test evidence:** Repository evidence not yet available.
- **PASS / PROTECTED confirmation:** Not applicable.
- **Remaining implementation work:** Implement and owner-validate: Define packages, included seats, active-device/replacement rules, expiry/grace behavior, renewal totals and loyalty redemption truth.
- **Prerequisite checkpoints:** 50, 67, 74
- **Dependent checkpoints:** MS2-LT-078, MS2-LT-083

<!-- TRACEABILITY_INDEX_END -->
