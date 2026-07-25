# MS2.0 Current Architecture Snapshot

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
