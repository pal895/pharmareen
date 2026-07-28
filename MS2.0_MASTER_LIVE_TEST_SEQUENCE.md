# MS2.0 Master Live Testing Sequence

Canonicalized: 2026-07-28

This is the single authoritative roadmap for all MS2.0 owner live validation. Future Codex chats and ChatGPT/Codex Bridges must derive checkpoint order and status only from this document. Project Brain, Engineering Memory, architecture documents, handoffs and historical plans provide evidence; they must point here and must not maintain a competing sequence.

Allowed capability classifications are exactly: `PASS / PROTECTED`, `Implemented — awaiting owner live test`, `Partial implementation`, `Planned / approved`, `External qualification`, `Deprecated with repository evidence`, and `Intentionally out of scope with repository evidence`. The 76 numbered checkpoints use the first six states; an out-of-scope item is recorded in the completeness ledger below and is never silently converted into a checkpoint. A PASS requires owner evidence. Automated tests alone never create protected status.

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
| 13 | Editable-card voice viewport/focus | Keep an inline Mic reachable beside any field and preserve the exact target/viewport through transcription. | 10–12 | Implemented — awaiting owner live test | Open | No | 5 min | CVS; LATP; `voiceViewportAnchor.js`; viewport verifier |
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
| 40 | CSV Technical Data Transfer | Export canonical 35×12 machine data with safe encoding, quoting and spreadsheet protections. | 10 | PASS / PROTECTED | Passed | Yes | CVS; CSV compatibility memory |
| 41 | Excel Operations Workbook | Produce purpose-built operational sheets with reconciled metrics and complete canonical inventory. | 10, 21 | PASS / PROTECTED | Passed | Yes | CVS; Export Hub verifier |
| 42 | PDF Owner Copy | Produce readable portrait overview and complete medicine cards without clipping. | 10, 21 | PASS / PROTECTED | Passed | Yes | CVS; Export Hub evidence |
| 43 | Word Owner Copy | Produce editable owner notes/corrections document with all medicines and stable page flow. | 10, 21 | PASS / PROTECTED | Passed | Yes | CVS; Export Hub evidence |
| 44 | Presentation Owner Briefing | Produce a readable nine-slide decision briefing with correct identity and no invented claims. | 10, 21 | PASS / PROTECTED | Passed | Yes | CVS; Export Hub evidence |
| 45 | Print Working Inventory | Show mobile review/finder and complete native print preview without claiming physical completion. | 10 | PASS / PROTECTED | Passed | Yes | CVS; Print evidence |
| 46 | Export Hub status/history | Maintain one pharmacy-scoped status card, deduplicated history and no operations-feed spam. | 40–45 | PASS / PROTECTED | Passed | Yes | CVS; export history memory/verifier |
| 47 | Cross-format canonical integrity | Keep one immutable snapshot, all records/fields, valid packages, filenames and readable layouts across formats. | 40–46 | PASS / PROTECTED | Passed | Yes | CVS; consistency/export verifiers |
| 48 | Future operational documents | Generate supplier orders, GRNs, cash/finance reconciliation, expiry and supplier reports from stored truth. | 29, 39–47 | Planned / approved | Not started | No | 20 min | OM Documents/Future rules; LATP Improvement 1 |

## 5. Financial & Payment Validation

| # | Checkpoint | Objective | Prerequisite(s) | Implementation state | Owner validation | Protected | Est. live test | Evidence/document source |
|---:|---|---|---|---|---|---|---|---|
| 49 | Exact form/unit/pack/price truth | Prevent unit/strength price leakage and preserve conversions across all inputs and consumers. | 10–15 | Planned / approved | Not started | No | 20 min | LATP Improvement 2; OI prerequisite |
| 50 | Payment modes, splits and discounts | Handle Cash, M-Pesa, Card, Credit, Mixed, payment corrections and supported discounts truthfully. | 14, 49 | Implemented — awaiting owner live test | Only narrower payment paths passed | No | 15 min | `intake.py`; day-2/intake tests; commit history |
| 51 | TCE Fast Record | Record owner-confirmed transactions immediately with daily numbering and exact one-time stock/finance effects. | 14 | PASS / PROTECTED | Passed | Yes | 10 min | CVS; TCE |
| 52 | Request & Verify success | Queue non-cash request, continue serving and complete only after verified success. | 51 | PASS / PROTECTED | Passed | Yes | 12 min | CVS; TCE; TCE/UI verifiers |
| 53 | Concurrent payment completion | Keep multiple waiting payments isolated, support out-of-order success and prevent duplicate stock effects. | 52 | PASS / PROTECTED | Passed | Yes | 12 min | TCE quiet-concurrency evidence |
| 54 | Payment failure/cancellation notification | Preserve stock/paid records and create one durable action-needed Notification without chat noise. | 52–53 | Implemented — awaiting owner live test | Next after checkpoint 13 | No | 8 min | TCE; ARCH; notification implementation |
| 55 | Refunds, returns and credits | Record linked financial/stock adjustments without deleting original history. | 51–54 | Partial implementation | Not owner-qualified end to end | No | 15 min | TCE; issue-return tests; intake history |
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
| 68 | Export IP/privacy/compliance safeguards | Register assets/licences, fail closed, redact/anonymize, control IDs/sharing/retention and avoid false endorsement. | 40–48, 65–67 | Planned / approved | Not started | No | LATP Improvement 3 |
| 69 | Product-secrecy and quiet-UI audit | Remove unnecessary internal implementation disclosures while preserving legal/safety/privacy truth. | All functional/intelligence tests | Planned / approved | Not started | No | CVS; LATP future audit |

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

## Repository completeness ledger

This ledger deliberately accounts for owner-facing domains discovered across current and historical Project Brain/Engineering Memory, plans, architecture, handoffs, commits/diffs, implementation, tests and fixtures. It does not create parallel checkpoints or change checkpoint counts.

| Capability/domain | Classification | Accounted by | Repository evidence boundary |
|---|---|---|---|
| Sales, receipts and daily numbering | PASS / PROTECTED | 14, 51 | Sales/TCE owner evidence and tests |
| Catalog, medicine editing, search and Activity History | PASS / PROTECTED | 10–11, 31–32, 66 | Catalog Search Mic and Activity Compaction owner evidence; catalog/activity verifiers |
| Stock management, stock checks, fixes and restocking | PASS / PROTECTED | 15–18, 24–25 | Stock Fix owner sequence; stock/restock tests |
| Exact unit, form, pack, conversion and price truth | Planned / approved | 49 | LATP ordered Improvement 2 |
| Supplier ordering, fulfilment and supplier payments | Planned / approved | 29, 48, 57 | LATP ordered Improvement 1; TCE permanent scope |
| Reorder, stock-out, demand, fast/slow/dead-stock and expiry intelligence | Planned / approved | 26–30 | OI; OM Future rules |
| Operational metrics, analytics, dashboard and decision support | Partial implementation | 21–23, 30 | Protected reports plus unqualified/partial intelligence renderers |
| Notifications, unread/action routing and quiet state | Implemented — awaiting owner live test | 24–25, 54 | Inventory/expiry lifecycles protected; payment failure remains open |
| Payment modes, split/mixed payments and discounts | Implemented — awaiting owner live test | 50 | Intake/TCE implementation and narrower protected payment evidence |
| Payment failure/cancellation | Implemented — awaiting owner live test | 54 | TCE provider-event and notification boundary |
| Refunds, returns, credits and undo/reversal | Partial implementation | 19, 55–56 | Basic cancellation protected; full financial reconciliation remains unqualified |
| Cash/finance reconciliation | Planned / approved | 48, 56–57 | OM Future rules; TCE reconciliation hooks |
| Reports, periods, speech controls and performance | PASS / PROTECTED | 21, 39, 71 | Report owner evidence, zero-AI latency/warmup history and tests |
| CSV, Excel/XLSX, PDF, Word, Presentation and Print | PASS / PROTECTED | 40–47 | Export Hub owner evidence and cross-format verifiers |
| Future operational document generation | Planned / approved | 48 | OM Documents; LATP |
| Export and Activity history | PASS / PROTECTED | 10, 46, 66 | Activity/Export History owner evidence and verifiers |
| Voice and contextual microphone editing | Implemented — awaiting owner live test | 12–13 | Shared voice is protected; contextual viewport/focus is current |
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
| Subscription collection | External qualification | 74 | TCE separates the MS2.0 merchant account; production merchant qualification is externally gated |
| Insurance settlements and branch transfers | Intentionally out of scope with repository evidence | None | TCE names them only as future extension points; no approved owner workflow or test programme exists |
| Generic anomaly engine beyond named rules | Intentionally out of scope with repository evidence | None | OI explicitly records no approved standalone anomaly programme |
| Legacy XLS parsing | Intentionally out of scope with repository evidence | 6 | Current XLSX checkpoint explicitly requires an honest unsupported-XLS result |

## Canonical status totals

- Total checkpoints: **76**
- PASS / PROTECTED: **42**
- Implemented — awaiting owner live test: **10**
- Partial implementation: **9**
- Planned / approved: **10**
- External qualification: **3**
- Deprecated with repository evidence: **2**

## Current execution pointer

The only current open checkpoint is **#13 Editable-card voice viewport/focus**. Checkpoints #14–#21 are already protected and must not be repeated without regression evidence. After #13 passes, execute the inherited isolated checkpoint **#54 Payment failure/cancellation notification**, whose prerequisites #52–#53 are protected. Then resume ascending order among eligible unpassed checkpoints, honoring every prerequisite.

## Canonical synchronization invariants

1. No Project Brain, Engineering Memory, architecture snapshot, test plan, handoff, bridge or synchronization package may publish an independent checkpoint list, count, order, prerequisite or status.
2. Every future Codex chat and ChatGPT/Codex Bridge must read this file before reporting or selecting live validation and must treat all embedded historical “next” statements as evidence only.
3. Any approved capability discovered later must be reconciled here in the same commit as its supporting-document reference; it may not be inserted only into a bridge or secondary plan.
4. A checkpoint may change status only here, with owner evidence for `PASS / PROTECTED`; dependent documents may record detail but cannot override it.
5. A deletion, merge, split, renumbering, prerequisite change or deprecation requires repository evidence, updated totals, an updated completeness-ledger row and same-commit synchronization of directly affected references.
6. Before push, validate unique checkpoint numbers/names, allowed states, totals, acyclic prerequisites, one current pointer and canonical-reference headers in every tracked Markdown governance/support document.
