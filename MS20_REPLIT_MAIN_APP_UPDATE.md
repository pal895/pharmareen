# MS2.0 Replit Main App Update

Update date: 2026-07-09

## Purpose

This update transfers the verified MS2.0 Main App foundation into the real GitHub/Replit project so Replit can serve the Main App from a phone-openable URL.

MS2.0 is Main App-first. WhatsApp/Baileys is preserved as an optional external channel for later and must not be used for this live product test phase.

## Added Main App Folder

```text
ms20-main-app/
```

Key files:

```text
ms20-main-app/index.html
ms20-main-app/package.json
ms20-main-app/tools/serve.mjs
ms20-main-app/tools/verify-architecture.mjs
ms20-main-app/src/app.js
ms20-main-app/src/services/liveBackendGateway.js
ms20-main-app/src/services/backendAdapters.js
ms20-main-app/src/contracts/integrationContracts.js
ms20-main-app/src/routes/routeRegistry.js
ms20-main-app/src/cards/editableCards.js
ms20-main-app/LIVE_APP_TEST_PLAN.md
ms20-main-app/REPLIT_WORKFLOW_HANDOFF.md
```

## Safety Boundary

The Main App is queue-only by design in this phase:

```text
writeMode: safe_queue_only
```

This means:

- Cards can be created.
- Cards can be edited.
- Cards can be confirmed to the local/offline queue.
- Backend target metadata can be attached.
- Live sale/stock writes are not automatically performed from every screen yet.

## Replit Pull Command

Run this in the real Replit Shell after this update is pushed:

```bash
git pull --no-rebase --no-edit origin main
```

Then verify the Main App:

```bash
cd ms20-main-app
npm run verify
npm run check
node --check src/services/liveBackendGateway.js
```

Optional backend compile check from repo root:

```bash
python -m py_compile app/main.py app/live_runtime.py app/local_first_parser.py app/sheets.py
```

## Start Main App In Replit

From the Replit Shell:

```bash
cd ms20-main-app && PORT=${PORT:-5177} npm run serve
```

When Replit provides `REPLIT_DEV_DOMAIN`, the server binds to `0.0.0.0` and prints:

```text
MS2.0 Replit URL: https://$REPLIT_DEV_DOMAIN
```

Use that public/dev URL for phone testing. Do not use desktop localhost as live proof.

## Main App Live Test Rules

- Main App only.
- One test action at a time.
- Wait for the owner screenshot/result before the next step.
- Record friction once.
- Fix root causes in shared Main App code, not only one visible screen.
- Run focused verification after each fix.
- Resume from the paused test step.
- Do not test WhatsApp/Baileys.
- Do not touch secrets.
- Do not call OpenAI/API.
- Preserve backend, offline app, Google Sheets, reports, stock/sales safety, and runtime config.

## First Live Test

After the Replit Main App URL opens on phone:

```text
Test 1.1: Open the Replit Main App link on your phone and send the first dashboard screenshot.
```

Expected:

- Brand shows MS2.0.
- Dashboard loads.
- Today, Cash, M-Pesa, Credit are visible.
- Online/backend/sheets/cloud/queue status strip is visible.
- Quick actions are reachable in one tap.
- No browser console errors.
