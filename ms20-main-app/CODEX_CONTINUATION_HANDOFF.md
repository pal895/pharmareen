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
- `ms20-main-app/src/services/brainAdapters.js`
- `ms20-main-app/src/services/cloudGateway.js`
- `ms20-main-app/src/services/localIntelligence.js`
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
- Offline app route exists separately at `/offline_app/index.html` on the backend.
- Main App currently connects through safe adapters and placeholders.
- Main App does not yet directly mutate live production sale/stock data from every screen.
- This is expected after a safe merge.
- Next job is live testing the Main App screens and workflows, then wiring missing actions safely.
- Current desktop workspace has a `.git` directory with missing `HEAD` and `config`; local `git status` failed here. Do not try to repair git unless the user explicitly asks.

## Next Phase

The next Codex chat must do Main App live product testing only:

1. Confirm current files and app routes.
2. Start Main App.
3. Test every Main App screen.
4. Test every Main App workflow.
5. Find friction.
6. Record friction clearly.
7. Fix only verified friction.
8. Preserve stable backend/offline systems.
9. Keep API usage at zero unless explicitly required.

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
- Main App route: `http://127.0.0.1:5177/index.html`.
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

