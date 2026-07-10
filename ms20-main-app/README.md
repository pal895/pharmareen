# MS2.0 Main App Foundation

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

- Messaging app home with one MS2.0 Assistant conversation row.
- First-run owner onboarding starts before daily sale/report/photo workflows.
- Focused chat screen with header, message bubbles, bottom composer, browser voice button, and hidden attach/actions menu.
- Complete high-confidence sale commands such as `Panadol 2 cash` record immediately through the existing safe queue path.
- Missing or ambiguous commands show editable cards directly, without extra narration.
- Cancel removes review cards quietly without adding a chat message.
- Every editable card has `-` and `+` text-size controls, and the chosen size is remembered on the device.
- Technical status, route slots, totals, queue state, and contracts are moved behind hidden Settings/Diagnostics/Admin controls.
- Offline app button remains available through Diagnostics and links to the existing live backend offline app route when the backend is running.
- Conversation flow for low-typing text commands, browser speech capture, direct camera/photo upload, barcode placeholder, invoice review, reports, setup, and sync.
- Editable Card Workspace with reusable cards:
  - SaleCard
  - InvoiceCard
  - RestockCard
  - OnboardingCard
  - StockCorrectionCard
  - ReportCard
  - VoiceReviewCard
  - PhotoReviewCard
  - MedicineMatchCard
  - VisualScanCard
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
3. Confirm setup.

The daily owner path stays three steps or less:

1. Open the MS2.0 Assistant conversation.
2. Type, speak, scan, or upload in the chat.
3. Get an instant receipt, or review the editable card only when MS2.0 needs owner judgement.

Complete sale commands skip cards and return a concise sale receipt. The owner home and chat flow should not show backend, Sheets, queue, token, route, or adapter details. Those belong in Settings, Diagnostics, Admin, or Developer Mode.

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

The foundation already has a clean catalog path:

1. Bulk medicine list is saved through `CloudMemoryGateway.saveCatalog(pharmacyId, catalogItems)`.
2. `PharmacyBrain.loadCatalog(items)` accepts name, aliases, forms, units, pack sizes, category, and stock.
3. `parseLocalCommand(text, catalog)` checks the pharmacy catalog before AI.
4. Ambiguous matches route to MedicineMatchCard.
5. Confirmed aliases can be saved per pharmacy with `PharmacyBrain.saveOwnerAlias`.

No hardcoded pharmacy medicines are required.

## Photo And Visual Scan Path

`src/services/visualPipeline.js` defines the safe future path:

1. Local image preprocessing
2. Local OCR placeholder
3. Barcode extraction placeholder
4. Packaging visual match placeholder
5. Pharmacy catalog match
6. Source brain lookup
7. Confidence scoring
8. Visual memory save
9. AI fallback adapter only if explicitly needed later

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
