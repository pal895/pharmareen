# MS2.0 Codex Continuation Handoff

This file is the copy-paste memory package for continuing MS2.0 in a fresh Codex chat.

## Project Identity

- Project name: MS2.0
- MS2.0 is a Pharmacy Operating Intelligence Platform, not an AI chatbot.
- The Main App is now the primary product surface.
- WhatsApp/Baileys is preserved as an optional integration layer for later, not the current testing focus.
- We are no longer returning to WhatsApp live testing now.
- The next testing phase is Main App live product testing.

## Core Engineering Rules

- Offline-first.
- Local-first before AI.
- AI only when useful and explicitly needed.
- Editable cards instead of heavy typing.
- Common pharmacy workflows must take three steps or less.
- Do not rebuild stable systems.
- Extend through adapters.
- Protect API tokens.
- No unnecessary OpenAI/API calls.
- Preserve backend, offline app, Baileys bridge, and Google Sheets integration.
- If blocked, stop and report the blocker instead of looping.

## What Was Just Completed

A safe Main App merge was completed inside `ms20-main-app`.

Completed:

- Main App shell preserved.
- Existing backend preserved.
- Existing offline app preserved.
- Baileys bridge preserved.
- Adapter slots added.
- Live backend gateway added.
- Route registry added.
- Integration contracts added.
- Editable card mapping added.
- Verification tooling added.
- User-facing brand moved to MS2.0 inside the Main App.
- No secrets touched.
- No production WhatsApp runtime modified.
- No OpenAI/API usage introduced.

## Latest Main App Onboarding Update

Completed after the messaging-first UI work:

- MS2.0 home has separate Operations and Notifications conversations.
- Setup completion now leads into medicine catalog onboarding before sale tests.
- The original paused sale test `Panadol 2 cash` remains paused.
- New next test is Onboarding Test A.1.
- Source Brain and Pharmacy Catalog are separated in code and documentation.
- Seed Source Brain medicine data exists in `src/data/sourceMedicines.js`.
- Catalog onboarding choices exist through `CatalogOnboardingCard`.
- Bulk paste and CSV/text import create `CatalogImportCard`.
- Approved catalog imports save to local pharmacy cache and `CloudMemoryGateway.saveCatalog`.
- Complete sale commands record instantly only when the medicine exists in the pharmacy catalog.
- Unknown sale-time medicines show `MedicineMatchCard` and can be added locally.
- Scan/invoice review cards include batch, expiry, barcode, supplier, shelf, price, and stock fields.
- Visual pipeline records local fingerprint and token-control metadata.
- Notifications are generated locally by `notificationCenter.js` and do not interrupt Operations Chat.
- CSV catalog export and bulk-paste template download are available.
- Read-aloud uses local/browser speech synthesis where supported.
- Real OCR, barcode decoding, PDF extraction, binary Excel parsing, and near-duplicate image recognition are adapter-ready but not fully implemented.

The merge deliberately kept live production writes disabled from the new Main App. Confirmed cards carry backend target metadata but remain `safe_queue_only` until live write sync is intentionally enabled and tested.

## Files Changed In The Last Merge

Primary changed files:

- `ms20-main-app/src/app.js`
- `ms20-main-app/src/services/liveBackendGateway.js`
- `ms20-main-app/src/services/backendAdapters.js`
- `ms20-main-app/src/contracts/integrationContracts.js`
- `ms20-main-app/src/routes/routeRegistry.js`
- `ms20-main-app/src/cards/editableCards.js`
- `ms20-main-app/src/styles.css`
- `ms20-main-app/tools/verify-architecture.mjs`
- `ms20-main-app/README.md`
- `ms20-main-app/FINAL_REPORT.md`

Related foundation files present in `ms20-main-app`:

- `ms20-main-app/index.html`
- `ms20-main-app/manifest.json`
- `ms20-main-app/package.json`
- `ms20-main-app/src/data/demoState.js`
- `ms20-main-app/src/data/sourceMedicines.js`
- `ms20-main-app/src/services/brainAdapters.js`
- `ms20-main-app/src/services/catalogOnboarding.js`
- `ms20-main-app/src/services/cloudGateway.js`
- `ms20-main-app/src/services/documentGenerator.js`
- `ms20-main-app/src/services/localIntelligence.js`
- `ms20-main-app/src/services/notificationCenter.js`
- `ms20-main-app/src/services/offlineQueue.js`
- `ms20-main-app/src/services/syncAdapter.js`
- `ms20-main-app/src/services/visualPipeline.js`
- `ms20-main-app/tools/serve.mjs`

Files intentionally not modified during the safe Main App merge:

- Existing backend under `app/`
- Existing offline app outside `ms20-main-app`
- Existing Baileys bridge/runtime files
- Existing Google Sheets secrets/config values
- Production WhatsApp session/auth files

## Commands And Test Results

Commands run during the safe merge and verification:

```bash
cd ms20-main-app
npm run verify
```

## Invoice Onboarding Continuation Update — 2026-07-12

- Current stage remains invoice/photo onboarding; do not restart earlier onboarding, sale, restock, camera, or stock tests.
- Current pause is the open original-invoice review card. Do not approve it until the canonical merged review is complete and total-consistent.
- Preserve the verified fast two-pass local OCR, camera controls, source order, editable card, arithmetic checks, and zero-token behavior.
- Matching rescans of one invoice must consolidate into one canonical review card so weaker rereads cannot replace stronger saved evidence or evict it through active-card limits.
- After the original invoice passes and saves correctly, run one second-invoice consistency test using a different supplier/layout and new trusted Source Brain medicines not already in Zuri Pharmacy.
- Only after both invoices pass extraction, review, approval, duplicate safety, catalog/stock persistence, reload, configured persistence, and zero-token checks may invoice onboarding be marked complete and the next existing onboarding option begin.

Result: PASS.

```bash
cd ms20-main-app
npm run check
```

Result: PASS.

```bash
cd ms20-main-app
node --check src/services/liveBackendGateway.js
```

Result: PASS.

```bash
cd ms20-main-app
node --check src/services/catalogOnboarding.js
```

Result: PASS.

```bash
cd ms20-main-app
node --check src/services/notificationCenter.js
```

Result: PASS.

```bash
python -m py_compile app/main.py app/live_runtime.py app/local_first_parser.py app/sheets.py
```

Result: PASS.

```powershell
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5177/index.html' -TimeoutSec 10
```

Result: PASS, HTTP 200.

In-app browser load inspection:

- Main App loaded at `http://127.0.0.1:5177/index.html`.
- Title detected: `MS2.0 Main App`.
- Dashboard detected.
- Backend/Screens status strip detected.
- Offline app link detected.
- Offline app link target: `http://127.0.0.1:5000/offline_app/index.html`.
- Browser console error check: PASS, zero errors.

Deterministic card proof:

```bash
cd ms20-main-app
node --input-type=module
```

The proof imported `BackendAdapterRegistry` and `PharmacyBrain`, parsed `Panadol 2 cash`, and confirmed:

- Card type: `SaleCard`
- Medicine: `Panadol`
- Quantity: `2`
- Payment: `cash`
- Backend write mode: `safe_queue_only`
- OpenAI calls: `false`

Browser UI click automation through the in-app browser tool timed out. This was a browser automation limitation, not a product proof failure. The app load, DOM inspection, route link inspection, console check, and deterministic module-level card proof passed.

## Current Known State

- Main App runs locally at `http://127.0.0.1:5177/index.html`.
- Backend route exists separately, normally at `http://127.0.0.1:5000`.
- Replit phone testing route is `https://$REPLIT_DEV_DOMAIN/main-app/` after the backend is restarted.
- The bare Replit domain may show `{"status":"running"}` because it is the preserved backend status route.
- Offline app route exists separately at `/offline_app/index.html` on the backend.
- Main App currently connects through safe adapters and placeholders.
- Main App does not yet directly mutate live production sale/stock data from every screen.
- This is expected after a safe merge.
- Next job is live testing onboarding first, then wiring verified missing actions safely.
- Current pause: `Panadol 2 cash` sale test is paused until catalog onboarding passes.
- Current desktop workspace has a `.git` directory with missing `HEAD` and `config`; local `git status` failed here. Do not try to repair git unless the user explicitly asks.

## Next Phase

The next Codex chat must do Main App live product testing only, beginning with onboarding:

1. Confirm current files and app routes.
2. Start Main App.
3. Open MS2.0 Assistant.
4. Confirm setup/catalog onboarding choices.
5. Test catalog onboarding before sale testing.
6. Only after catalog approval resume the paused `Panadol 2 cash` sale test.
7. Test every Main App workflow.
8. Find friction.
9. Record friction clearly.
10. Fix only verified friction.
11. Preserve stable backend/offline systems.
12. Keep API usage at zero unless explicitly required.

Do not return to WhatsApp live testing in the next phase.

## Copy-Paste Continuation Script

```text
Continue MS2.0 from the existing workspace. This is not a new project.

Project identity:
- Project name: MS2.0.
- MS2.0 is a Pharmacy Operating Intelligence Platform, not an AI chatbot.
- The Main App is now the primary product.
- WhatsApp/Baileys is only an optional integration layer for later.
- Do not return to WhatsApp live testing now.
- Continue with Main App live product testing only.

Core rules:
- Offline-first.
- Local-first before AI.
- AI only when useful and explicitly needed.
- Editable cards instead of heavy typing.
- Common workflows must be three steps or less.
- Do not rebuild stable systems.
- Extend through adapters.
- Protect API tokens.
- No unnecessary OpenAI/API calls.
- Preserve backend, offline app, Baileys bridge, and Google Sheets integration.
- If blocked, stop and report the blocker instead of looping.

Current completed state:
- Safe Main App merge completed in `ms20-main-app`.
- Main App shell preserved.
- Existing backend preserved.
- Existing offline app preserved.
- Existing Baileys bridge preserved.
- Adapter slots added.
- Live backend gateway added.
- Route registry added.
- Integration contracts added.
- Editable card mapping added.
- Verification tooling added.
- User-facing Main App brand is MS2.0.
- No secrets were touched.
- No production WhatsApp runtime was modified.
- No OpenAI/API usage was introduced.

Important current architecture:
- Main App local verification route: `http://127.0.0.1:5177/index.html`.
- Main App Replit phone route: `https://$REPLIT_DEV_DOMAIN/main-app/`.
- Backend route normally: `http://127.0.0.1:5000`.
- Offline app route on backend: `/offline_app/index.html`.
- Main App uses safe adapters/placeholders and `safe_queue_only` backend metadata.
- Main App does not yet directly mutate live production sale/stock data from every screen.
- That is expected after the safe merge.
- Next work is to live-test Main App screens/workflows and wire only verified missing actions safely.

Files changed in the last merge:
- `ms20-main-app/src/app.js`
- `ms20-main-app/src/services/liveBackendGateway.js`
- `ms20-main-app/src/services/backendAdapters.js`
- `ms20-main-app/src/contracts/integrationContracts.js`
- `ms20-main-app/src/routes/routeRegistry.js`
- `ms20-main-app/src/cards/editableCards.js`
- `ms20-main-app/src/styles.css`
- `ms20-main-app/tools/verify-architecture.mjs`
- `ms20-main-app/README.md`
- `ms20-main-app/FINAL_REPORT.md`

Files/systems intentionally preserved:
- Existing backend under `app/`.
- Existing offline app.
- Existing Baileys bridge/runtime files.
- Existing Google Sheets secrets/config values.
- Production WhatsApp session/auth files.

Tests already passed:
- `cd ms20-main-app && npm run verify` PASS.
- `cd ms20-main-app && npm run check` PASS.
- `cd ms20-main-app && node --check src/services/liveBackendGateway.js` PASS.
- `python -m py_compile app/main.py app/live_runtime.py app/local_first_parser.py app/sheets.py` PASS.
- HTTP check for `http://127.0.0.1:5177/index.html` PASS, HTTP 200.
- Browser load inspection PASS.
- Browser console errors check PASS, zero errors.
- Deterministic card proof PASS: `Panadol 2 cash` becomes SaleCard, medicine Panadol, quantity 2, payment cash, backend write mode `safe_queue_only`, OpenAI calls false.

Known caveat:
- Browser UI click automation through the in-app browser tool timed out, so use normal browser/manual testing or focused app-module tests if automation is flaky.
- Local desktop `.git` metadata appears incomplete: `.git` exists but `HEAD` and `config` are missing, so `git status` failed. Do not repair git unless explicitly asked.

Next phase task:
Start Main App live product testing only.

Execution order:
1. Confirm current files and routes.
2. Start Main App with `cd ms20-main-app && npm run serve`.
3. Open `http://127.0.0.1:5177/index.html`.
4. Test Dashboard.
5. Test Chat workspace.
6. Test editable sale card flow.
7. Test Voice workspace.
8. Test Photo workspace.
9. Test Offline framework.
10. Test Stock workflow.
11. Test Report workflow.
12. Test Restock workflow.
13. Test invoice/photo placeholder.
14. Test sync/offline behavior.
15. Test error states.
16. Test mobile layout if available.
17. Record owner usability friction.
18. Fix only verified friction.
19. Run focused tests after each fix.
20. Preserve backend/offline/Baileys/Sheets systems.
21. Keep API/OpenAI usage at zero unless explicitly required.

Do not:
- Do not rebuild from scratch.
- Do not restart architecture.
- Do not return to WhatsApp live testing.
- Do not modify secrets.
- Do not call OpenAI/API.
- Do not rewrite the backend, offline app, Baileys bridge, or Google Sheets layer unless a verified Main App integration bug requires a narrow safe patch.
- Do not loop. If blocked, report the exact blocker and wait.

First action for the new Codex chat:
Inspect `ms20-main-app`, run `npm run verify`, start `npm run serve`, open the Main App, then begin the LIVE_APP_TEST_PLAN from Dashboard.
```

## Live Continuation Update — 2026-07-11

This section supersedes only stale pause instructions above. It does not remove historical context or accepted tests.

Current verified live state:

- Zuri Pharmacy setup and catalog resume state passed.
- Catalog spelling variation `Cefimixe` resolves locally to canonical `Cefixime`.
- Sale confirmation passed: `✅ Cefixime x1 recorded • Cash`, stock left 19.
- Restock confirmation passed: `✅ Cefixime +6 tablets added`, stock left 25.
- Mobile compact-shell test passed: the header/composer remain inside the fixed app and only chat content scrolls.
- Latest verified commit at this continuation point: `094d029 Persist restocks and show stock left`.
- OpenAI/API usage for these actions: zero.

Exact continuation point:

- The basic restock test has passed. Do not repeat it unless related code changes.
- Continue the expanded onboarding sequence one action at a time.
- Before the next onboarding method, read Zuri Pharmacy's current catalog, exclude onboarded medicines, and select suitable new test medicines from the trusted Source Brain.

Accepted additions that must remain integrated:

- Test every onboarding method, duplicates, scanner/photo/invoice, paste, CSV, Excel, POS/stock sheets, persistence, reports, documents, and completion state.
- Maintain onboarding, friction, fixed, regression, catalog, duplicate, scanner, document/export, API/token, AI fallback, and blocked/incomplete logs; update only what changed.
- Use simple English suitable for a 12-year-old.
- Use a shared local medicine resolver across typing, voice, autocomplete, cards, onboarding, scans, imports, stock, sales, reports, and duplicate detection.
- Resolution order: pharmacy exact/aliases/learning first, then Source Brain aliases and canonical relationships, then strength/form-aware spelling/fuzzy/phonetic ranking, then safe ambiguity; AI only for genuinely unresolved portions.
- Permanent records, receipts, stock, reports, and exports must use canonical medicine identity even when input is misspelled or shorthand.
- Add local, offline autocomplete that never changes text without selection and preserves quantity/payment text.
- Add a calm live medicine action card with relevant identity, stock, price, supplier, batch/expiry, location, aliases, and activity only when data exists; primary actions are Sell, Restock, and Stock.
- Test safe unit/pack conversions, no negative stock, no double deduction, durable card state, offline queue, reconnect/sync, and duplicate submission protection.
- Test representative phone, tablet, and desktop layouts without claiming untested universal device support.
- Fix each friction in the shared reusable component, run focused related regression checks, and return to the interrupted live action.

## Test 2 live continuation update - 2026-07-13

- The first two phone captures of the Dawa Bora landscape fixture returned no clear medicine rows.
- The verified shared friction was layout diversity: the invoice includes strength, pack-size, and selling-price columns, and dense OCR segmentation found no stable medicine-row anchors.
- The local reader now preserves more landscape resolution, uses sparse-text segmentation only as a zero-row fallback, and assigns values from named table columns by geometry so extra numeric columns cannot become quantity, cost, or line total.
- Focused invoice OCR tests: 13 passed. Main App architecture verification: passed. OpenAI/API usage: zero.
- Exact pause: deploy the new commit to Replit, then repeat only the interrupted Test 2 capture. Do not repeat Test 1.

## Test 2 completion update - 2026-07-13

- Dawa Bora landscape invoice live test passed after editable human review.
- All header fields and four source-order medicines were confirmed against the source.
- Owner corrected remaining uncertain values before approval; approval stayed blocked until required fields and arithmetic reconciled.
- Four medicines saved, catalog count increased from 13 to 17, refresh persistence passed, and CSV download completed.
- The installed Android document reader did not open the CSV; this is an external viewer observation. CSV content integrity remains scheduled for its dedicated test.
- TEST 2: PASSED. Do not repeat it without concrete regression evidence.
- Exact pause: Android Downloads screen showing the downloaded catalog CSV. Next single action is to return to MS2.0.
