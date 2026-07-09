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

1. Open a shell in the workspace root.
2. Run:

```bash
cd ms20-main-app
npm run verify
npm run serve
```

3. Open:

```text
http://127.0.0.1:5177/index.html
```

Expected:

- App loads.
- Brand shows MS2.0.
- No browser console errors.
- Offline app link is visible.
- Backend/Screens status strip is visible.

## Dashboard

Test:

- Dashboard loads on first screen.
- Owner can see today totals.
- Owner can see cash, M-Pesa, credit sections.
- Owner can see online/offline state.
- Owner can see queue count.
- Owner can reach common actions in one tap.

Pass criteria:

- Common action visible immediately.
- No confusing old PharMareen user-facing brand.
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
- Confirm dashboard fits.
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
2. Identify root cause.
3. Patch the smallest safe Main App file.
4. Do not alter backend/offline/Baileys unless required.
5. Run focused checks.
6. Continue the test plan.

