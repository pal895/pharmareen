# MS2.0 Main App Foundation

Every checkpoint is maintained only in `../MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`; historical handoffs and embedded “next” notes are evidence only.

This folder is the isolated production foundation for the future permanent MS2.0 app.

It does not rewrite or modify the current live backend, offline app, WhatsApp/Baileys bridge, Google Sheets code, or pharmacy engine. The current live system is connected through read-only/live-status adapter slots and queue-only card actions.

## Run

```bash
cd ms20-main-app
npm run verify
npm run serve
```

Open `http://127.0.0.1:5177`.

In Replit phone testing, open the backend-served route instead:

```text
https://$REPLIT_DEV_DOMAIN/main-app/
```

The bare Replit domain may show backend status JSON because the existing backend owns the public port.

No dependency install is required.

## What Works Now

- Messaging app home with separate MS2.0 Assistant and Notifications conversations.
- First-run owner onboarding starts before daily sale/report/photo workflows.
- After setup, medicine catalog onboarding starts before sale testing.
- Catalog onboarding supports invoice/photo, medicine/shelf scan, bulk paste, CSV/text upload, and sale-time fallback.
- Bulk paste and CSV/text imports are parsed deterministically into a catalog review card.
- Source Brain and Pharmacy Catalog are kept separate; approved medicines save to the pharmacy catalog, not directly into global knowledge.
- Local Digital Operations Assistant notifications are separate from Operations Chat.
- CSV catalog export and bulk-paste template download are available from the Main App.
- Scan/invoice cards now include reusable batch, expiry, barcode, supplier, shelf, price, and stock fields.
- Focused chat screen with header, message bubbles, bottom composer, browser voice button, and hidden attach/actions menu.
- Complete high-confidence sale commands record immediately only after the medicine exists in the pharmacy catalog.
- Missing or ambiguous commands show editable cards directly, without extra narration.
- Cancel removes review cards quietly without adding a chat message.
- Every editable card has `-` and `+` text-size controls, and the chosen size is remembered on the device.
- Technical status, route slots, totals, queue state, and contracts are moved behind hidden Settings/Diagnostics/Admin controls.
- Offline app button remains available through Diagnostics and links to the existing live backend offline app route when the backend is running.
- Conversation flow for low-typing text commands, browser speech capture, direct camera/photo upload, barcode placeholder, invoice review, reports, setup, and sync.

## Permanent typing-last UX rule

For every applicable workflow, MS2.0 first offers the fastest safe deterministic route: one-tap action, shared barcode/scanner, shared voice, appropriate camera/photo recognition, then recent/frequent/filtered/suggested choices. Complete typed entry remains available as the final fallback. Do not create clutter merely to expose every route, and do not duplicate scanner, voice, camera, catalog-match or filter logic inside individual screens.

Medicine finding uses one pharmacy-scoped local index across applicable catalog and preview surfaces. Exact canonical and barcode matches rank first, then canonical prefixes, aliases, complete field matches and conservative spelling recovery. Supported searchable evidence includes name, aliases, strength, form, sale unit, barcode, supplier, shelf and batch. Low/out-of-stock and expiry filters use only saved canonical values. Screen filtering never silently changes a full export or print dataset.

## Permanent lawful-technology rule

Prefer original MS2.0 code, already verified project capabilities, standard browser/device functionality, and then properly licensed documented dependencies. Do not add an asset, SDK, API, library, design, icon, font, model, dataset or copied implementation without verified commercial/modification/redistribution rights, required notices, privacy/data-flow review, maintenance/security review and an approved machine-readable provenance entry. Unknown or incompatible rights fail closed. Never transmit pharmacy, medicine, customer, supplier or operational data without documented authorization, and never imply third-party or regulator endorsement.
- Editable Card Workspace with reusable cards:
  - SaleCard
  - InvoiceCard
  - RestockCard
  - OnboardingCard
  - StockCorrectionCard
  - ReportCard
  - SaleCard (the single shared Production Sales Card for typed and voice sales)
  - PhotoReviewCard
  - MedicineMatchCard
  - VisualScanCard
  - CatalogOnboardingCard
  - CatalogImportCard
  - ImportMappingCard
  - NotificationCard
  - DocumentExportCard
  - SyncReviewCard
- Text command `Panadol 2 cash` or `panadol2cash` records a sale locally and queues it safely.
- Incomplete commands such as `Panadol` or `Panadol 2` create editable review cards.
- Mic starts browser speech capture when supported; complete results use the same local-first sale path, and uncertain results become review cards.
- Camera and photo library uploads create VisualScanCard and PhotoReviewCard.
- Invoice review creates an InvoiceCard.
- First-run setup creates an OnboardingCard.
- Confirming a card stores a queued offline action with duplicate/idempotency protection.
- Confirmed cards include live backend target metadata but remain queue-only until live write sync is explicitly enabled.
- Sync button flushes queued demo actions to the cloud memory gateway placeholder.

## Product Flow

The first-run owner path is designed around three steps:

1. Open MS2.0 and tap the MS2.0 Assistant conversation.
2. Complete the setup card.
3. Choose how to add medicines, then review and approve.

The daily owner path stays three steps or less and follows the permanent interaction priority **Voice first → fast tap/action second → typing last**:

1. Open the MS2.0 Assistant conversation.
2. Speak first where the device/platform supports it; otherwise use the fastest tap/action, scan or upload, with typing retained as fallback.
3. Get an instant receipt, or review the editable card only when MS2.0 needs owner judgement.

Every supported typed operational command must have voice parity wherever device/platform speech is available. After transcription, voice and typed text use the same deterministic router and business roots; do not create voice-only workflow logic or invoke AI when local routing is sufficient. Typing remains available for accessibility, noise, unsupported browsers, offline speech limitations, transcript correction and deliberate fallback.

Complete known-medicine sale commands skip cards and return a concise sale receipt. Unknown medicines show a clean editable learning card so the pharmacy catalog improves safely. The owner home and chat flow should not show backend, Sheets, queue, token, route, or adapter details. Those belong in Settings, Diagnostics, Admin, or Developer Mode.

## Cloud Memory And Recovery

Cloud memory is the source of truth. Device storage is only cache plus pending queue.

When live auth is connected later, the recovery flow should:

1. Login or identify the owner.
2. Load pharmacy profile, branches, catalog, aliases, visual memory, pending queue, and card history from cloud memory.
3. Rehydrate the chat home, conversation history, pending cards, and saved queue.
4. Resume sync with idempotent action ids so no duplicate sale, restock, correction, or report action is applied.

The placeholder gateway lives in `src/services/cloudGateway.js`.

## Local-First Intelligence

MS2.0 should always try local intelligence before AI:

- Pharmacy Brain: pharmacy catalog, owner aliases, pack sizes, forms, units, visual memory.
- MS2.0 Source Brain: approved common medicine/source knowledge.
- AI Fallback: only when local/source confidence is too low and the action explicitly allows it.

The placeholder brain adapters live in `src/services/brainAdapters.js`.

## Medicine Catalog Onboarding Path

The foundation now starts catalog onboarding before sale testing:

1. Setup saves the pharmacy profile.
2. MS2.0 asks how the owner wants to show the pharmacy: invoice/photo, scan, paste list, CSV/text/POS export, or add while selling.
3. Bulk paste and CSV/text files create a `CatalogImportCard`.
4. Approved catalog items are saved through `CloudMemoryGateway.saveCatalog(pharmacyId, catalogItems)` and the local pharmacy cache.
5. `PharmacyBrain.loadCatalog(items)` accepts name, aliases, forms, units, pack sizes, prices, stock, supplier, barcode, batches, expiry, and shelf.
6. `parseLocalCommand(text, catalog)` checks the pharmacy catalog before allowing instant known sales.
7. Ambiguous or missing medicines route to MedicineMatchCard.
8. Confirmed aliases can be saved per pharmacy with `PharmacyBrain.saveOwnerAlias`.

No hardcoded pharmacy medicines are required.

## Photo And Visual Scan Path

`src/services/visualPipeline.js` defines the safe future path:

1. Local fingerprint
2. Exact duplicate lookup
3. Near duplicate lookup where practical
4. Previous confirmed result lookup
5. Local image preprocessing
6. Local OCR adapter
7. Barcode extraction adapter
8. Packaging visual match adapter
9. Pharmacy catalog match
10. Source brain lookup
11. Supplier template lookup for invoices
12. Confidence scoring
13. Visual memory save
14. AI fallback adapter only if explicitly needed later

Supported future photo types include packaging, strips, cartons, shelf photos, stock photos, invoices, reports, onboarding documents, and supplier documents.

## Backend Integration Slots

Reserved and live-readiness slots are listed in `src/contracts/integrationContracts.js`:

- `/api/ms20/*`
- command parser adapter
- medicine brain adapter
- sale engine adapter
- stock engine adapter
- report engine adapter
- invoice engine adapter
- onboarding engine adapter
- sync engine adapter
- auth/session adapter
- cloud storage adapter
- external channel adapter

The existing WhatsApp/Baileys system remains the external channel adapter. This app only reads live status and preserves the bridge.

The live gateway in `src/services/liveBackendGateway.js` probes only local/current backend endpoints:

- `/health`
- `/debug/version`
- `/live/readiness`
- `/offline_app/index.html`
- `/webhooks/baileys/whatsapp` as a target route, not an automatic write
- `/reports/daily?send_whatsapp=false` as a target route

## Offline App Integration

The existing offline app can be reached through:

- `/app/offline`
- `/offline` for compatibility
- `/offline_app/index.html` through the existing live backend

This foundation does not rebuild the existing offline app. It only links/mounts the route slot and queue/sync contracts.

## Token Safety

This foundation uses zero OpenAI/API tokens. It performs no OpenAI/API provider calls and includes no AI provider client. The only runtime network calls are local/current backend readiness probes used to detect the existing live MS2.0 system.

Zero-token flows should include known sales, aliases, confirmed packaging, cached invoice layouts, repeated documents, stock checks, reports, simple analytics, and barcode scans.

See `MS20_ONBOARDING_AND_OPERATIONS_INTELLIGENCE.md` for the persistent onboarding, source brain, catalog, notifications, scanner, document, and live-test continuation architecture.
