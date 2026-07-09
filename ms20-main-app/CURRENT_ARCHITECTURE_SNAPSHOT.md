# MS2.0 Current Architecture Snapshot

Snapshot date: 2026-07-09

## Product Direction

MS2.0 is now centered on the Main App as the primary pharmacy product. The intended owner experience is:

- Open the app.
- Type, tap, speak, scan, or upload.
- Review an editable card.
- Confirm, correct, or cancel.

The owner should not need to think in chatbot commands. WhatsApp/Baileys remains a preserved optional integration layer for later.

## Current Main App Location

```text
ms20-main-app/
```

Local app URL used during verification:

```text
http://127.0.0.1:5177/index.html
```

Backend URL normally expected:

```text
http://127.0.0.1:5000
```

Existing offline app route expected on backend:

```text
/offline_app/index.html
```

## Main App Modules

- `src/app.js`: Main UI shell, dashboard, feed, editable cards, actions, queue handling, live status display.
- `src/contracts/integrationContracts.js`: Card types, token policy, cloud memory contract, live backend routes, adapter slot names.
- `src/cards/editableCards.js`: Card field mappings and editable card helpers.
- `src/routes/routeRegistry.js`: Frontend route slots plus live backend route status/link mapping.
- `src/services/liveBackendGateway.js`: Read-only live backend probes and backend target metadata.
- `src/services/backendAdapters.js`: Adapter registry for parser, medicine brain, sale, stock, report, invoice, onboarding, sync, cloud, and external channel slots.
- `src/services/localIntelligence.js`: Local deterministic parser and known command handling.
- `src/services/brainAdapters.js`: Pharmacy Brain, Source Brain, and AI fallback placeholders.
- `src/services/offlineQueue.js`: Local queue and duplicate/idempotency behavior.
- `src/services/syncAdapter.js`: Queue sync placeholder.
- `src/services/cloudGateway.js`: Cloud memory placeholder.
- `src/services/visualPipeline.js`: Photo/invoice/visual scan placeholder pipeline.
- `tools/verify-architecture.mjs`: Zero-token and architecture verification.
- `tools/serve.mjs`: Static local dev server.

## Connected Safely

- Main App shell.
- Dashboard.
- Chat/action feed.
- Editable card workspace.
- Local deterministic sale parser.
- Offline queue.
- Duplicate/idempotency demo.
- Live backend readiness route mapping.
- Offline app link.
- Google Sheets readiness detection through `/live/readiness`.
- Baileys route exposed as external channel route metadata.
- Report route metadata.
- Onboarding card placeholder.
- Medicine catalog onboarding path placeholder.
- Photo/invoice review-first placeholders.

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
- `python -m py_compile app/main.py app/live_runtime.py app/local_first_parser.py app/sheets.py`
- HTTP 200 for `http://127.0.0.1:5177/index.html`
- Browser load inspection
- Browser console error check
- Deterministic `Panadol 2 cash` card proof

Known caveat:

- Browser click automation through the in-app browser tool timed out. Use manual browser testing or focused app-module tests when the browser tool is flaky.

## Not Ready Yet

Not yet complete:

- Direct production write sync from every confirmed Main App card.
- Full live Main App workflow validation.
- Full mobile usability validation.
- Real owner friction review.
- Final production polish.

## Next Correct Work

Continue with Main App live product testing only:

1. Start the Main App.
2. Test every Main App screen.
3. Test every Main App workflow.
4. Record friction.
5. Fix only verified friction.
6. Preserve backend/offline/Baileys/Sheets systems.
7. Keep OpenAI/API usage at zero unless explicitly required.

