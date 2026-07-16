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
