# MS2.0 Live Main App Test Plan

This plan is for Main App live product testing only. Do not return to WhatsApp live testing in this phase.

## Test Rules

- Test the Main App as the primary product.
- Keep OpenAI/API token use at zero unless explicitly required.
- Do not rebuild architecture.
- Do not touch secrets.
- Do not modify backend/offline/Baileys runtime files unless a verified Main App integration bug requires a narrow safe patch.
- Record friction once, then fix the root cause broadly.
- Run focused tests after each fix.
- Stop and report exact blockers instead of looping.

## Startup

### Replit Phone Testing

1. Pull the latest repo update into Replit.
2. Verify:

```bash
cd ms20-main-app
npm run verify
npm run check
```

3. Restart the Replit app so the backend loads the Main App static route.
4. Open:

```text
https://$REPLIT_DEV_DOMAIN/main-app/
```

The bare Replit domain may show `{"status":"running"}` because it is the backend status route.

### Standalone Local Check

For focused local module checks only:

```bash
cd ms20-main-app
npm run verify
npm run serve
```

Then open:

```text
http://127.0.0.1:5177/index.html
```

Expected:

- App loads.
- Brand shows MS2.0.
- No browser console errors.
- A calm messaging-first home is visible.
- Backend, Sheets, queue, totals, and route diagnostics are not shown on the owner home.
- Settings/Diagnostics/Admin is collapsed and available if needed.

## Messaging Home

Test:

- Owner sees MS2.0, a greeting, and a clear composer.
- Owner can type a sale without reading technical status.
- Owner can reach common actions without a noisy dashboard.
- Diagnostics remain collapsed.

Pass criteria:

- Common action path is visible immediately.
- No confusing old PharMareen user-facing brand.
- No backend, Sheets, token, queue, route, or adapter details on the owner home.
- No layout overlap.
- No console errors.

## Chat Workspace

Test:

- Type `Panadol 2 cash`.
- Confirm it creates an editable sale card.
- Try `panadol2cash`.
- Confirm it creates the same sale intent.

Pass criteria:

- Local parser handles known structured sale.
- No OpenAI/API call.
- Editable card appears.
- Owner can correct before confirm.

## Editable Sale Card

Test:

- Confirm fields: medicine, quantity, payment.
- Change quantity.
- Change payment mode.
- Cancel card.
- Create another sale card.
- Confirm card to offline queue.

Pass criteria:

- No direct production write yet.
- Confirmed action enters queue.
- Duplicate/idempotency behavior remains safe.
- Flow is three steps or less.

## Voice Workspace

Test:

- Use Tap & Talk demo.
- Confirm VoiceReviewCard appears.
- Confirm card can be reviewed, corrected, or cancelled.

Pass criteria:

- Voice path is clearly placeholder/review-first.
- No AI/API call unless explicitly enabled later.

## Photo Workspace

Test:

- Use Photo demo/upload.
- Confirm VisualScanCard appears.
- Confirm PhotoReviewCard appears.
- Confirm result is review-first.

Pass criteria:

- Photo path does not claim full production extraction yet.
- No AI/API call.
- Owner can review/correct.

## Offline Framework

Test:

- Confirm offline app link exists.
- Confirm route target points to backend `/offline_app/index.html`.
- Toggle browser offline if available.
- Create a local card while offline.
- Return online and sync.

Pass criteria:

- App does not lose queue state.
- Owner understands pending sync.
- No duplicate action is created.

## Stock Workflow

Test:

- Open stock correction demo/action.
- Edit stock values.
- Confirm to queue.
- Confirm no direct production stock mutation yet.

Pass criteria:

- Stock action is represented as editable/reviewable card.
- Safe queue metadata exists.

## Report Workflow

Test:

- Use Reports action.
- Confirm ReportCard appears.
- Confirm daily report route metadata points to backend target route.

Pass criteria:

- Report card is review-first.
- No WhatsApp send occurs automatically.
- No OpenAI/API call.

## Restock Workflow

Test:

- Trigger or create restock card.
- Edit supplier, medicine, quantity, unit/pack details if present.
- Confirm to queue.

Pass criteria:

- Restock flow is editable.
- Queue-only until live write is intentionally enabled.

## Invoice/Photo Placeholder

Test:

- Use invoice/photo workflow.
- Confirm invoice/photo card appears.
- Confirm placeholder copy is honest and short.

Pass criteria:

- No false claim of complete OCR extraction.
- No AI/API call.
- Owner can review/correct.

## Sync And Offline Behavior

Test:

- Create two different queued cards.
- Try creating a duplicate action.
- Run sync.
- Confirm duplicate is blocked.

Pass criteria:

- Queue count changes correctly.
- Duplicate/idempotency is preserved.
- Sync feedback is clear.

## Error States

Test:

- Empty command.
- Unknown medicine.
- Ambiguous medicine if catalog supports it.
- Backend unavailable.
- Offline app unavailable.

Pass criteria:

- Error text is short, friendly, and actionable.
- No infinite loading.
- No console errors.

## Mobile Layout

Test:

- Use browser mobile viewport if available.
- Confirm messaging home fits.
- Confirm editable cards fit.
- Confirm action buttons are reachable.
- Confirm text does not overlap.

Pass criteria:

- Owner can complete common workflow on phone.
- No layout shift that blocks core actions.

## Owner Usability Review

For each workflow, record:

- Steps required.
- Typing required.
- Confusing wording.
- Slow response.
- Missing next action.
- Anything that would make a pharmacy owner lose trust.

Pass criteria:

- Common workflows take three steps or less.
- Owner feels guided, not buried in menus.
- App feels like a pharmacy operating tool, not a chatbot.

## Friction Handling

For every verified friction:

1. Write down the friction.
2. Read the existing project files.
3. Understand the existing architecture.
4. Locate the existing implementation.
5. Do not rebuild working systems.
6. Identify the real root cause.
7. Fix the root cause everywhere the same problem could appear.
8. Verify automatically.
9. Resume testing exactly where it paused.
10. If project files or routing cannot be located, stop and report the blocker.
