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

## Final Invoice Consistency Gate

At the current invoice/photo stage, first complete the original supplier invoice using one canonical total-consistent review card. Do not repeat earlier passed tests.

Then, before moving to another onboarding option, create and live-test one different supplier invoice using new medicines confirmed in Source Brain and absent from the current Zuri Pharmacy catalog. Verify local extraction, clean editable review, corrections, approval, duplicate prevention, catalog/stock persistence, reload, configured persistence, saved invoice reuse, and zero unnecessary AI/API calls. Give one owner action at a time.

3. Restart the Replit app so the backend loads the Main App static route.
4. Open:

```text
https://$REPLIT_DEV_DOMAIN/main-app/
```

The bare Replit domain may show `{"status":"running"}` because it is the backend status route.

## Current Pause And Resume Rule

The previous paused sale test was:

```text
Test 1.4: Panadol 2 cash
```

Do not resume that sale test yet.

Replacement first live test:

```text
Onboarding Test A.1: open MS2.0 Assistant and confirm the owner sees medicine onboarding choices before any sale test.
```

Only after at least one medicine is approved into the pharmacy catalog should the team return to the paused sale test.

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
- A calm chat home is visible.
- Owner-facing items are MS2.0 Assistant and Notifications only.
- A fresh device shows setup as the first required step.
- After setup, a catalog onboarding card appears before sales.
- Backend, Sheets, queue, totals, and route diagnostics are not shown on the owner home.
- Settings/Diagnostics/Admin is hidden behind the chat menu.

## Chat Home

Test:

- Owner sees MS2.0 and the subtitle.
- Owner sees MS2.0 Assistant plus Notifications.
- MS2.0 Assistant shows Setup needed, Catalog needed, or Ready.
- Owner taps the row to open the chat.
- No composer, stats, quick action grid, or diagnostics are visible on the home screen.

Pass criteria:

- Chat entry path is obvious.
- First-run owner path starts with setup before daily workflows.
- No confusing old PharMareen user-facing brand.
- No backend, Sheets, token, queue, route, or adapter details on the owner home.
- No layout overlap.
- No console errors.

## First-Run Onboarding

Test:

- Open the MS2.0 Assistant conversation on a fresh device or after Reset setup.
- Confirm the setup card appears before sale/report/photo work.
- Fill pharmacy, owner, branch, location, and payment methods.
- Confirm setup.

Pass criteria:

- Onboarding appears as the first real-system step.
- No old demo messages or previous test cards are visible after refresh.
- Confirming setup marks the assistant Ready.
- Cancel removes the setup card quietly without adding a `Cancelled.` chat bubble.
- The `-` and `+` controls resize card text and apply to future editable cards.

## Medicine Catalog Onboarding

Test:

- Complete setup or use an already setup test device with an empty catalog.
- Confirm MS2.0 asks how to add medicines.
- Confirm choices are invoice/photo, scan, paste list, upload file, and add while selling.
- Tap Paste list.
- Paste a clean list:

```text
Cefixime tablets 120
Ceftriaxone vial 180
Salbutamol inhaler 250
Metformin tablets 15
Omeprazole capsules 20
Diclofenac gel 180
Hydrocortisone cream 180
Azithromycin suspension 350
Zinc syrup 70
```

Pass criteria:

- A CatalogImportCard appears.
- Owner can edit the list.
- Approving saves medicines to the pharmacy catalog.
- Notifications stay separate from Operations Chat.
- No OpenAI/API call.

## Scanner And Invoice Onboarding

Numbered live status:

- Test 1 — AfyaLink supplier invoice/photo onboarding: PASSED and preserved.
- Test 2 — Dawa Bora second supplier invoice consistency: PASSED after editable review. Four medicines saved, catalog count reached 17, refresh persistence passed, and CSV download completed. Do not repeat without regression evidence.

Test:

- Use Invoice/photo.
- Use Scan shelves.
- Use file upload with CSV/text.
- Confirm each path creates a review card with batch and expiry where relevant.

Pass criteria:

- Review cards do not claim real OCR/barcode extraction unless actually available.
- Owner can correct and approve.
- Confirmed data saves to the pharmacy catalog.
- Repeated known information should be reused locally.

## Chat Workspace After Catalog Approval

Test:

- Type `Panadol 2 cash`.
- Confirm it records instantly and returns a sale receipt.
- Try `panadol2cash`.
- Confirm it records the same sale intent.
- Type `Panadol 2`.
- Confirm it shows an editable card directly, without a narration message before the card.

Pass criteria:

- Local parser handles known structured sale.
- No OpenAI/API call.
- Complete sale does not show an editable card.
- Missing or ambiguous sale does show an editable card.
- Owner can correct the card before confirm.

## Editable Sale Card

Test:

- Confirm fields: medicine, quantity, payment.
- Use `-` and `+` to adjust card text size.
- Change quantity.
- Change payment mode.
- Cancel card.
- Confirm no `Cancelled.` chat bubble appears.
- Create another sale card.
- Confirm card to offline queue.

Pass criteria:

- No direct production write yet.
- Confirmed action enters queue.
- Duplicate/idempotency behavior remains safe.
- Flow is three steps or less.

## Voice Workspace

Test:

- Tap Mic from the chat composer after setup is complete.
- Confirm the browser asks for microphone permission or starts listening.
- Speak a complete sale such as `Panadol 2 cash`.
- Confirm complete voice result records instantly.
- Confirm uncertain voice results can become review cards.

Pass criteria:

- Voice path uses the same local-first command route.
- Mic does not inject fake demo text.
- Mic status stays near the composer and does not create noisy chat messages.
- No AI/API call unless explicitly enabled later.

## Photo Workspace

Test:

- Tap `+` in the composer.
- Choose Camera and take a photo from the phone.
- Choose Photo library and select an existing image.
- Confirm VisualScanCard appears.
- Confirm PhotoReviewCard appears.
- Confirm result is review-first.

Pass criteria:

- Photo path does not claim full production extraction yet.
- Camera capture is available directly from the app.
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
- Confirm chat home fits.
- Confirm chat screen fits.
- Confirm editable cards fit.
- Confirm action buttons are reachable.
- Confirm text does not overlap.

Pass criteria:

- Owner can complete common workflow on phone.
- Card text can be enlarged or reduced without browser zoom.
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

## Integrated Human Input And Medicine Card Coverage

Add this coverage at the relevant upcoming catalog, operations, scanner, import, reporting, and device stages. Do not restart passed tests or send the entire plan to the owner at once.

- Shared local resolver: exact catalog name, pharmacy alias/shorthand/learning, Source Brain name/alias/brand/generic, strength/form/unit, spelling/fuzzy/phonetic match, usage ranking, and safe ambiguity.
- Human input: exact, light/heavy typo, missing spaces, compact commands, capitalization, incomplete names, aliases, brand/generic names, shorthand, prior corrections, unknown input, and unsafe ambiguity.
- Autocomplete: catalog-first and Source Brain suggestions, touch/keyboard, preserve quantity/payment, ignore/select behavior, offline use, small ranked result set, and no unwanted insertion or API call.
- Live medicine action card: open from typing, autocomplete, voice, and scanner; show only available useful identity, stock, price, supplier, barcode, batch/expiry, shelf, aliases, and activity; test Sell, Restock, Stock, updates, history, reports, cancel, queue, sync, and duplicate prevention.
- Units and packaging: tablet, strip, box, capsule, bottle, vial, ampoule, tube, inhaler, sachet, and pack where catalog conversion data exists; never guess missing conversions.
- Canonical records: misspellings and shorthand must resolve to the correct catalog identity in receipts, stock, reports, and exports.
- Layout/state: phone portrait/landscape where practical, tablet, desktop, keyboard, touch, refresh, reopen, offline, and reconnect.
- All normal matching, autocomplete, cards, calculations, canonicalization, and duplicate checks remain local and zero-token.

Current live continuation after the 2026-07-11 restock pass:

```text
Cefixime stock is 25 after a verified +6 tablet restock. Continue with the next not-yet-tested onboarding method using a new Source Brain medicine not already in Zuri Pharmacy.
```
