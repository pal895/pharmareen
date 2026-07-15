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

## Roadmap additions preserved on 2026-07-13

These are future-stage requirements. They do not change the current onboarding test or reopen passed invoice tests.

- Remaining onboarding fixtures: before each untested onboarding method, read Zuri Pharmacy's current catalog, exclude already-onboarded medicines when testing additions, select only verified Source Brain medicines, create the exact realistic input asset, verify its format/content/route and internal arithmetic, push it when repository-hosted, and only then give the owner one phone action. Cover clean and messy paste lists, CSV, Excel, old-POS mappings, stock sheets, invoice assets, supported package images, and genuine supported barcodes as their existing stages are reached.
- Export Hub/document stage: after the scheduled onboarding, acquisition, Medicine Action Card, Mic Test 2, and broader sales/restocking checks, implement and live-test the in-app owner workflow for generating and downloading real files directly from MS2.0. Preserve CSV as a correctly encoded, escaped, machine-readable spreadsheet interchange and label it as best opened with Excel, Google Sheets, or another spreadsheet app. Separately support professional purpose-specific Excel, PDF, and Word outputs only where genuinely implemented. Verify pharmacy identity, Kenya date/time, summaries, readable fonts, widths, wrapping, grouping, pagination/repeated headers, phone/desktop download and viewing, printing, correct canonical rows, and no AI/API formatting. Apply this standard to catalog, inventory, onboarding, purchasing, supplier, stock, expiry, operational, financial, correction, and reconciliation outputs rather than emitting one generic raw table. Codex-created workspace files or committed fixtures are test inputs and references, not proof of this production workflow.
- Repository asset rule: commit every important reproducible fixture, Excel/CSV sample, PDF/Word template, export example, onboarding sample, testing asset, and safe downloadable report whenever appropriate. Git is the authoritative shared source; do not keep important assets only in Codex or temporary local storage. Never commit secrets, private pharmacy data, caches, or disposable runtime output.
- Restocking stage: expand the already-passed basic restock coverage across typed commands, Medicine Action Card, approved invoices, barcode/scanner where supported, manual editable cards, supplier delivery, and offline queue/sync. Include unit/strip/box/pack conversion, prices, supplier, batch, expiry, bonus, discount, duplicate delivery protection, safe corrections, persistence, history/reports, and no duplicate sync. Reuse known values and smart defaults; never guess conversions.
- Discount stages: add local deterministic percentage, fixed, line, invoice, purchase, sale-where-permitted, and supplier discounts. Always expose original price, discount type/value, final price, savings, and resulting totals; require review for financial impact and protect rounding, reports, receipts, profit, payments, stock independence, correction/void, double-discount, and non-negative-total behavior.
- Bonus-quantity stages: record purchased quantity, bonus quantity, total stock added, total purchase cost, effective unit cost where useful, supplier, batch, and expiry separately. Cover one/multiple medicines, box/strip/unit, invoice/manual restock, corrections, persistence, reports, supplier history, and cost/profit calculations without treating bonus stock as purchased quantity.

## Shared medicine recognition gate - 2026-07-13

- Live catalog search for `zinc sirup` exposed drift between exact catalog filtering and the broader medicine resolver.
- One local confidence-ranked matcher now covers canonical names, aliases, brand/generic names, forms, strengths, partials, compact/reordered text, common spelling, phonetic, and OCR variations. Catalog, Source Brain, Operations Chat, onboarding/import, sales, restock, stock enquiry, and speech-recognized text reuse it; no ordinary match spends AI tokens or creates records.
- Focused matcher, catalog workspace, and connected architecture verification pass. After one representative live `zinc sirup` verification, close this behavior class and continue from the next unfinished onboarding option; do not repeat equivalent medicine spellings without regression evidence.
- Onboarding remains open: finish current catalog validation, then continue the remaining CSV, Excel, bulk-paste variants, manual creation, learning during sales, any still-scheduled invoice/photo consistency, and barcode/scan onboarding before sales progression. Validate Medicine Action Cards with onboarding results.
- Current checkpoint after medicine-photo closure: Test 5 modern XLSX onboarding. Upload `fixtures/test-5-excel-import.xlsx`, verify one honest unsaved three-row review, and keep the catalog at 32 until approval. Legacy XLS is not claimed as supported.
- Test 5 XLSX approval, refresh persistence, exact 32-to-35 growth, unique Cetirizine/Co-Amoxiclav/Paracetamol records, and complete reviewed-field retention are live-verified. During the persistence check, typed `Show me` incorrectly entered medicine-sale parsing; before advancing, live-confirm that natural-case typed `Show me` opens the 35-item catalog directly and creates no Medicine Check. Do not approve or save anything during this routing check.
- Natural-case typed `Show me` is live-verified at the 35-item baseline: it opens the catalog directly, creates no Medicine Check, and saves nothing. Protect this checkpoint. The next Excel checkpoint is repeat-import duplicate prevention with the same committed Test 5 XLSX; all three already-saved rows must be excluded, no duplicate must be created, and the catalog must remain 35. In that same sequence, validate the permanent compact chat-header catalog icon: it uses the shared catalog controller, creates no chat message or draft, shows the same complete catalog, and closes back to the unchanged chat.
- The compact header catalog icon is live-verified at 35 medicines. The first repeat-XLSX attempt incorrectly exposed the three existing medicines as editable approval rows; it was not approved and the catalog remained 35. File and Paste List acquisition now share one pre-review catalog partition. Retest the same `fixtures/test-5-excel-import.xlsx`: expect a non-approvable no-new-medicines result naming Cetirizine, Co-Amoxiclav, and Paracetamol, an explicit nothing-saved statement, and an Open catalog action. Confirm the catalog remains 35. Do not approve or advance until this evidence passes.
- The repeat-XLSX no-new-medicines result and 35-item preservation are live-verified. Its `Open catalog` card button exposed one missing-render defect: shared navigation state changed, but the direct card action did not render it. The handler now calls the same shared controller and renders immediately, with focused source regression coverage. Keep this checkpoint open only for one button retest: tap `Open catalog`, confirm the complete 35-item catalog appears immediately, then close it and confirm no message, draft, approval, or catalog mutation occurred.
- Mic Test 2 remains mandatory after the current catalog friction and remaining onboarding/catalog checks are reliable, at the voice-input section before general sales progression. It must cover local speech text flowing through the shared matcher, aliases/misspellings/partials, first-use/mobile/offline behavior where supported, editable Medicine Action Card output, and zero-token matching for known medicines.
- For every friction in these stages, preserve stable behavior, fix the shared reusable component, run only directly affected focused regressions, save the reusable lesson in engineering memory, and resume at the interrupted action. Local-first/no-token behavior remains mandatory.
- Every live-test response must follow `docs/engineering-memory/live-test-execution-discipline.md`: provide exact copy-paste commands and self-contained ordered steps, keep the standard result/root/fix/regression/commit/command/test/expected/approval/next-evidence structure, and perform the completeness check before sending. Use current Engineering Memory and recent relevant diffs, inspect only the active shared root, run focused tests plus necessary protected regressions, and preserve all local-first and API-token discipline. This rule changes process only and never advances the active checkpoint.
- Onboarding completion now leads into a reusable Pharmacy Catalog workspace backed by the persisted catalog rather than copied card rows. The home screen must expose the catalog directly; the workspace must search locally, show all canonical medicines without duplicates, keep existing and newly approved medicines, use concise primary fields with progressive disclosure, and remain usable in one-column mobile and multi-column desktop layouts.
- `SHOW ME` is the permanent top-level catalog entry outside Operations Chat. A catalog row opens a progressively disclosed Medicine Action Card; edits require review and approval, discard without mutation, update the existing canonical record, block identity collisions, persist across refresh, and use zero AI tokens.
