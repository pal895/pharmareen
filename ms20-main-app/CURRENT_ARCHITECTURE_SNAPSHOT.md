# MS2.0 Current Architecture Snapshot

## Shared Production Sales Card boundary — 2026-07-29

- One canonical model: `src/services/productionSaleCard.js`.
- One canonical renderer: `productionSaleCardBody` in `src/app.js`.
- One compact presentation rule: Fast action is summary-first and approval-ready; full inputs exist only in explicit Correct mode. Secondary facts use compact on-demand lists.
- Sale correction fields reuse the Catalog contextual Mic presentation and shared `startVoiceCapture()` root. A workflow-local speech service or permanently expanded Sale form is prohibited.
- Active editable/review cards own the viewport during inline mutation. `preserveInlineCardViewport()` captures the card through `voiceViewportAnchor.js`; `render()` restores it instead of invoking chat-bottom scrolling. Actual new feed/card additions clear that ownership and retain deliberate conversation auto-scroll.
- Sales field voice uses the same exact-field anchor but updates its existing DOM in place for the complete recognition lifecycle, preserving the carousel node and selected slide. When a card is removed and its target cannot be restored, render deliberately positions the long conversation at its recent end rather than accepting a zero scroll offset.
- Per-medicine pack truth is `baseStockUnit` + `unitConversions` + `unitPrices`. Parsing separates selling unit from identity; transaction metadata and stock mutation carry the base-unit deduction. Missing pack truth blocks instead of guessing.
- Typed and voice inputs both resolve to `SaleCard`; no instant typed write and no `VoiceReviewCard`.
- Review, correction, Payment Queue, payment verification and failed-payment recovery preserve the same exact medicine/form/unit/quantity/unit-price/total/payment/stock/status fields.
- Per-unit price and stock-conversion maps are retained at the Pharmacy Brain boundary. Ambiguous units/forms are explicit choices; missing or unsafe truth blocks Confirm.
- Transaction metadata carries the canonical sale projection so queue/history/notifications do not reconstruct a divergent card.
- Owner live approval passed on 2026-07-30. The single compact three-tab Production Sales Card, its shared microphones/manual correction, viewport ownership, safe pack clarification and catalog-context preservation are protected. MS2-LT-049 is the next pending checkpoint and is not yet passed.
- Recovery audit: terminal payment is parsed before identity, explicit-payment commands safely default quantity to 1, spaced/compact quantities are excluded from identity, and canonical catalog hydration supplies all known fast/stock/trace facts. The shared renderer owns the three approved sections. Optional traceability never blocks confirmation; critical unknowns and contradictions do.

Canonical live-validation authority: `../MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`. Architecture evidence may change checkpoint state only by updating that master in the same commit.

The master’s completeness ledger is the architecture-to-validation coverage index. No component, route, adapter, fixture or historical capability creates an implicit checkpoint outside it.

The generated Engineering Traceability Index in the master maps every checkpoint to repository evidence, implementation commits/files, owner evidence, remaining work and dependency edges. Architecture changes that affect any mapping must regenerate and verify that index in the same commit.

## Launch-readiness architecture direction (2026-07-29)

`../docs/engineering-memory/launch-readiness-roadmap.md` is the active priority and Launch Gate authority. Existing protected shared roots remain unchanged. New launch work must extend the pharmacy-scoped catalog, transaction engine, notification projection, offline queue/sync, audit, identity/access, report and shared editable-card boundaries rather than create parallel loyalty, community, multiuser, photo or assistant implementations.

The launch dependency order is transaction correctness; persistence/access/provisioning; Multiuser Pharmacy; billing clarity; Impala Loyalty; Impala Community; measurable low-data/resource/desktop reliability; compact multi-medicine photo onboarding; daily assistant; external qualification; and Demo Mode certification. Only one milestone may be active and the former numeric sequence cannot select work automatically.

The planned shared ownership boundaries are:

- one pharmacy/account root for owner, staff roles, devices, invitations and immutable attribution;
- one shared catalog/stock/transaction truth with local queue and idempotent sync status;
- one pharmacy-pooled Impala wallet with deterministic eligibility/caps and owner-only redemption;
- one separate moderated Impala community identity, never mixed with operational chat;
- one measured reliability harness for network bytes/requests, recovery, resources and responsive layouts;
- one compact multi-pack review that reuses existing medicine schema, matcher, provenance and editable cards;
- one deterministic daily-summary/feedback service that cannot silently change product behavior.

No production architecture for these planned checkpoints is claimed until its milestone is implemented and verified.

## Payment failure/cancellation action routing (MS2-LT-054)

`buildTransactionNotification()` in `notificationCenter.js` is the single deterministic terminal-failure projection for failed and cancelled payments. It creates a stable transaction/status ID, plain-language stock/paid safety message, zero-AI provenance and a `payment:<transaction-id>` action target. Existing notification merging retains transaction-origin alerts through catalog/expiry projection rebuilds and deduplicates unchanged terminal events. The shared Notification Card now renders `Review payment`; its target routes to the existing Payment Queue rather than creating a second payment workflow.

The Transaction Completion Engine still owns terminal-event idempotency and rejects late events from rewriting terminal truth. Only confirmed events enter `applyConfirmedPendingSale`; failed/cancelled events do not call stock, finance or feed mutation. Focused verification covers failure, cancellation, persistence, deduplication, action routing and absence of operational chat noise. Owner evidence is still required.

Owner evidence now closes MS2-LT-054. Septrin supplies the authoritative numeric `12 → 12` failure proof; Zinc remains supporting flow evidence because its stock was blank. Distinct stable transaction/status notification IDs correctly retain separate Sale 1 and Sale 2 alerts while repeated processing of the same event remains idempotent.

`src/services/saleTestFixture.js` is the deterministic preflight boundary for future sale-related live tests. It validates stable identity, numeric/sufficient stock, form, selling unit/price, conditional cost/barcode/reorder/expiry requirements, and duplicate/alias conflicts without mutating pharmacy data. `fixtures/launch-sale-test-medicines.json` records reusable reference expectations; live values must still be inspected and captured. `SALE_LIVE_TEST_FIXTURE_STANDARD.md` requires the production SaleCard, matcher, voice, TCE and queue/sync roots and prohibits test-only bypass cards.

## Notification and Catalog voice architecture (2026-07-28)

Low-stock and Out-of-Stock via Catalog Mic notification lifecycles are owner-validated and protected. Owner evidence proves the complete Cefixime `22 → 0 → 22` Mic-only round trip, one-field reviews, exact single alert through refresh, 35 medicines and final quiet restoration. `buildDeterministicNotifications()` projects alerts from the current pharmacy-scoped catalog with deterministic IDs; `mergeNotifications()` prevents duplicates, preserves read state for an unchanged fact, resets one materially changed alert to unread using a content fingerprint, and removes generated alerts when their source condition clears. Refresh/restart rebuilds the same projection from persisted catalog and card state.

The Catalog Medicine Action Card and Catalog Search use the existing shared `startVoiceCapture()` boundary. A focused editable field supplies edit intent; explicit phrases such as `current stock twenty two` are accepted; Catalog Search places the normalized transcript into the synchronized query and immediately invokes the existing local medicine matcher. Validation, change review, approval, persistence and notification refresh remain unchanged; no second microphone service or AI parsing path exists. Catalog Search Mic is owner-validated and protected: invalid speech safely returns zero results, valid speech resolves exact saved medicines, clearing restores 35, repeated use stays accurate, and no operational mutation occurs.

Long shared editable cards preserve voice reachability and target visibility through one common root. Every primary and advanced editable medicine field renders an adjacent contextual Mic; it selects that exact field and delegates to the existing `startCatalogEditVoice` and shared `startVoiceCapture` boundaries. Commit `67cfcac` gives an active contextual field session render ownership: microphone start/listening/interim/final status, selected value and validation review update the existing DOM in place; normal root replacement and `scrollChatToBottom()` do not execute. Final owner evidence on 2026-07-29 validates this contract across upper, middle, lower and Expiry positions with one-field mutation and successful discard/restoration. MS2-LT-013 is PASS / PROTECTED; the earlier failed global-rerender repairs remain historical evidence.

The master sequence owns the complete forward order and classifications. `docs/engineering-memory/operating-intelligence-program.md` remains supporting evidence only.

The Notifications Expiry Alert Lifecycle is owner-validated and protected. The shared Catalog Mic normalized Ibuprofen expiry `2026 06` to `2026-06`; the approved expiry-only change preserved 35 medicines, stock `27` and batch `IBU-200C`; deterministic notification projection created exactly one `Ibuprofen has expired` alert through refresh; restoring `2028-12` removed it and returned Notifications to Quiet.

## Shared Activity History architecture (2026-07-28)

`src/services/activityHistory.js` is the deterministic audit-event root for approved Catalog changes. `approveCatalogEdit()` is the only Catalog edit persistence boundary that records an event. Each entry is pharmacy-scoped, bounded, newest-first, idempotent, Africa/Nairobi-labelled, zero-AI and records event type, medicine, changed fields, source and saved outcome.

`src/app.js` maintains at most one durable `ActivityHubCard` per pharmacy. New saves replace its compact latest-status presentation while Activity History retains detail. Catalog search, card reopening, refresh and discarded drafts do not call the recorder. Exact legacy `Medicine updated in the Pharmacy Catalog.` feed items are removed during resume without touching sales or unrelated operational history. Activity never changes Notification projection or unread counts.

## Shared Export Hub architecture (2026-07-27)

`src/services/exportFormatMetadata.js` is the single format registry. Excel serves operational analysis; PDF professional read-only sharing; Word corrections and working notes; Presentation management decisions; Print a browser-generated physical working register; CSV machine interoperability. Reject a new format unless its distinct owner workflow is justified.

`src/app.js` maintains one deterministic compact `ExportHubCard` per pharmacy. It updates with the latest useful status and next action, opens Hub/history directly, and never emits generation feed messages. History is pharmacy-keyed, newest first, bounded, deduplicated by generation identity, metadata-only, and regenerable.

`documentGenerator.js` is deterministic, pharmacy-isolated and zero-AI. CSV starts with the canonical 12-column header, then one CRLF-terminated physical row per medicine. It uses UTF-8 without BOM because Google Sheets owner evidence rendered the BOM visibly, plus comma delimiters, standards quoting, embedded-line-break normalization, spreadsheet formula protection and leading-zero barcode preservation. Pharmacy metadata stays in the safe filename and pharmacy-scoped Export History rather than non-tabular pre-header rows. The browser creates a `text/csv; charset=utf-8` Blob and downloads it through one safe `.csv` anchor filename; there is no CSV HTTP response or `Content-Disposition` header in this local generation path. Print reports only preparation/dialog/failure states because browsers cannot prove completion or cancellation.

Protected owner-validated formats: XLSX, PDF, DOCX, nine-slide PPTX, canonical UTF-8-without-BOM CSV and four-page Print Working Inventory. Android owner evidence confirms all 35 medicines across Print pages 1/4 through 4/4 without blank pages, corruption, crash or printer selection.

Post-validation shared-root review confirms all common behavior is centralized in the immutable canonical snapshot, `exportFormatMetadata.js`, `ensureExportHubCard()`, pharmacy-keyed history, `recordExportEvent()` and common format dispatch. Future formats inherit these roots; duplicated route-specific status, history, guidance, isolation or feed behavior is prohibited.

Snapshot date: 2026-07-10

## Product Direction

MS2.0 is now centered on the Main App as the primary pharmacy product. The owner experience is messaging-first:

- Open MS2.0.
- See MS2.0 Assistant and Notifications conversations, not a technical dashboard.
- Tap into the permanent MS2.0 conversation.
- Complete first-run setup before daily workflows on a fresh device.
- Complete medicine catalog onboarding before the paused sale test.
- Type, speak, scan, or upload in the chat.
- Complete sales record instantly through the safe queue path.
- Missing or ambiguous work becomes an editable card for confirm, correct, or cancel.

The owner should not need to think about backend, Sheets, queues, route slots, tokens, adapters, or system diagnostics. Those details are available only behind Settings/Diagnostics/Admin. WhatsApp/Baileys remains a preserved optional integration layer for later.

## Current Main App Location

```text
ms20-main-app/
```

## Reporting source-read performance delta (2026-07-19)

`GoogleSheetsStore` owns one bounded source snapshot per configured pharmacy spreadsheet for Daily Log and Transactions. It is warmed after schema setup, refreshed every five minutes, expires after ten minutes, coalesces concurrent cold loads, and receives write-through updates after successful in-app log/transaction writes. Report periods and the shared daily-log/transaction readers filter this canonical snapshot locally. Store-instance ownership prevents cross-pharmacy cache leakage; oversize or unavailable snapshots fall back to the authoritative combined Sheets read. Capacity is bounded at 100,000 combined rows and non-sensitive readiness/count/age/hit/miss diagnostics are exposed with report responses; warmup completion and row counts are emitted to deployment logs. This shared layer removes repeated network waits without adding AI, report mutation, duplicate persistence, or current-stock-as-history behavior.

Routine report recommendation construction is deterministic-only. `ReportService` never calls OpenAI for Today, historical, custom-range or refreshed reports; the production factory supplies no recommender. This preserves token-minimal AI-last execution and prevents an external model round trip from dominating otherwise local cached report construction.

## Zero-unjustified-AI policy (2026-07-19)

No routine operational workflow may invoke an LLM or paid AI API unless there is a documented engineering justification. Reports, totals, stock and sales calculations, catalog lookup, date filtering, dashboards, exports, documents, invoices, order lists, barcode lookup, deterministic command parsing, cache retrieval and pharmacy data reads remain local/deterministic. `app/ai_policy.py` is the fail-closed production registry: an unregistered workflow raises before an API call. Each approval records the deterministic limitation, user value, unavailable fallback, token/cost controls, timeout, retry maximum, cache behavior, privacy scope, approval state and responsible code/owner.

The only approved production AI boundaries are uncached voice-note transcription when browser-local recognition is unavailable, ambiguous free-form command parsing only after the shared local parser fails, and explicitly enabled invoice/photo extraction only after local handling cannot produce a safe review. All remain review-first or clarification-first, use bounded timeouts, disable automatic retries, and have non-AI fallbacks. Routine report recommendations are explicitly unapproved and fail closed even if legacy dependency injection attempts to restore them.

Replit redirects backend stdout/stderr to `server.log`, so the truthful background snapshot marker was produced but hidden from the startup shell. `start.sh` now waits after health for at most 15 seconds, inspects only the newest 200 log lines as text, prints the newest real `REPORT_SOURCE_SNAPSHOT_WARMED` marker exactly once, and warns without claiming success if it does not arrive.

Completed sales now retain a stable local transaction reference at the conversation boundary. The shared receipt renderer makes each numbered completion explicitly openable, including persisted numbered receipts recoverable by Sale number. One detail card owns the Refund, Return and Credit entry points and creates linked, non-mutating adjustment reviews; it does not alter or duplicate the protected Production Sales Card.

The approved post-original Sale Direct Command programme begins through one deterministic parser and the existing completed-sale lookup/detail root. Its first isolated case accepts typed `open sale N` only, resolves an existing completed sale locally and opens the canonical immutable detail card without stock, finance, queue or adjustment mutation. Missing sales fail explicitly with no change. Adjustment actions, last-sale resolution and microphone parity remain disabled until their separately owner-gated cases.

Direct-command priority is one shared pre-medicine boundary for both typed composer input and microphone transcripts. It recognizes the narrow sale-navigation grammar before stock/catalog/medicine parsing, including `open sale N`, shorthand `sale N`, and bounded speech normalization such as `open cell one`. Text outside that grammar falls through to the existing parsers unchanged. This fixes routing ownership without changing the sales, onboarding, catalog, editable-card or adjustment engines.

All sale navigation now resolves through `openCompletedSale()` and `transactionEngine.list()`, the same persisted immutable ledger root used by receipt and reciprocal adjustment links. Command routes do not precheck transient UI/demo transaction arrays. Exact transaction IDs retain historical identity; an unqualified daily Sale number deterministically resolves the latest completed, non-reversed matching ledger record, consistent with the existing transaction lookup/undo convention. Missing records remain read-only safe failures.

Permanent interaction architecture: **Voice first → fast tap/action second → typing last**. Every supported typed operational command must accept voice transcripts wherever platform speech is available. Both inputs converge before business interpretation on the same deterministic command router and shared workflow services; no voice-only business fork and no LLM routing for deterministic commands are permitted. Typed input remains a protected fallback for accessibility, noise, unsupported platforms, offline phone speech limitations, transcript correction and owner choice. Common flows target three steps or fewer.

Direct Return routing reuses those same roots: `return sale N` resolves via `transactionEngine.list()` and `openCompletedSale()`, then delegates to `startSaleAdjustment(..., "return")`. It opens the established review-only card and does not introduce a command-specific adjustment engine or confirmation boundary.

MS2-LT-055-I is the latest owner-verified passed/frozen/protected checkpoint. Voice-routed direct Return confirmation delegates once to the unchanged shared adjustment engine, producing one linked adjustment, stock restoration and financial reversal while preserving immutable completed-sale history and fully-adjusted controls. The phone misrecognition `return cell to` caused no mutation and does not authorize broad `cell`-to-`sale` normalization. MS2-LT-055-J is the only active owner case: the priority grammar accepts exact `refund sale N` and `refund sale number N`, with numeric or bounded spoken numbers, before medicine parsing; it then reuses the persisted completed-sale resolver and shared Refund review root, with confirmation and all mutation outside this routing-only stage. Incomplete, medicine-shaped and Refund/Return `cell` forms remain rejected. Permanent interaction priority remains **Voice first → fast tap/action second → typing last**; typing is fallback, never the primary workflow.

Local app URL used during verification:

```text
http://127.0.0.1:5177/index.html
```

Replit phone testing URL:

```text
https://$REPLIT_DEV_DOMAIN/main-app/
```

The existing backend owns the bare Replit domain, so opening `https://$REPLIT_DEV_DOMAIN/` may show backend status JSON. Use `/main-app/` for Main App live product tests.

Backend URL normally expected:

```text
http://127.0.0.1:5000
```

Existing offline app route expected on backend:

```text
/offline_app/index.html
```

## Main App Modules

- `src/app.js`: Two-screen messaging Main UI shell, first-run onboarding, chat home, conversation, browser voice capture, direct camera/photo capture, instant sale receipts, editable cards, queue handling, silent cancel, and hidden diagnostics.
- `src/contracts/integrationContracts.js`: Card types, token policy, cloud memory contract, live backend routes, adapter slot names.
- `src/cards/editableCards.js`: Card field mappings and editable card helpers.
- `src/routes/routeRegistry.js`: Frontend route slots plus live backend route status/link mapping.
- `src/services/liveBackendGateway.js`: Read-only live backend probes and backend target metadata.
- `src/services/backendAdapters.js`: Adapter registry for parser, medicine brain, sale, stock, report, invoice, onboarding, sync, cloud, and external channel slots.
- `src/services/localIntelligence.js`: Local deterministic parser and known command handling.
- `src/services/brainAdapters.js`: Pharmacy Brain, Source Brain, and AI fallback placeholders.
- `src/data/sourceMedicines.js`: Seed Source Brain medicine/form/unit knowledge for onboarding tests.
- `src/services/catalogOnboarding.js`: Catalog onboarding choices, bulk paste parser, CSV/text import parser, catalog text review format.
- `src/services/notificationCenter.js`: Local deterministic Digital Operations Assistant rules and notification cards.
- `src/services/documentGenerator.js`: Local CSV/template document generation and download helpers.
- `src/services/offlineQueue.js`: Local queue and duplicate/idempotency behavior.
- `src/services/syncAdapter.js`: Queue sync placeholder.
- `src/services/cloudGateway.js`: Cloud memory placeholder.
- `src/services/visualPipeline.js`: Photo/invoice/visual scan placeholder pipeline.
- `tools/verify-architecture.mjs`: Zero-token and architecture verification.
- `tools/serve.mjs`: Static local dev server.

## Connected Safely

- Main App shell.
- Messaging app home.
- Permanent MS2.0 Assistant conversation.
- Separate Notifications workspace.
- Chat bubbles and bottom composer.
- Hidden attach/actions menu.
- First-run onboarding card.
- Browser speech capture from the Mic button.
- Honest voice recovery distinguishes offline, microphone permission, network failure, and no speech. Recognized restock speech stays a real Restock card; partial transcripts remain visible and are never completed by guessing.
- Browser speech may play a native device start sound that the web app cannot suppress without changing transcription technology. Listening stops automatically, never offers a manual Stop control, pins the exact heard transcript, replaces stale voice drafts, and keeps every voice mutation review-first.
- Browser voice startup is explicitly phased: `Wait` while the speech service prepares, then `Speak` only after the browser's real recognition/audio-start event. This prevents early words from being silently lost and keeps compact mobile composer controls readable.
- The ready phase uses `onaudiostart` only; the earlier recognition-service `onstart` event is not treated as proof that audio is being captured.
- Direct camera capture and photo library upload.
- Silent card cancel with no chat noise.
- Persistent editable-card text-size controls.
- Instant complete-sale receipt path only for medicines already in the pharmacy catalog.
- Onboarding-first catalog flow after setup.
- Bulk paste and CSV/text catalog import cards.
- CSV catalog export and bulk-paste template download.
- Local read-aloud action through browser/device speech synthesis.
- Batch, expiry, barcode, supplier, shelf, price, and stock fields on scanner/import paths.
- Deterministic notifications for catalog needed, low stock, out of stock, expiry windows, and pending review items.
- Paste List pending-review alerts are generated only after the shared editable-review transition; merely opening or typing in an input draft creates no alert. The transition refreshes the local notification projection immediately. Paste List reuses the shared microphone, camera and photo-picker acquisition lifecycles rather than maintaining separate capture code.
- The authoritative Paste List lifecycle is `paste_input` raw text → owner taps `Review list` → deterministic parsing updates that same card to `review` → exactly one linked unread notification. A notification cannot validly precede parsing because no editable review target exists yet.
- NotificationCard uses one shared action boundary: linked operational actions render as compact primary buttons and route to their existing pending review; informational notifications render values only. Action labels are never duplicated as field-like inputs.
- Owner validation protects the complete linked-review lifecycle: the compact `Review import` action reopens the exact existing editable draft, never creates a duplicate, and Cancel/Approve removes its deterministic notification while leaving the saved catalog unchanged.
- Inventory notification thresholds remain centralized in `notificationCenter.js`: numeric stock at or below zero is out of stock; numeric stock from one through five is low stock. Catalog approval refreshes this projection immediately. Blank stock is unknown and does not create a low-stock claim.
- Editable card workspace.
- Local deterministic sale parser.
- Local deterministic restock parsing with canonical medicine matching, explicit positive stock quantity, separate bonus stock, reusable saved details, optional delivery traceability, and a three-section owner review before mutation.
- Generic forms and units such as syrup, tablet, bottle, pack, or box are never sufficient medicine identity. Shared matching returns a blocked clarification instead of selecting an arbitrary catalog medicine.
- Offline queue.
- Duplicate/idempotency demo.
- Live backend readiness route mapping.
- Offline app link.
- Google Sheets readiness detection through `/live/readiness`.
- Baileys route exposed as external channel route metadata.
- Report route metadata.
- Onboarding card placeholder.
- Medicine catalog onboarding foundation.
- Photo/invoice review-first scanner adapter foundation.

## Preserved Existing Systems

These systems were intentionally preserved and not rewritten:

- Existing backend under `app/`
- Existing offline app
- Existing Baileys/WhatsApp bridge
- Existing Google Sheets integration
- Existing reports logic
- Existing stock/sale backend logic
- Existing secrets
- Existing WhatsApp session/auth state

## Current Safety Boundary

The Main App is live-wired through adapters, but write behavior is still protected:

```text
writeMode: safe_queue_only
```

This means:

- Cards can be created.
- Cards can be reviewed.
- Cards can be queued.
- Backend target metadata can be attached.
- Live production sale/stock mutations are not automatically performed from every screen yet.

This is expected and correct after the safe merge.

## Token Safety

The Main App currently uses zero OpenAI/API tokens.

Verification checks confirmed:

- No OpenAI provider client in runtime sources.
- Known sale parser path is local-first.
- Visual/photo placeholder does not call AI.
- Bulk paste and CSV/text imports do not call AI.
- Notifications and expiry calculations do not call AI.
- Backend status probes only local/current backend endpoints.

## Branding

Current Main App user-facing brand is MS2.0.

Verified:

- `index.html` title uses `MS2.0 Main App`.
- `tools/verify-architecture.mjs` checks that old user-facing brand text is not present in `src/app.js` or `index.html`.

Internal historic file names and old project artifacts may still contain legacy names. Do not rename internal/project files during live testing unless a user-facing conflict is verified.

## Verification Summary

Passed:

- `npm run verify`
- `npm run check`
- `node --check src/services/liveBackendGateway.js`
- `node --check src/services/catalogOnboarding.js`
- `node --check src/services/notificationCenter.js`
- `python -m py_compile app/main.py app/live_runtime.py app/local_first_parser.py app/sheets.py`
- HTTP 200 for `http://127.0.0.1:5177/index.html`
- Browser load inspection
- Browser console error check
- Deterministic architecture proof for source brain lookup, bulk paste import, CSV import, notification rules, CSV export, visual token control, and zero OpenAI/API use

Known caveat:

- Browser click automation through the in-app browser tool timed out. Use manual browser testing or focused app-module tests when the browser tool is flaky.

## Not Ready Yet

Not yet complete:

- Direct production write sync from every confirmed Main App card.
- Real OCR, barcode decoding, PDF extraction, binary Excel parsing, and near-duplicate image recognition are adapter-ready but not fully implemented.
- PDF/Excel document generation is reserved for the document adapter path.
- Full live Main App workflow validation.
- Full mobile usability validation.
- Real owner friction review.
- Final production polish.

## Next Correct Work

Continue with Main App live product testing only:

1. Start the Main App.
2. Resume from onboarding, not sale testing.
3. Verify setup then medicine catalog onboarding choices.
4. Test paste/CSV/photo/scan/import paths one at a time.
5. Record friction.
6. Fix only verified friction.
7. Preserve backend/offline/Baileys/Sheets systems.
8. Keep OpenAI/API usage at zero unless explicitly required.

Paused original sale test remains:

```text
Test 1.4: Panadol 2 cash
```

Replacement next test is onboarding:

```text
Onboarding Test A.1: open the MS2.0 Assistant and confirm catalog onboarding choices appear before sale testing.
```

## 2026-07-11 Architecture Continuation

The Main App now has one reusable catalog spelling resolver used by parsing and pharmacy lookup. Canonical catalog names flow into sale/restock cards and confirmations. Accepted next architecture work extends this same resolver—rather than parallel matchers—for autocomplete, voice, scanning, imports, duplicate checks, medicine action cards, and canonical reporting.

The resolver now includes a bounded phrase-level phonetic skeleton for accent- and recognizer-shaped catalog text. It runs locally after exact/normalized comparisons, never creates a medicine, preserves strength ambiguity, and retains the generic-form identity block. The command parser also converts common spoken English/Kiswahili number words into editable sale/restock quantities. Medicine Match confirmation shares a readiness gate requiring medicine, positive quantity, supported payment, and positive selling price.

## Transaction Completion Engine

MS2.0 uses one Transaction Completion Engine rather than a standalone Payment Engine. Sales, subscriptions, supplier/restock payments, refunds, reversals, credits, and future settlement workflows share this completion boundary.

Completed sales and all Refund/Return/Credit outcomes use one deterministic Sale Adjustment engine. Reviews share remaining-quantity enforcement, explicit stock/payment consequences and a single idempotent Confirm boundary. Confirmed adjustments persist locally with permanent original linkage, audit identity/timestamps, proportional base-stock restoration where authorized, and stable offline queue IDs. Refund never assumes stock restoration; Credit never claims a cash/M-Pesa refund. Adjustment receipts and original sales provide reciprocal navigation, and original transactions remain immutable.

The shared adjustment presentation uses everyday pharmacy wording and separates quantity, money, stock and audit identity. Mutually exclusive choices retain an obvious green/checkmarked selected state. Owner titles lead with `Refund/Return/Credit for Sale N`; record sequence appears only as secondary `record #N` audit text across receipts, details and original-sale links.

- Completion modes: Always Fast Record, Always Request & Verify, or Always Ask.
- Providers are isolated behind Payment Adapters.
- Simulator-first development is mandatory before official M-PESA/card adapters.
- Pending requests enter a non-blocking Payment Queue.
- Global transaction IDs coexist with owner-facing daily `Sale N` numbering.
- Undo creates linked reconciliation/reversal history and never deletes a sale.
- Operational Confidence may preselect or suggest but never silently execute a financial action.

The local foundation is implemented and documented in `docs/engineering-memory/transaction-completion-engine.md`. Existing confirmed sales use Fast Record through the TCE. Owner-facing Setup selection, Request & Verify queue screens, full reconciliation hooks, subscription UI and official providers remain staged future work.

Pharmacy payments are tenant-owned: customer funds go directly to each pharmacy's authorized merchant account. MS2.0 subscriptions use a separate MS2.0-owned merchant account. Credentials stay in encrypted backend storage and never in client code, chat, logs, Sheets or Git.

Future production supports either direct per-pharmacy merchant connections or an explicitly approved platform/aggregator arrangement through the same Payment Adapter contract. The platform model remains disabled until confirmed. Provider capabilities determine which verified actions the UI may offer.

Unresolved production question: whether Safaricom permits an approved multi-tenant SaaS authorization model for independently owned pharmacies or requires separate Daraja production applications. No answer is assumed; direct provider confirmation is required.

Implemented and live-verified:

- Unique spelling variation resolution (`Cefimixe` → `Cefixime`).
- Simple sale and restock confirmations with stock left.
- One-time local sale deduction and restock addition through queue idempotency.
- Catalog stock persistence across refresh.
- Fixed mobile app shell with internal conversation scrolling.

Planned at their proper test stages:

- Pharmacy-specific alias/correction learning and strength/form-aware ambiguity.
- Local autocomplete in the normal chat composer.
- Shared live medicine action card.
- Deterministic packaging/unit navigation.
- Canonical reporting/export proof.
- Full onboarding, scanner/import, document, completion-state, token-log, offline/reconnect, and representative device coverage already accepted in the live plan.

## Automatic transaction completion boundary

- Simulator and future authenticated provider results enter the same TCE `providerEvent` root.
- Supplied tenant, branch, merchant, payment-request and amount identity must match before completion.
- Concurrent requests are isolated; duplicate and late events cannot repeat or rewrite terminal effects.
- Confirmed stock applies once. Failure/cancellation creates no stock movement or paid receipt and is routed to Notifications.
- Simulator actions are visible only in simulator mode and rejected by the TCE in production mode.
- The redundant home SHOW ME tile is removed; header, typed/voice, and result-card catalog routes remain protected.
- Mobile live evidence on 2026-07-18 confirms home retains MS2.0 Assistant, Notifications and Payment Queue, the header catalog route opens all 35 saved medicines, and closing it causes no mutation or operational noise.
- Mobile live evidence on 2026-07-18 confirms two concurrent Simulator M-Pesa requests can complete second-first without cross-request mutation: each stock change applies once, the queue reaches zero, history/receipts stay truthful and routine success creates no Notification. Protected stocks are Cefixime 23 and Losartan 37.
- Stock Fix uses one shared execution policy after canonical validation. Online Confirm updates durable local catalog stock immediately and records one completion without a pending duplicate; offline or unavailable durable storage retains one idempotent correction that startup/reconnect applies automatically, with no ordinary manual Sync step.
- Manual, Catalog, picture and guided-voice Stock Fix entry now hydrate one authoritative cross-slide draft. Shared live readiness prevents visible/control drift, one active slide is persisted, local speech synthesis supplies concise Read controls, local picture evidence is catalog-matched without invention, and pharmacy-scoped pronunciation learning cannot alter canonical names or cross tenants.
- Stock Fix trusted stock reads canonical `stockLeft` plus protected legacy stock shapes through one shared boundary. Its local Read review is segmented by slide so Android/Chrome Pause/Resume remains deterministic and the visible section always follows the words being spoken.
- Stock Fix keeps the fast owner path to three main choices: Confirm, a single stateful Read control, and More. Medicine selection fills trusted saved stock when there is one safe catalog match. Owner copy says `Stock updated` only after durable online application and explains automatic update plainly only in the offline fallback.
- Camera, Photo and File are equivalent image sources for one Stock Fix evidence pipeline: bounded local resize/compression, local Tesseract extraction, deterministic catalog matching, one normalized result contract and one shared draft. Temporary image resources are released, older scans are cancelled, unsupported files cannot enter onboarding, saved catalog stock remains authoritative, and corrected stock is never inferred. Guided microphone entry resolves through the same catalog/draft boundary and applies spoken Confirm once.
- Mobile live evidence on 2026-07-18 confirms the Stock Fix Photo source: Prednisolone resolved with trusted catalog stock 24 without low-memory failure, one owner-confirmed correction applied 24 to 23 immediately, and the saved Medicine Action Card independently retained stock 23 with no pending duplicate or catalog-edit approval. Camera, File and microphone remain separate live source checkpoints.
- The next isolated source checkpoint is Camera using the committed Metronidazole 400 mg carton. Its image contains package evidence only; the Stock Fix pipeline must source current stock 36 exclusively from the saved Pharmacy Catalog, leave correction/reason owner-entered, and converge on the same immediate execution boundary. File and microphone remain later distinct checkpoints.
- Initial Camera evidence showed one safe no-match followed by one correct match from the same clear Metronidazole carton. The shared local OCR boundary now unions unique lines from complementary normal and binary layout passes instead of retaining only the longest pass, preventing usable medicine evidence from being discarded before deterministic catalog matching. This remains local and zero-token across Camera, Photo and File.
- Stock Fix reason is optional for rush-hour operation. Canonical saved medicine, authoritative current stock, a different non-negative corrected stock and explicit Confirm remain required; supplied reason is preserved, while omission stays blank in the audit and is presented as `not provided` without invented text.
- Mobile evidence confirms optional Reason through immediate Metronidazole 35 to 34 application and independently saved stock 34. Camera consistency remained open after one no-match followed by one correct match, so local OCR now includes bounded package-region passes and the shared evidence matcher can recover a missed name only from a unique exact catalog barcode, unique exact batch, or unique strength-plus-expiry pair. Generic or duplicated evidence remains blocked; stock and correction authority are unchanged.
- A further no-match/then-match pair proved the initial package crop remained too broad and small for screen-displayed cartons. Package OCR now uses a tighter lower-center crop enlarged to a stable width, normal and binary layouts, and a dedicated upper-package identity pass, while retaining whole-frame evidence and the same strict catalog-identity safeguards.
- Mobile live evidence after `74f7f69` closes the Stock Fix Camera source: repeated acquisition retained canonical Metronidazole, recognized 400 mg strength and trusted saved stock 34 across the complete draft, while blank correction/reason caused no mutation. Camera is protected; File and microphone remain separate source checkpoints.
- The next isolated source checkpoint is File using a committed normal Ibuprofen 200 mg PNG. It must remain inside Stock Fix, reuse the same bounded OCR/evidence/draft/execution boundary, source current stock 28 only from the saved catalog, and leave correction/optional reason owner-controlled. Microphone remains later.
- Mobile live evidence on 2026-07-18 closes the Stock Fix File source: a normal Ibuprofen PNG stayed inside Stock Fix, resolved canonical Ibuprofen 200 mg with catalog-authoritative stock 28, applied one owner-confirmed correction to 27 with optional Reason blank, and independently persisted stock 27 without onboarding leakage, catalog-edit approval or pending duplication. Guided microphone remains the final distinct source checkpoint.
- The final guided-microphone checkpoint uses saved Co-Amoxiclav at trusted stock 24. Guided voice remains catalog-first and ambiguity-safe, and optional Reason cannot bypass review: the first spoken Confirm on an unreviewed complete draft starts the local three-section review, which says `not provided` for blank Reason and resumes listening after speech; only a second spoken Confirm reaches the shared one-time execution boundary. The isolated live target is 24 to 23 with canonical identity retained and no pending duplicate.
- Initial Android evidence exposed a browser speech-capture observability failure: the control could remain in `Speak` without yielding heard text or a terminal error. The shared capture boundary now displays interim/final transcripts, stops on speech end or an eight-second bound, reports absent completed transcripts, and prevents unmatched/ambiguous Stock Fix medicine speech from silently starting another capture. Interpretation remains catalog-first and no stock authority changed.
- Observable Co-Amoxiclav evidence then isolated guided-stage drift and natural-stock-phrase gaps: canonical identity/current stock could fill while the carousel/prompt remained on Medicine, ordinary `new stock 23` speech was not reliably parsed, and the ready final card did not consistently acknowledge success or state the next action. Guided Stock Fix now derives stage from completed fields, retains a bounded visible utterance log, accepts current-plus-new/new-stock-only speech and explicit blank reason, caches safe matched pronunciation variants only inside the pharmacy, and uses device speech synthesis to acknowledge each stage and announce the next instruction before listening resumes. Review-before-confirm and one-time mutation remain unchanged.
- Owner evidence closes the Co-Amoxiclav one-time mutation at 24 to 23, with canonical identity, transcript history, blank Reason, saved stock and no visible duplicate retained. Medicine Action Card status is no longer hard-coded: the shared catalog review result now drives `Saved medicine`, `Unsaved changes` or `Needs attention` plus matching guidance, including live field-edit transitions. This prevents unchanged saved records from falsely claiming an unsaved draft.
- Live evidence after `a7fbc82` confirms the shared presentation boundary: reopened Co-Amoxiclav shows `Saved medicine`, stock 23, complete retained fields, no changes and disabled approval. The remaining guided-voice consistency checkpoint uses Cetirizine 45 to 44 and pauses on the full local review before the post-review Confirm.
- Cetirizine evidence exposed that draft readiness and completed review shared one UI flag, allowing the first spoken Confirm to apply 45 to 44. Guided Stock Fix now separates review started from review completed. Reason completion cannot unlock execution; only completion of every local review segment does, interrupted review stays blocked, and any field change invalidates the completed state. The repair checkpoint uses saved Cetirizine 44 to 43 and stops after review.
- Evidence after `8e273f6` confirms first Confirm is review-only and Cetirizine stays 44. The shared guided-confirmation boundary now also makes the two-confirm contract discoverable before review, applies equally to voice and button input, speaks the exact second action after review, and preserves it instead of replacing it with a generic silence error.
- Live evidence after `a2211a0` closes Guided-Voice Stock Fix: the explicit first Confirm reviewed all three sections, the explicitly requested second Confirm applied Cetirizine 44 to 43 once, and the saved canonical card retained complete data with no draft or duplicate. The next isolated feature-map stage is the read-only Report entry checkpoint.
- Initial Report evidence exposed an internal route and catalog-CSV action on a request placeholder. Report now uses the existing daily-report backend through one owner-safe Generate/Refresh boundary, suppresses WhatsApp delivery, renders returned report text read-only, hides technical routing, and reports offline/backend failure honestly. Document downloads remain a later Export Hub checkpoint.
- The first generated response exposed shared card-schema drift: generation succeeded but the renderer still reserved `backend_route` and omitted returned report fields. Report now has one canonical presentation schema for period, focus, report date and read-only report text, with outcome-derived guidance.
- Production evidence after `342c359` closes the report path: startup exposed `REPORT_SOURCE_SNAPSHOT_WARMED logs=0 transactions=0`; immediate Last 7 days refreshes completed in 0.6 and 0.3 seconds; the inclusive saved-record range, historical-stock honesty, no-WhatsApp and no-duplicate-save boundaries held; and OpenAI usage did not change. Routine reports are deterministic, snapshot-backed and zero-AI.
- Export architecture is the next incomplete shared boundary. The current product has a catalog CSV generator but no owner-facing Export Hub or genuine Excel, PDF and Word generators. The next implementation must derive every format from one canonical pharmacy-scoped document model, preserve format-specific presentation and download semantics, and prohibit AI/API formatting.
- Export Hub now derives CSV, XLSX, PDF, DOCX, PPTX and print-ready HTML from one immutable `ms20.inventory-export.v1` model. The model receives only the active pharmacy identity and its canonical catalog rows; format renderers have no global pharmacy access, network call or AI boundary. This preserves tenant isolation and exact cross-format values by construction.
- The shared generator includes a local stored-ZIP/OOXML packager for genuine Office files, a deterministic paginated PDF writer, UTF-8 CSV with spreadsheet guidance, and a responsive repeating-header print view. All formats include pharmacy identity and Africa/Nairobi generation time, use safe owner filenames, and share the professional mobile-first MS2.0 document palette and hierarchy.
- The `+` menu exposes one Export Hub card rather than independent copied workflows. Its six format actions share one download controller and truthful status boundary; generation is read-only and makes no catalog, approval, queue, WhatsApp, backend or API mutation.
- Live evidence after `32bcaef` confirms the responsive Export Hub opens with 35 medicines, the active pharmacy/branch, all six formats, and explicit local/pharmacy-isolated/canonical/zero-AI wording. CSV acquisition is not yet evidenced because the visible state remains `None yet`; no filename or Downloads entry is shown.
- Follow-up mobile evidence closes CSV acquisition: one tap generated one 2.53 KB Android download, advanced the in-app status with 35 medicines and an Africa/Nairobi timestamp, retained the shared isolation/canonical/zero-AI boundary, and coincided with zero OpenAI tokens and requests. Excel acquisition is the next isolated format checkpoint.
- Export Hub is a read-only workspace, not an approval card. Its shared action renderer now suppresses inherited Confirm/Read/Correct/Cancel controls while retaining direct format downloads, status, Details and close controls. This prevents unrelated generic card actions from appearing across every export format.
- Mobile evidence after `f137c10` closes Excel acquisition with one 29.49 KB XLSX, 35 medicines, an Africa/Nairobi timestamp, no inherited actions and zero OpenAI use. The shared owner-note boundary now also states that format downloads require no confirmation, replacing the last generic approval instruction before PDF validation.
- Mobile evidence after `840642a` closes PDF acquisition with one 13.63 KB PDF, 35 medicines, an Africa/Nairobi timestamp, truthful no-confirmation guidance and zero OpenAI use. Word acquisition is the next isolated format checkpoint.
- Mobile evidence closes Word acquisition with one 59.65 KB DOCX, 35 medicines, an Africa/Nairobi timestamp, truthful no-confirmation guidance and zero OpenAI use. Presentation acquisition is the next isolated format checkpoint.
- Mobile evidence closes Presentation acquisition with one 220.07 KB PPTX, 35 medicines, an Africa/Nairobi timestamp and zero OpenAI use. The Print-ready browser view is the next isolated format checkpoint; device printing remains a separate later action.
- Mobile evidence rejected the first Print screen despite correct data because a missing viewport and always-landscape 12-column table made it unreadable on a phone. The shared renderer now has two deterministic presentations over the same canonical model: labelled stacked medicine cards for mobile review and a repeating-header A4-landscape table under print media. A local Blob URL replaces `about:blank`; pharmacy identity, Kenya time, record count, isolation and zero-AI provenance remain visible. Print-view acquisition must be repeated before device-print validation.
- Evidence after `d37cd31` proves the readable first-to-last mobile view, but 35 always-expanded 12-field cards remain inefficient. Mobile review now uses a compact, locally searchable disclosure list over the same immutable model: essential medicine/unit/stock/price facts are visible, full canonical fields expand on demand, and no network or AI path exists. Print CSS explicitly suppresses the mobile index and restores every row and column in the landscape table, preventing screen optimizations from reducing paper truth.
- Evidence after `6600418` closes compact-list and typed-fallback behavior but not the actual Print action. Medicine finding is now a shared pharmacy-scoped indexed service used by Catalog and Print. The Print adapter adds a compact typing-last control: same-origin bridges reuse the existing scanner and voice capture, truthful canonical filters cover low/out/expiry/A-Z, and typed local ranking covers identity plus operational fields and safe misspellings. Screen results never mutate or subset the print table. The implementation adds no dependency or external asset and is registered in the machine-readable provenance registry.
- Live evidence after `c637d52` exposed two Print adapter defects without invalidating the shared index: empty/all input was incorrectly passed through the non-empty score threshold, producing `0 of 35`, and mobile Blob previews could lose the sole `window.opener` capture bridge, leaving Scan and Speak inert. Print now uses the correct empty-query result boundary and a short-lived per-preview authenticated browser channel with guarded opener fallback. That adapter delegates to the existing shared camera/barcode and speech-recognition lifecycles and sends progress or actionable permission/unavailable messages back to the preview. Catalog data remains pharmacy-scoped and read-only; matching stays local and deterministic; paper output remains complete. The Print Finder checkpoint remains open for live confirmation.
- Evidence after `db1709c` proved that cross-tab delivery alone is insufficient: mobile capture requires the original direct user activation in the same browser context. Print review is now a full-screen same-context `srcdoc` surface inside Main App, with the shared camera overlay above it and the unchanged deterministic print document inside it. Direct taps synchronously enter the shared permission/capture roots. Microphone permission uses `getUserMedia` before Web Speech, both permission and recognition startup are bounded, all success/error/cancel paths clean up, and canonical local matching returns to the preview. Barcode uses the same existing camera/BarcodeDetector lifecycle and returns catalog match/no-match/not-read/cancel states. The tracked Losartan EAN-13 fixture supplies a controlled existing-catalog test without mutation or duplication. Print Finder still requires live confirmation.
- Evidence after `f8fe088` confirms voice permission/listening/local Paracetamol matching and actual scanner UI launch. The remaining voice flash came from replacing the complete iframe on each status render, not recognition. Print now performs stable in-frame status/query updates while capture state is unchanged; only camera overlay transitions rebuild the shell. The deterministic Losartan fixture now has a full-screen responsive SVG live surface and 3000×1600 PNG so camera decoding is not defeated by display scale. No runtime dependency or catalog mutation was introduced.
- The future Supplier Order Generator belongs after Export Hub integrity in the supplier/restocking domain. It must reuse canonical inventory/export roots, saved reorder levels, confirmed conversions and a sourced status model; maximum owner path is request -> editable card -> Send Order. Missing facts remain Unknown/Awaiting confirmation and routine calculations are zero-LLM.
- Exact form/unit sales belong at the shared sale-card and execution roots after catalog pack/unit data is authoritative. Unit-specific price and conversion must remain visible on the first rush-hour card and propagate unchanged through every input route, stock/ledger/report/history/correction/undo/offline/export consumer. Pack-photo evidence preserves field-level provenance and never invents or duplicates.
- Export production readiness now requires one shared provenance/compliance boundary: original or rights-verified assets, a machine-readable licensing registry with fail-closed production checks, minimum-necessary pharmacy-isolated data, access/retention/deletion/audit/redaction controls, controlled document identity/source labeling and no false endorsement. Kenya-specific legal, IP, privacy, pharmacy, payment and security conclusions remain qualified professional pre-launch reviews, not code claims.
- Live mobile evidence after `f88fa99` closes the shared Print Finder boundary: voice resolves Paracetamol without a full-preview flash, barcode capture resolves EAN-13 `6161109876546` to the one saved Losartan record with its canonical fields, and clear restores `35 of 35`. These screen-only finder operations do not alter the complete print model, catalog, queue or API state. The next isolated Export Hub checkpoint is the actual `Print inventory` action and native device print dialog.
- Android native print evidence closes Print acquisition. The system preview honored landscape after the owner selected Android's landscape control, retained the complete inventory across two pages with headings and remaining rows preserved, and performed no physical print or PDF save. Browser/device print settings remain user-controlled even when the document requests A4 landscape. The next Export Hub boundary is original/cross-format canonical consistency and integrity.
- Export final-integrity presentation is now format-aware over the unchanged immutable `ms20.inventory-export.v1` model. CSV/XLSX retain all 12 columns; PDF, DOCX, PPTX and Print group those same fields into readable operational and traceability lines with deterministic balanced pagination. Fresh filenames include full generation time. Automated parity checks require the same 35 unique medicines in every package, valid Office/PDF structures, bounded slide geometry, balanced Print/PDF/Word page counts, pharmacy identity and zero network/AI code. Local visual renders pass for XLSX, PDF and every PPTX slide; DOCX structural page-flow validation passes. Export Hub remains open only for one fresh owner open/visual confirmation across the five downloads and updated Print layout.
- First owner Excel viewing evidence kept the Excel checkpoint open: the genuine XLSX preserved data and improved colour/header legibility, but one 12-column table still required tiring horizontal navigation and felt like a database export. The shared XLSX renderer now builds five deterministic sheets from the same immutable model: `Inventory Overview`, `Full Inventory`, `Low Stock`, `Expiry Tracking`, and `Suppliers`. The overview exposes calm stock/value/attention summaries; operational sheets use purpose-specific compact columns; Full Inventory retains every canonical field; all relevant sheets freeze their title/header rows and medicine/primary column, wrap and vertically centre content, band data rows, cap auto-sized widths, hide gridlines, filter headers and preserve print setup. Low Stock reuses the shared medicine-finder reorder-level classification and shows an explicit healthy empty state. Automated package, canonical-data, five-sheet, freeze, style, formula-error and all-sheet visual-render checks pass. Excel remains the active live checkpoint until the owner opens one freshly generated workbook; do not advance to PDF before that evidence passes.
- Fresh phone evidence then exposed a misleading overview integrity defect: freezing column A while placing three unrelated KPI pairs across each wide row allowed scrolled values to appear beside the wrong fixed labels. The owner could see impossible combinations such as 714, 0 or 8 total medicines even though the canonical snapshot contained 35. XLSX generation now validates one immutable snapshot before any sheet is built, recomputes and reconciles every summary, rejects missing/duplicate medicine identities and invalid numeric values, and validates all five sheet projections before packaging. Identical inputs produce byte-identical workbooks. The overview uses four stacked label/value KPIs and a four-column Attention Required list; Low Stock, Expiry Tracking and Suppliers have narrow dedicated responsibilities, while only Full Inventory retains the complete 12-field table. All-sheet structural and visual verification passes locally. Excel still requires one final fresh owner-device validation and PDF remains blocked.
- Follow-up phone evidence showed the remaining Excel failure was the pane behavior itself: any frozen medicine column produced a distracting split screen and allowed metadata/headings to clip during horizontal movement. The final XLSX presentation emits no pane, `xSplit` or `ySplit` XML on any worksheet. Overview is constrained to a 46-character four-column width with vertically stacked KPIs, wrapped metadata, a compact attention table and merged full-width empty guidance. Full Inventory uses normal scrolling and owner-priority column order; all operational sheets remain narrow, filterable and pane-free. Automated tests require no panes, five filters, complete 35-row projections, compact overview width, merged metadata/empty states and deterministic bytes. Artifact import, formula scan and visual rendering of all five sheets pass without clipped headings or values.
- The subsequent Android viewer failure was worksheet identity/navigation, not canonical data. XLSX now publishes the exact tab sequence `Overview`, `Full Inventory`, `Low Stock`, `Expiry Tracking`, `Suppliers`, with matching distinct A1 titles (Overview uses `Pharmacy Overview`) and a numbered contents guide on the first sheet. Every working sheet has its own identity block and purpose-specific schema. Explicit dimensions stop at real content (`A1:D20`, `A1:M39`, `A1:F5`, `A1:G39`, `A1:E39` in the controlled fixture), all panes remain absent, and print/page metadata is omitted so mobile viewers cannot manufacture blank worksheet pages. Extended properties carry worksheet titles for clients that use package metadata. The immutable snapshot and reconciliation boundary is unchanged; Excel remains the only active live checkpoint and PDF is blocked.
- Because the tested Android viewer hides workbook tabs, worksheet navigation is now self-contained using standard OOXML internal hyperlinks. Overview exposes five large tap targets; each working sheet exposes `← Back to Overview` and the same five-sheet strip, with the active sheet emphasized. All targets are validated existing-sheet locations ending at A1 and never use external relationships, macros or scripts. Sheet views request `showGridLines=0`, `showRowColHeaders=0`, A1/top-left selection and 90% zoom; viewer chrome and preference support remain external compatibility concerns. The fixture used ranges are now `A1:D20`, `A1:M40`, `A1:F6`, `A1:G40`, and `A1:E40`, reflecting only the intentional navigation row. This compatibility checkpoint was closed after the owner proved that the tested viewer displays the workbook but ignores those standard links.
- Excel Owner Workbook is passed with a documented viewer limitation. Excel-compatible package import/rendering and direct OOXML validation confirm five visible distinct sheets, 29 valid internal targets, exactly 35 Full Inventory records, reconciled metrics, deterministic bytes and zero formula errors. The tested advertising-supported Android viewer displays XLSX content but ignores standard internal worksheet hyperlinks; its `1/5` controls, advertisements, headings and overscroll are external behavior and do not justify another workbook redesign.
- PDF Owner Copy is now the active format checkpoint. The unchanged immutable export model produces one portrait overview page plus seven portrait five-medicine inventory pages. Every medicine card carries identity, stock, form/unit, prices, supplier, expiry, batch, shelf and barcode. Generation remains deterministic, pharmacy-isolated and zero-AI; all eight pages pass automated structure/content checks and local rendered visual inspection.
- Authoritative Android evidence passes and closes PDF Owner Copy: eight portrait pages opened without sideways scrolling, reconciled Overview metrics were readable, all seven five-card inventory pages were intact and medicines 31–35 completed the document. The final shared-card polish replaces missing important values with `Not recorded`, omits missing optional trace fields, preserves numeric zero and shortens the visible footer. All 35 names remain exactly once and every final page render is unclipped.
- Word Owner Document remains active after its first owner-device usability failure. The shared generator now uses a portrait working-document architecture: one review overview followed by four non-splitting editable medicine cards per page, with readable hierarchy, prominent stock/prices, separated traceability and owner notes/corrections fields. The same immutable validated snapshot supplies all 35 records and totals; deterministic bytes, pharmacy isolation and zero-AI formatting remain enforced.
- Authoritative owner-device evidence after `5567f92` closes Word Owner Copy layout: one readable overview plus nine portrait review pages, four intact cards per full review page, all 35 medicines, and medicines 33–35 on page 10. Focused final polish gives missing stock a smaller `Stock not recorded` hierarchy, preserves real zero, and adds one subtle editable prompt plus writing lines to every notes panel. Metadata carries `ms20.word-owner-copy.v2`. Microsoft Word confirms ten stable pages, and a save/reopen editability round-trip preserves all 35 identities with no protection, macro or flattened-image dependency. Word is passed and protected.
- Presentation Owner Briefing is now active. It exists for large-screen owner, staff or supplier briefings and does not copy Word's edit form or Excel's analysis grid. The shared PPTX renderer emits one minimal title, one reconciled overview and seven five-medicine review slides with 35 canonical medicines exactly once, visible stock/prices and secondary supplier/traceability. PowerPoint renders all nine slides cleanly; the immutable snapshot, deterministic bytes, pharmacy isolation and zero-AI boundary are unchanged.
- Final owner-device evidence after `c561003` permanently passes Word Owner Copy: the fresh 104.43 KB DOCX retains ten pages, all 35 medicines, calm missing-stock labels, prominent numeric stock, editable prompts, usable notes space and intact cards through page 10. Protect Word from further redesign without regression evidence.
- Export formats now inherit a purpose-first registry contract. Every format has one unique machine-readable operational purpose and one direct owner-facing explanation. Excel is analysis/operations, PDF read-only sharing, Word editable review, CSV system exchange, Presentation business briefing and Print a physical working copy. A new or redesigned format must answer why the owner chooses it over every alternative or be rejected; shared canonical truth, isolation, deterministic zero-AI rendering and provenance safeguards remain mandatory.
- Presentation now emits a fixed nine-slide owner decision briefing. `validateInventoryPptxPackage` runs on the exact bytes before download and verifies the ZIP terminator, mandatory OOXML parts, slide content types, relationship targets and slide count. The artifact opens and renders as nine slides in Microsoft PowerPoint; the generic Android app error (4) is an external viewer limitation, while the live checkpoint remains pending.
- Export completion is routed through `recordExportEvent`. It updates the single durable `ExportHubCard` instead of appending feed messages. Newest-first metadata is stored under `ms20-main-app:export-history:<pharmacy-id>`, deduped by record id and bounded to 50 entries. Files remain owner-device downloads; browser storage retains metadata only.
- Production Sale resolution keeps catalog medicine identity independent from requested selling unit. Common and pharmacy-configured units—including irregular box/boxes—are parsed locally before matching. An unconfigured unit preserves the matched medicine’s complete catalog context, blocks confirmation only on missing conversion/price, and saves approved pack facts back to that existing pharmacy-isolated record.

<!-- VALIDATION_CONTRACT_SYNC_START -->
## Generated validation-contract reference

- Authority: `MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`
- Checkpoints: 84
- Current: MS2-LT-055 — Refunds, returns and credits
- Bridge manifest: `docs/engineering-memory/bridge-validation-contract.json`
- Token policy: ACTIVE — `docs/engineering-memory/token-execution-policy.md`
- Rule: Codex and ChatGPT Bridges load the master and Engineering Traceability Index; no parallel sequence is permitted.
<!-- VALIDATION_CONTRACT_SYNC_END -->
