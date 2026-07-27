# MS2.0 Live Main App Test Plan

## Current checkpoint — Notifications Review Import Action Routing

Excel, PDF, Word, Presentation, CSV and Print are owner-validated, permanently passed and protected. Do not retest or polish them without regression evidence. The one-card status/history architecture is approved.

Print owner evidence confirms the complete 35-medicine view and four readable Android native-preview pages, numbered 1/4 through 4/4, with no blank page, corruption, crash or printer selection. One compact history entry, one updated status card and clean chat also pass. Opening the dialog is not proof of physical printing.

The shared-root review is complete. Common behavior remains centralized in the canonical snapshot, format metadata registry, one pharmacy-scoped Export Hub card, pharmacy-keyed history/event routing and common dispatch. Future formats or shared behavior must extend those roots rather than create route-specific copies.

Notifications Quiet State is owner-validated, passed and protected. Evidence confirms Home and the separate Notifications workspace both showed zero unread, no alert card or Operations composer appeared, returning Home was unchanged, and no operational mutation occurred. Do not repeat it without regression evidence.

Notifications Pending Review Unread State is owner-validated, passed and protected after `c63f687`. Evidence proves Mic input, correct editable parsing, one unread local Learning alert, workspace isolation, cancellation integrity, mark-read and quiet-state restoration. Do not repeat those responsibilities without regression evidence.

Test only the next distinct responsibility:

1. Create one unapproved Paste List review with `Notification Action Test 10 mg tablet 1`. Do not approve it.
2. Return Home, open the single unread Notifications alert, and visually confirm `Review import` is now one clear compact tappable button rather than a large field-like value.
3. Tap `Review import` once.
4. Confirm MS2.0 returns to the exact existing `Notification Action Test` editable review card, with no duplicate review card and no saved medicine.
5. Cancel/close that draft, open the catalog and confirm `Showing 35 of 35`.
6. Return Home and confirm Notifications is quiet at zero unread.

Expected: one shared compact action routes to the existing review, no duplicate card, no catalog/stock save, no sale/payment, no API request and no AI token use. Do not test inventory, expiry or payment-failure alerts yet.

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
- The repeat-XLSX no-new-medicines result and 35-item preservation are live-verified. Its `Open catalog` card button exposed one missing-render defect: shared navigation state changed, but the direct card action did not render it. The handler now calls the same shared controller and renders immediately, with focused source regression coverage. Live evidence after `114e66d` verified that tapping `Open catalog` immediately rendered the complete `Showing 35 of 35` persisted catalog and that closing returned to the unchanged chat without a message, draft, approval, sale, new medicine, or catalog mutation. Test 5 modern XLSX onboarding is complete and protected.
- Mic Test 2 is now the active stage before general sales progression. It must cover local speech text flowing through the shared matcher, aliases/misspellings/partials, first-use/mobile/offline behavior where supported, editable Medicine Action Card output, and zero-token matching for known medicines. The first safe voice boundary is live-verified: spoken `show me` opened the complete 35-item catalog twice on intentional repeat, closed back to the same chat, and OpenAI Platform remained at zero tokens, zero requests, and zero spend. The next voice-restock attempt exposed shared recovery and workflow friction: offline failure blamed permission, one attempt returned no guidance, a fast phrase was honestly transcribed only as `syrup`, and the successful `restock zinc syrup` transcript was flattened into a sale-shaped review with Payment instead of retaining Restock. Voice recovery now reports offline/permission/network/no-speech honestly, never invents missing words, and retains a complete shared Restock card. Missing quantity stays blank and blocks saving; bought and bonus stock stay separate; known catalog values are reused; optional supplier, pricing, traceability, shelf, delivery-reference, and note fields remain available in three simple sections. Retest offline guidance, then say `Restock Zinc syrup 12` at a normal quick pace, inspect the complete no-Payment restock review, and close without tapping `Add stock`. Catalog count, Zinc stock, sales, approvals, and API usage must remain unchanged.
- The first post-fix evidence passed only the offline message. The online attempts produced different owner bubbles (`zinc syrup 12` and later `restock zinc syrup 12`) while the visible active card remained the generic sale-shaped review for transcript `zinc syrup 12`. The owner also heard an unexpected phone voice after tapping Mic. Keep Mic Test 2 open at this exact point: isolate whether the device/browser omitted `restock`, whether an older card remained active, whether the new card failed to focus, and what the audible words/source are. Do not mark voice restock passed, do not approve, and do not replace this checkpoint with typed or quick-action testing.
- Follow-up evidence identified the sound as a wordless Android/Chrome recognition pop after starting and another after manually stopping. The native start pop cannot be suppressed through Web Speech without replacing the zero-token browser recognizer; the avoidable second pop is removed by disabling the listening button and auto-stopping. Voice actions are now always review-first, the exact transcript is pinned visibly, and each new voice result replaces the prior voice draft so a stale Loratadine or generic card cannot appear to be the current result. Retest once: tap Mic, do not tap again, say `Restock Zinc syrup 12`, wait for auto-stop, confirm the visible transcript and complete Restock card, then close without saving. Do not advance Mic Test 2 until this passes live.
- Evidence after `9e5fb8b` isolated a browser-startup gap: speech begun immediately after tapping Mic occurs before Chrome's pop/audio-ready event, so leading words can be lost; speech begun after the pop produces the full correct Restock review. The long Listening label also crowded Send. The Mic lifecycle now shows compact `Wait` plus `Starting microphone… Please wait.` until the real recognition/audio-start event, then compact `Speak` plus `Speak now.` Both phases are disabled and auto-stop. Retest this exact phase transition once, then close the correct Restock review without saving.
- Evidence after `f1a85f9` showed `onstart` was still earlier than dependable audio capture and exposed a broader matcher defect: transcript `restock syrup 12` selected Loratadine because the generic form `syrup` scored as a medicine identity. Readiness now waits only for `onaudiostart`. Generic form/unit-only input can never select a medicine; it produces a blocked clarification review across voice, typed, sale, restock, and lookup paths. Retest `Restock syrup 12` for safe no-match, then `Restock Zinc syrup 12` for the correct Restock card. Close both without saving.
- Live evidence after `aed9819` passed both cases: generic `restock syrup 12` left identity blank and `Add stock` disabled, while `restock zinc syrup 12` produced the exact transcript and complete canonical Zinc Restock review. No approval occurred. Protect this behavior class. The next Mic Test 2 checkpoint is one complete spoken sale under the review-first rule: say `Cefixime 1 cash` after `Speak`, confirm the exact canonical review appears without an automatic sale, then close and verify stock is unchanged.
- Spoken-sale evidence showed that Android/Chrome may transform a difficult medicine pronunciation into multiple words (`Cefixime` became `suffix may`) and may return number words (`one`) instead of digits. The shared matcher now has a conservative catalog-wide phrase-phonetic comparison, and the shared local command parser normalizes common English/Kiswahili number words for sale and restock quantities. This is reusable accent tolerance, not a Cefixime-only alias. Ambiguous matches still stop for owner choice, generic-only identity still stays blank, and Medicine Match confirmation is blocked until medicine, positive quantity, payment, and selling price are complete.
- Resume with the easier saved catalog word `Zinc`: after `Speak`, say `Zinc one cash`. Expect canonical Zinc, quantity 1, Cash, exact heard text, and no automatic mutation. Close without Confirm and verify stock/sales remain unchanged.
- Live evidence after `4c419d0` passed this interpretation boundary exactly: transcript `zinc one cash`, canonical Zinc, quantity 1, Cash, and an editable review card appeared without a sale acknowledgement. Pronunciation, accent tolerance for this phrase, spoken-number conversion, canonical identity, payment parsing, and review-first presentation are passed. The only remaining action is to Cancel/close the draft and verify no sale was added and Zinc stock is unchanged; do not repeat the voice phrase.
- Follow-up saved-catalog inspection passed the no-mutation check: Zinc retained blank current stock, selling price 70, syrup form/unit, and alias `Zinc syrup`; the edit card said `No changes yet` and disabled `Approve & save`. The unconfirmed voice review did not alter stock or catalog data. Close this Mic Test checkpoint and continue only to the next distinct unvalidated voice responsibility.
- The deliberate bad-pronunciation test completed Mic Test 2: `suffix may one cash` resolved canonical Cefixime, quantity 1 and Cash while retaining the exact transcript and requiring review. Cancellation preserved Cefixime stock 25 and selling price 120; its saved record reported `No changes yet`. Mic Test 2 is closed.

## Transaction Completion Engine stage

- Permanent architecture is recorded in `docs/engineering-memory/transaction-completion-engine.md`.
- Prepare and protect the adapter boundary, Fast Record, Request & Verify state, simulator scenarios, non-blocking Payment Queue, daily sale numbering, permanent IDs, duplicate callbacks and linked undo/reversal before official-provider tests.
- Do not connect real M-PESA or card providers before simulator owner flows pass.
- First live checkpoint: type `Cefixime 1 cash` once. Expect an immediate TCE Fast Record receipt headed `Sale 1`, Cefixime x1, Cash and stock left 24. This intentionally records one local test sale from the verified stock baseline 25. Do not repeat or undo until analyzed.
- Preserve this active checkpoint while payment architecture is clarified. Future simulator/payment coverage must include isolated Pharmacy A and B merchants, the separate MS2.0 subscription merchant, cross-tenant rejection, missing/revoked credentials, wrong environment, wrong-tenant callback, duplicate callback, mismatched amount/merchant, provider capabilities, Fast Record, Request & Verify, payment queue, refunds/reversals and Operational Confidence without silent financial execution.
- Do not begin production provider testing or request credentials until the unresolved Safaricom multi-tenant onboarding question is answered directly by Safaricom or an authorized provider.
- Live evidence passed the first Fast Record transaction: typed misspelling `Cefimixe 1 cash` resolved canonical Cefixime, returned `Sale 1`, recorded Cash, reduced stock exactly once from 25 to 24, and persisted 24 with no pending catalog edit.
- Next checkpoint: type `Losartan 1 cash` once. Expect `Sale 2`, Losartan x1, Cash, and stock 39 from the protected baseline 40. This proves daily numbering continues across medicines through the shared TCE. Do not repeat or undo before analysis.
- Live evidence passed the second Fast Record transaction: `Losartan 1 cash` returned `Sale 2`, recorded canonical Losartan x1 as Cash, reduced stock exactly once from 40 to 39, and persisted the complete saved commercial and traceability record with no pending catalog edit.
- The Fast Record cash baseline is complete. Next implement and focused-test the simulator-backed Request & Verify owner flow and non-blocking Payment Queue. Do not connect a real provider or request credentials. Issue the next owner live command only after this shared stage is implemented, documented, committed, pushed, and deployed.
- Simulator Request & Verify is implemented as an owner-selectable Payment Queue mode. Non-cash requests use only the Simulator adapter, remain pending without stock mutation, never block the next sale, and resolve through explicit simulated paid/failed actions. Confirmed stock application is idempotent.
- Live evidence passed the pending boundary: on the next pharmacy business day, `Losartan 1 mpesa` correctly became that day's `Sale 1`, entered one visible Simulator M-Pesa waiting item, allowed serving to continue, and preserved stock 39. The prior `Sale 3` expectation was wrong because daily display numbers reset. Fix shared presentation friction: label queue history by pharmacy day, fill only the selected completion mode, and always open the queue at its heading.
- Next checkpoint after deployment: do not create another sale. Open Payment Queue, verify `Today · Sale 1`, Losartan x1, M-Pesa, Waiting and only Request & Verify filled; tap `Simulate paid` once. Expect Waiting to clear, completed history/receipt to remain, and stock to change exactly once 39→38. Do not repeat until analyzed.
- Live evidence passed persistence and one-time resolution: the waiting item survived into the following day as `2026-07-17 · Sale 1`, retained Losartan x1/M-Pesa, and one simulated-paid action moved it to completed. Date display and selected-mode styling passed. Fix the newly exposed financial-review friction at the shared queue renderer: waiting requests must show `Expected amount: KES …`; history must retain date, sale label, medicine, quantity, amount, method and status. The resolution checkpoint remains open only for receipt and saved Losartan stock 38 evidence.
- Live evidence after the financial-context deployment completed the paid checkpoint: history showed `2026-07-17 · Sale 1 · Losartan x1 · KES 25 · M-Pesa · completed`; the MS2.0 receipt showed stock left 38; the saved Losartan card independently showed stock 38 and no pending changes. Confirmation mutated stock exactly once 39→38. The receipt was present lower in the conversation, so no receipt-rendering change is needed.
- Next checkpoint: with Request & Verify still selected, type `Losartan 1 mpesa` once. Verify one waiting request with expected KES 25, then tap `Simulate failed` once. Expect zero waiting, failed history, no completed receipt for that request, and saved Losartan stock still 38. Do not repeat before analysis.
- For every friction in these stages, preserve stable behavior, fix the shared reusable component, run only directly affected focused regressions, save the reusable lesson in engineering memory, and resume at the interrupted action. Local-first/no-token behavior remains mandatory.
- Every live-test response must follow `docs/engineering-memory/live-test-execution-discipline.md`: provide exact copy-paste commands and self-contained ordered steps, keep the standard result/root/fix/regression/commit/command/test/expected/approval/next-evidence structure, and perform the completeness check before sending. Use current Engineering Memory and recent relevant diffs, inspect only the active shared root, run focused tests plus necessary protected regressions, and preserve all local-first and API-token discipline. This rule changes process only and never advances the active checkpoint.
- Same-commit Project Brain rule: when accepted implementation changes architecture, permanent behavior, UX decisions, protected behavior, fixtures, token policy, the testing sequence, or the active checkpoint, update the relevant Engineering Memory and Project Brain documents in the same commit and push them together. Avoid documentation churn for trivial details that do not change permanent project knowledge.
- Permanent zero-unjustified-AI rule: no routine operational workflow may invoke an LLM or paid AI API without a complete approved entry in `app/ai_policy.py`. Reports and other deterministic pharmacy operations stay local. Current approved exceptions are bounded voice-note transcription, ambiguous-command fallback only after local parsing fails, and explicitly enabled review-first photo/invoice extraction; each must retain its documented fallback, token/cost controls, timeout, zero automatic retries, caching and privacy scope. Unregistered calls fail closed.
- Active report-performance continuation: after deploying the zero-AI report path, the startup shell must automatically show the real `REPORT_SOURCE_SNAPSHOT_WARMED logs=<count> transactions=<count>` line. Then perform exactly two immediate Last 7 days refreshes and capture both generation times, both Generated At values and screenshots. Do not repeat completed speech or export tests. Performance remains open until this live evidence passes.
- Circuit breaker: once the root cause is identified, two further inspection or command cycles without new evidence end the investigation. Apply the smallest justified shared-root fix or report one concrete blocker; never continue an open-ended loop.
- Onboarding completion now leads into a reusable Pharmacy Catalog workspace backed by the persisted catalog rather than copied card rows. The home screen must expose the catalog directly; the workspace must search locally, show all canonical medicines without duplicates, keep existing and newly approved medicines, use concise primary fields with progressive disclosure, and remain usable in one-column mobile and multi-column desktop layouts.
- `SHOW ME` is the permanent top-level catalog entry outside Operations Chat. A catalog row opens a progressively disclosed Medicine Action Card; edits require review and approval, discard without mutation, update the existing canonical record, block identity collisions, persist across refresh, and use zero AI tokens.

## Permanent cross-input equivalence lane

Typed input is a required supported interaction path even though MS2.0 minimizes typing. At each logical workflow stage, use the smallest representative comparison to prove that an equivalent typed, spoken, scanned, imported, photographed, selected, or otherwise supported intent reaches the same shared domain behavior. Preserve medicine identity, form, strength, quantity, unit/pack, prices, payment where relevant, supplier, bonus, discount, batch, expiry, validation, approval, mutation, duplicate safety, and final saved result.

Representative typed coverage must eventually include sales, restocking, stock checks, missed demand/out-of-stock, corrections/undo, reports and operational questions, medicine lookup, supported onboarding/creation, complete commercial and traceability details, aliases, compact commands, natural phrases, reasonable misspellings, and ambiguity that asks instead of guessing. Do not duplicate every existing test. Reuse protected shared-root evidence and add only the smallest cross-channel comparison.

The typed `restock zinc syrup` screenshot is unverified future evidence. At the appropriate typed/restock stage, determine whether canonical Zinc and syrup form are preserved, whether missing quantity/defaults are safe, and whether typed and spoken equivalents converge. Do not implement or test a Zinc-only exception now.

## Active feature coverage map

Every active discoverable feature must eventually receive controlled live validation. Track shared-root coverage separately from source-specific coverage.

| Entry point | Input source | Shared root | Source-specific responsibility | Expected result | Mutation / approval | Offline / tokens | Existing coverage | Smallest remaining live test |
|---|---|---|---|---|---|---|---|---|
| Camera | Direct capture | Visual acquisition and medicine review | Camera permission, capture, retake/use lifecycle | Honest review or clear retry | No save before approval | Local-first; zero-token unless explicitly authorized | Representative camera flows passed | Only source-specific untested workflow cases |
| Photo library | Existing image | Same visual review root | Picker and selected-file retention | Same canonical review rules | No save before approval | Local-first; zero-token-first | Gallery flows partly/passed by stage | Only untested image responsibility |
| Shelf photo | Camera or library | Shelf recognition to catalog review | Multi-medicine shelf acquisition | Honest multi-row review or retake | Explicit approval | Zero-token controlled path | Gallery/direct shelf coverage protected | Do not repeat without regression evidence |
| File | XLSX/CSV/text | Shared catalog import preparation | File picker and format parsing | New-only review or no-changes result | Explicit approval; duplicate-safe | Local and zero-token | CSV/XLSX protected | Later untested formats/mappings only |
| Invoice | Camera/photo/file | Invoice extraction to catalog review | Invoice structure, totals, incomplete-scan safety | Invoice-specific editable review | Explicit approval | Local-first; token policy visible | Two invoice fixtures protected | Later distinct source responsibility only |
| Scan barcode | Live barcode | Barcode decode and catalog/source lookup | Scanner activation and honest unknown fallback | Known review or unmatched safe result | Explicit approval | Local and zero-token | Known/unknown barcode coverage protected | Do not repeat without regression evidence |
| Paste list | Typed/pasted list | Shared catalog import preparation | Paste editor and row parsing | New-only/mixed/no-changes review | Explicit approval | Offline-capable; zero-token | Clean/all-existing/mixed protected | Remaining genuinely different messy variants |
| Stock fix | Manual correction | Stock-correction validation/mutation | Reason and safeguard rules | Editable correction review | Explicit approval | Local-first; zero-token | Not fully closed | Controlled stock-fix stage |
| Report | Owner request | Report intent and generator | Report type, period, readable result | Clear report review/output | Confirm as required | Local-first; zero-token formatting | Not fully closed | Scheduled report stage |
| Export CSV | Download action | Canonical export generator | Encoding, download, phone opening | Correct downloadable catalog CSV | No catalog mutation | Zero-token | Earlier CSV download evidence partial | Export Hub integrity stage |
| Setup | Owner fields | Onboarding/setup memory | First-use completion and correction | Ready pharmacy setup | Explicit confirmation | Offline-safe where supported; zero-token | Basic setup represented | Remaining scheduled setup coverage |

For every row, retain the full internal mapping: entry point, source, shared root, unique responsibility, visible result, mutation/no-mutation, approval, offline behavior, token expectation, regression protection, prior coverage, and smallest remaining live test. A shared-root pass reduces repetition but never hides an untested permission, acquisition, parser, format, recognition, export, or failure path.

## Next controlled live sequence: automatic completion

1. Passed on 2026-07-18 — Home/catalog protection: after a clean Replit pull and restart, home retained MS2.0 Assistant, Notifications and Payment Queue, the SHOW ME tile was absent, the header icon opened `Showing 35 of 35`, and closing returned home without a message, draft, approval, sale, mutation, notification or waiting-payment change. Do not repeat without regression evidence.
2. Passed on 2026-07-18 — Quiet concurrency: Today’s Sale 2 Losartan x1 at KES 25 and Sale 3 Cefixime x1 at KES 120 waited together with stocks unchanged at 38 and 24. Completing Sale 3 first changed only Cefixime to 23 and left Sale 2 waiting; completing Sale 2 then changed Losartan to 37 and cleared the queue.
3. Passed on 2026-07-18 — Final truth: both completed history rows and receipts retained correct day, sale label, medicine, quantity, amount and method; saved cards independently showed Cefixime 23 and Losartan 37 with no draft changes; Notifications remained at 0 unread. The automatic-completion simulator sequence is complete. Do not repeat it without regression evidence; no credentials or real provider are authorized.

## Next controlled live sequence: Stock fix

The first Losartan attempt failed before queueing: all values were visible, but Confirm and guidance retained readiness from the initial blank render. The shared lifecycle fix is implemented and protected; this checkpoint is not passed until screenshots prove it.

1. Pull and restart, open MS2.0, tap `+`, then `Stock fix`. Verify one blank editable card appears and nothing changes before confirmation.
2. Use a different saved medicine: Medicine `Cefixime`, Current stock `23`, Correct stock `22`, Reason `Physical count test`. Visit all three sections and return to each once. Verify every value remains and only the current section is highlighted.
3. Tap Read and verify the local spoken summary covers Cefixime, 23, 22 and the reason. Pause/Resume/Stop may be checked without changing the draft.
4. Tap Confirm once. Expect `Stock fix waiting to sync`, `Cefixime: 23 → 22`, the reason, and `Saved stock is still 23.`
5. Reopen Cefixime from the complete saved Pharmacy Catalog and confirm Current stock remains 23 with `No changes yet`. Do not tap Sync or repeat. Return the populated three sections, waiting-to-sync result and unchanged saved stock. Picture-assisted and voice-guided Stock Fix remain separate later tests with different medicines.

Second-attempt evidence proved slide/value retention and single active-tab styling, but Confirm remained disabled because the trusted-stock reader omitted canonical `stockLeft`. It also proved one long Android/Chrome utterance could not provide reliable Pause/Resume or visual synchronization. After the shared fix, repeat only the interrupted Cefixime card: guidance must become ready, Read must move Fast action → Stock & details → Reason & review as those segments are spoken, Pause/Resume must continue from the paused segment, and one Confirm must queue without applying stock.

Latest evidence passes Read, automatic section movement, pause/resume, and ready Confirm. Protect those passes. The only remaining manual step is Confirm: after pulling the latest code, refresh the existing Cefixime draft, tap Confirm once, then verify the waiting-to-sync result and saved stock 23. The card now shows only Confirm, one Read/Pause/Resume control, and More; its section labels are Medicine, Stock, and Reason.

Corrected checkpoint: the Cefixime pending result is friction because an online Stock Fix must update saved stock immediately. The shared execution repair is ready for one different-medicine test: note Losartan's saved stock; open Stock Fix, enter a different corrected quantity and reason, then Confirm once; verify `Stock updated` and that Pharmacy Catalog immediately shows the corrected quantity. Do not repeat Read or begin picture/voice Stock Fix yet.

Passed after `9deb92f`: startup automatically applied the retained Cefixime 23 to 22 fallback once. Losartan then changed online from saved stock 37 to 39 with one Confirm and a `Stock updated` result; reopening its saved card independently showed Current stock 39 and `No changes yet`. Manual Stock Fix is complete and must not be repeated without regression evidence.

Next distinct checkpoint is picture-assisted Stock Fix using a different catalog medicine and a newly prepared realistic controlled package with a known trusted stock baseline. Do not issue the live test until the fixture, local recognition boundary, shared execution convergence and focused regression checks are ready. Do not reuse Amoxicillin because its saved stock is blank, and do not begin guided voice yet.

Prepared picture checkpoint: use `/main-app/fixtures/stock-fix-prednisolone-5mg.png`. After pull/restart and downloading that fixture to the phone, open Stock Fix and choose More → Photo. Expect canonical Prednisolone and trusted Current stock 24 from Pharmacy Catalog; the image must not fill Correct stock or Reason. Enter 23 and `Picture count test`, Confirm once, then verify `Stock updated. Prednisolone: 24 → 23.` and saved Current stock 23 with no pending duplicate. Do not test Read, camera acquisition, guided voice or another medicine.

The first attempt stopped before photo selection because More's options were clipped outside the carousel and appeared unresponsive. After the layout repair, resume the same blank Stock Fix card at More → Photo; do not recreate or repeat any passed step beyond what refresh requires.

The repaired More panel and Google Photos picker passed, but the first selected representation returned to a blank card because its cropped/re-encoded visual identity was outside the initial bounded references. After deployment, repeat only Photo selection with the same Prednisolone fixture. It must either fill Prednisolone/current stock 24 or show an explicit safe failure; if filled, continue with 23 and `Picture count test` as already specified.

The repeat produced the required explicit safe failure; Google Photos remains unsuitable for this controlled exact fixture. After deployment, resume at More → File, choose `stock-fix-prednisolone-5mg.png` from Downloads, and expect deterministic Prednisolone/current stock 24. Do not repeat Google Photos or broaden recognition.

Android still opened Google Photos because the first File path reused an image-capable input. Download `/main-app/fixtures/stock-fix-prednisolone-5mg.ms20image`, then use More → File and select that exact file from Downloads/Files. It is byte-identical to the PNG and uses the same SHA gate; do not select the PNG or use Google Photos again.

Superseded by the shared media repair: do not use the `.ms20image` transport. Camera, Photo and File now feed one bounded local OCR/catalog-matching pipeline and one shared draft; the microphone uses the same identity and draft boundary. Begin with Test 1 only: Photo-select the prepared Prednisolone PNG, verify Prednisolone and saved stock 24 plus supported package details, enter corrected stock 23 and reason `Picture count test`, then Confirm and verify immediate stock 23. Camera, File and microphone follow only after this evidence returns.

Passed on 2026-07-18 — Stock Fix Test 1 Photo. After the clean pull/restart, Android Photo selection filled canonical Prednisolone and trusted saved stock 24 without a low-memory error. One confirmation with corrected stock 23 and reason `Picture count test` produced `Stock updated. Prednisolone: 24 → 23.` The saved Medicine Action Card independently retained Prednisolone 5 mg, tablet form/unit and commercial values, showed Current stock 23 and `No changes yet`, and required no second approval or Sync. No pending duplicate was visible. Protect this pass and do not repeat it without regression evidence.

Next distinct checkpoint: Stock Fix Test 2 Camera with a different saved medicine. Prepare and verify one suitable camera package and its exact saved-catalog stock baseline before issuing the test. Run Camera alone; do not combine File or microphone.

Prepared Camera checkpoint: display `/main-app/fixtures/stock-fix-metronidazole-400mg-camera.png` on the laptop. Confirm the saved Pharmacy Catalog baseline is Metronidazole 36 before mutation. On the phone open Stock Fix → More → Camera, capture only that carton, and use the captured photo. Expect canonical Metronidazole, trusted Current stock 36 and supported package details; Camera must not fill Correct stock or Reason. Enter 35 and `Camera count test`, Confirm once, then verify `Stock updated. Metronidazole: 36 → 35.` and saved Current stock 35 with no pending duplicate. Stop after Camera; do not start File or microphone.

Initial evidence produced an unsafe inconsistency: the first clear Camera capture returned no safe match, while the second capture of the same carton returned Metronidazole 400 mg/current stock 36 and successfully applied 36 to 35. Local OCR had discarded every pass except the longest, even when a shorter pass contained the medicine name. The shared backend now unions unique evidence lines from normal and binary layout passes before deterministic catalog matching. Reason is also optional for rush-hour Stock Fix: the label and guidance say so, blank reason no longer blocks Confirm, and the audit stores blank rather than inventing text.

Repair checkpoint after deployment: capture the same displayed Metronidazole carton twice in the same Camera-only session. Both completed reads must populate canonical Metronidazole and trusted Current stock 35 with the same supported package details. After the second read, enter Correct stock 34, leave Reason blank, Confirm once, then verify `Stock updated. Metronidazole: 35 → 34.` and saved Current stock 34 with no pending duplicate. Stop; do not start File or microphone.

Optional Reason passed after `c86cfc8`: blank Reason left Confirm ready, one confirmation applied Metronidazole 35 to 34, and the saved card independently showed Current stock 34 with retained medicine/commercial details and no draft change. Camera consistency remained open because the first post-repair capture returned no match while the next capture returned canonical Metronidazole/current stock 35. The next shared repair adds package-region OCR and safe unique catalog identity through exact barcode, exact batch, or strength-plus-expiry; it never selects from strength alone or a duplicated identifier.

Next checkpoint after deployment: use the same displayed Metronidazole carton and saved baseline 34. On one Stock Fix draft, perform Camera capture twice without confirming or changing stock. Both completed reads must independently show canonical Metronidazole, trusted Current stock 34 and the same supported package details. Stop and return both populated results; do not mutate stock, start File or start microphone.

Evidence after `b9aea88` still failed consistency: the first capture produced no match and the second populated Metronidazole/current stock 34; no correction was entered or confirmed. The first package crop did not recover any strong identifier on the failed frame. The local OCR root now tightens the lower-center package crop, enlarges it before reading, applies normal and binary layouts, and adds an upper-package name/strength pass. After deployment, repeat exactly the same two Camera reads with saved baseline 34 and no mutation. Both must populate the same canonical medicine, stock and package details before Camera can close.

Passed after `74f7f69` — Stock Fix Test 2 Camera consistency. The repeated Camera-only result retained canonical Metronidazole, recognized strength 400 mg and trusted saved Current stock 34 across Medicine, Stock and Reason. Correct stock and optional Reason remained blank, so no confirmation, mutation or pending action occurred. Protect Camera and do not repeat it without regression evidence. The next distinct source is File using another supported saved medicine image; prepare that isolated checkpoint before testing. Do not begin microphone with File.

Prepared File checkpoint: download `/main-app/fixtures/stock-fix-ibuprofen-200mg-file.png` to the phone. Open one blank Stock Fix card, choose More → File, and select that normal PNG. Expect canonical Ibuprofen, trusted Current stock 28 and supported package details; File must not fill Correct stock or optional Reason. Enter Correct stock 27, leave Reason blank, Confirm once, then verify `Stock updated. Ibuprofen: 28 → 27.` and saved Current stock 27 with no pending duplicate. Stop after File; do not begin microphone.

Passed on 2026-07-18 — Stock Fix Test 3 File. Android selected the normal Ibuprofen PNG, the result stayed in Stock Fix, and the shared local evidence path populated canonical Ibuprofen 200 mg with trusted saved Current stock 28. Blank optional Reason remained valid; one Confirm applied 28 to 27 immediately. The saved Medicine Action Card independently retained tablet form/unit, prices 18/9, Current stock 27 and `No changes yet`, with no second approval, onboarding card or pending duplicate. Protect File and do not repeat it without regression evidence. The next distinct source is guided microphone with a different harder-to-pronounce saved medicine; prepare it before testing and do not combine another image source.

Prepared guided-microphone checkpoint: use the existing blank Stock Fix card and the bottom Mic control; do not use Camera, Photo, File, Read or manual field entry. Speak `Co-Amoxiclav`, expect canonical Co-Amoxiclav and trusted Current stock 24, then speak `23`. On the Reason section leave the optional field blank and say `Confirm`. This first Confirm must not mutate: it must read Medicine, Current stock, Correct stock and `Reason: not provided`, moving through all three sections. When the microphone resumes after the review, say `Confirm` once more. Expect exactly one `Stock updated. Co-Amoxiclav: 24 → 23.` result. Open the saved Co-Amoxiclav Medicine Action Card and verify Current stock 23, canonical name retained, `No changes yet`, disabled approval and no pending duplicate. Stop after this microphone test.

First-attempt evidence failed at microphone capture, before matching: Android stayed on `Speak` and displayed neither heard words nor an error despite more than ten repetitions; the Stock Fix draft remained blank and Co-Amoxiclav stayed 24. After deploying the capture repair, repeat only step one: tap Mic once, say `Co-Amoxiclav` once, then pause. Return the visible `Heard: “…”` text and the Medicine section result. Do not speak stock or Confirm yet. The repaired control must finish after speech or eight seconds, show the transcript, and either populate canonical Co-Amoxiclav/current stock 24 or show an explicit `I heard …` safe mismatch that waits for another tap.

The capture repair made Android words visible (`call amoxic love`, `call amoxiclav`) and a later safe match filled canonical Co-Amoxiclav/current stock 24, but the conversation did not pass. It sometimes retained the Medicine section/wrong prompt, did not reliably accept `current stock 24` plus `new stock 23`, and ended the ready Reason card without a useful acknowledgement/next instruction. No Confirm occurred; saved Co-Amoxiclav remains 24.

After deploying the guided-stage repair, reopen one blank Stock Fix and complete Co-Amoxiclav only. Tap Mic and say `Co-Amoxiclav`; require a visible transcript entry, canonical Co-Amoxiclav/current stock 24, automatic Stock section, and a local acknowledgement telling you to say the new correct stock. When listening resumes, say the single full Stock transcript `current stock is 24, new stock is 23`; require both values, automatic Reason section, and an acknowledgement that Reason is optional and the next choices are a reason or Confirm. When listening resumes, say `no reason`; require the transcript, blank optional Reason, and the complete three-section spoken review. When listening resumes after review, say `Confirm` once; require exactly one `Stock updated. Co-Amoxiclav: 24 → 23.` and independently saved stock 23 with no draft change or pending duplicate. Stop. Only after this passes, prepare a separate different-medicine consistency test using the same three-stage script.

Owner evidence after `1b4de86` proves exactly one Co-Amoxiclav 24 to 23 result, retained transcript/canonical identity/blank Reason, independently saved stock 23, disabled approval and no visible duplicate. The saved card also displayed a contradictory hard-coded `Unsaved draft` badge beside `No changes yet`. After deploying the shared review-derived card status repair, reopen Co-Amoxiclav and require `Saved medicine`, Current stock 23, `No changes yet`, and disabled approval. Then close it. Do not change a field or run Stock Fix during this verification. After that passes, prepare the separate different-medicine guided consistency test and capture the complete review before its post-review Confirm.

Passed after `a7fbc82`: reopened canonical Co-Amoxiclav showed `Saved medicine`, Current stock 23, all retained catalog details, `No changes yet`, and disabled approval. No edit or Stock Fix was performed. Next, run the isolated different-medicine guided consistency checkpoint with saved Cetirizine at trusted stock 45. Open one blank Stock Fix, tap Mic once and say `Cetirizine`; require canonical identity, current stock 45 and automatic Stock guidance. Say `current stock is 45, new stock is 44`; require correct stock 44 and automatic Reason guidance. Say `no reason`; require blank optional Reason and the complete Medicine → Stock → Reason review. Stop before the post-review Confirm and return screenshots of the transcript and complete review. Saved Cetirizine must remain 45 at this checkpoint.

Failed safely in scope but mutated once: the Cetirizine draft retained canonical medicine, current 45, corrected 44 and blank Reason, yet the first spoken Confirm produced `Stock updated. Cetirizine: 45 → 44.` without the required visible review. The reopened saved card confirms stock 44, no changes and disabled approval. After deploying the explicit review-lifecycle repair, use a new blank Stock Fix and say `Cetirizine`, `current stock is 44, new stock is 43`, and `no reason`. Then say `Confirm` once. Require the complete Medicine → Stock → Reason review and a prompt to Confirm again. Stop without the second Confirm; saved Cetirizine must remain 44. Return the transcript and review evidence only.

Passed after `8e273f6`: one spoken Confirm entered and completed review without mutation; the transcript retained Cetirizine/new stock 43/blank Reason/Confirm, the card reported review complete, and saved stock remained 44. The second-confirm requirement was visible only after review and a silent auto-listen replaced it with a generic transcript error, creating owner friction. After deploying the guidance repair, discard the existing unexecuted draft and open one fresh Stock Fix. Repeat Cetirizine 44 to 43 with `no reason`; require explicit guidance that Confirm is said once to review and again to apply. Say the first Confirm, hear/see the full review and exact request for the second Confirm, then say Confirm once more. Require exactly one `Stock updated. Cetirizine: 44 → 43.`, saved stock 43, no draft and no duplicate.

Passed after `a2211a0`: the fresh guided Cetirizine flow explained the two-confirm contract, first Confirm visibly began the Medicine/Stock/Reason review, and second Confirm applied exactly one 44 to 43 update. The independently reopened saved card retained canonical Cetirizine 10 mg, tablet form/unit, stock 43, prices, packaging/supplier/traceability fields, `No changes yet`, disabled approval and no visible duplicate. Stock Fix is complete. Next controlled feature-map checkpoint: tap `+`, then `Report`. Require one local `Check report` card for Today with its focus and backend route visible. Do not Confirm, download, edit, create a sale or mutate anything. Return one screenshot of the complete report card.

The first Report card failed owner-facing acceptance: it exposed the backend URL, Confirm meant saving a request rather than generating a result, and Download CSV was the unrelated catalog export. After deploying the shared report boundary, tap `+` → `Report`, verify there is no backend route or CSV action, then tap `Generate report` once. Require a visible read-only Today report generated from saved pharmacy records, an explicit statement that nothing was sent to WhatsApp, and no sale/stock/catalog/approval/queue mutation. Return the complete report card. Do not start PDF, Word, Excel or CSV download coverage yet.

Generation succeeded after `41f1583`, but shared card field mapping still displayed a blank Backend Route and hid the returned report date/text; the guidance also remained the obsolete request-saving copy. After deploying the schema repair, reopen the existing `Today's report` card and tap `Refresh report` once. Require visible Report date and complete read-only report text plus `Generated from saved pharmacy records. Nothing was sent to WhatsApp.` No backend route may appear and no operational data may mutate. Return the full card; do not test downloads yet.

The returned `2026-07-19` zero-sales totals are consistent with the authoritative live evidence: this business day validated stock corrections but no sale. The audit found three shared defects: preview refreshes appended duplicate report-history rows, identical content had no freshness evidence, and the global developer `<pre>` rule clipped and restyled the owner report. Report preview/refresh is now a no-store read-only recomputation, exposes a Nairobi generation timestamp and source scope, removes the duplicate Sales total, and uses an unclipped owner-readable layout. After deployment, tap `Refresh report` once. Require a changed Generated at value, one Total Sales line, the complete report through Source, the same honest zero sales, and no sale/stock/catalog/approval/queue or report-history mutation. Do not test downloads yet; professional PDF/Word/Excel/CSV validation remains at the approved Export Hub stage.

Live evidence after `9fbf0d2` loaded the new schema/layout but did not complete refresh: Generated At stayed blank, the retained pre-fix report still contained both Sales lines, and the card remained at `Generating today's report...`. Root causes were an unbounded browser request, persisted transient `submitting` state that could permanently trap a resumed card, and an unnecessary Google Sheets transaction read even when the authoritative local sale ledger supplies finance totals. Durable-card hydration now clears transient submission state and labels legacy snapshots `Not refreshed yet`; interrupted loading gets precise retry guidance; report fetch has a 20-second abort boundary that preserves the prior snapshot; and ledger-backed reports skip the redundant transaction-sheet read. Retest the same card after deployment with one Refresh. Require completion within 20 seconds, a real Generated At value, one Total Sales line, complete Generated/Source lines, and the unchanged honest zero totals. If the backend exceeds the bound, return the exact timeout guidance and Replit server log rather than tapping repeatedly.

Passed after `db6dbd1`: refresh completed, Generated At displayed `19/07/2026, 02:40:09`, a later refresh advanced the report body to `Generated: 02:50 Africa/Nairobi`, exactly one `Total Sales: KES 0` remained, the full source line was visible, and guidance confirmed no WhatsApp send or duplicate report save. The zero totals remain honest because no sale occurred on this business day. Code review of the next Read checkpoint found that generic card narration would repeat labels/date/freshness and announce raw field names before the report. The shared Read boundary now narrates only the authoritative report body, speaks KES/Ksh as Kenyan shillings and M-Pesa naturally, and gives truthful guidance if no report exists. After deployment, tap Read once and listen through at least Total Sales, Payment totals, Cost and Gross Profit. Require one clean narration with no repeated form labels and no mutation. Return whether those lines were spoken correctly; do not test exports yet.

Read content passed after `1124e37`: Total Sales, Payment totals, Cost and Gross Profit were spoken clearly. Live evidence exposed a shared five-second silent start across editable cards. Root cause was the common speech path unconditionally calling `speechSynthesis.cancel()` immediately before every `speak()`, which can force Android Chrome to restart its speech queue, combined with voices not being warmed at startup. All editable-card and guided-review narration now uses one shared speaker: voices are loaded early, idle speech starts immediately without cancellation, and cancellation plus a short restart is used only when replacing active or pending speech. After deployment, tap the report Read button once while no other narration is active. Require audible speech to begin promptly (target under one second), correct report content and no mutation. Return the observed start delay; do not test exports yet.

Passed after `f691df2`: first report narration began in about one second and content remained clear. Two reporting-stage gaps were then accepted as permanent requirements. First, generic editable-card speech had no visible Pause/Resume/Stop lifecycle. The shared speech controller now exposes Pause and Stop while active and Resume while paused, across Report and other generic editable cards, without changing the protected guided Stock Fix controller. Second, Report was hard-coded to Today. The shared deterministic report contract now accepts Today, Yesterday, any ISO date, Last 7 days, This/Last week, This/Last month, and an inclusive ISO custom range. It reads the requested saved transaction/log interval, uses transaction rows for sales/cost/profit when available with sale-ledger fallback, bypasses caches, never persists previews, rejects future/invalid ranges, and keeps freshness outside the report body so identical records produce identical report text. Historical current-stock warnings are omitted rather than presenting today's stock as past stock. The permanent follow-on matrix must expand historical expenses, credits, restocks and inventory movement as those canonical ledgers are exercised; no absent record type may be invented. After deployment, in the same Report card replace Period with `Yesterday`, tap Refresh once, and require Report Date/body `2026-07-18`, a Generated At value, Source, and values derived only from saved records. Then tap Read, Pause, Resume and Stop to validate the shared controls. Do not test exports yet.

Historical Yesterday returned `2026-07-18` with zero sales/payments/cost/profit/items/transactions/restocks/no-stock requests and no activity. This is consistent with supplied evidence, which showed stock corrections but no July 18 sale; it is not proof of unobserved external records, so the saved sources remain authoritative. Three frictions failed the checkpoint: response took about one minute, Resume did not restart speech, and the historical source text incorrectly included current stock. Root causes were Yesterday falling back to the daily path (including an irrelevant current-stock query), separate full Google Sheets reads for logs and transactions, and Resume trusting Android's unreliable `speechSynthesis.paused` flag. Historical generation now always uses the historical path, retrieves filtered Daily Log and Transactions ranges in one Sheets batch request, excludes present stock and says so explicitly, uses a historical title/guidance, and resumes from MS2.0's own paused state. After deployment, leave Period `2026-07-18`, refresh once, and time it; target under 10 seconds. Require historical source wording/no current-stock claim and the same saved-record totals. Then Read, Pause, Resume and Stop once each. Return elapsed time and control results; do not tap Refresh repeatedly.

Delta evidence after `4f9f7e0` occurred while Wi-Fi was unavailable: selecting Yesterday preserved the prior `2026-07-19` report and correctly surfaced the 20-second timeout instead of replacing it with stale/partial data. It also confirmed that long-utterance Android pause remained unreliable and that period entry was still typing-heavy. The reporting UI now uses one mobile-native preset selector with Today, Yesterday, Last 7/30 days, This/Last week, This/Last month, Last 3/6 months, This year, Custom date and Custom range; custom choices reveal calendar inputs. All selections still resolve through the canonical backend period parser. Generic editable-card reading is now sentence/line segmented: Pause cancels only the active segment while retaining its index, Resume repeats the nearest safe sentence then continues, Stop clears the session, refresh/period changes/closing stop old speech, and controls reflect the actual state. Duplicate report taps are visibly disabled and stale requests are cancelled. With Wi-Fi restored, deploy and select `Last 7 days` from the picker, refresh once, require completion preferably within 1-3 seconds and no later than 10, then Read/Pause/Resume. Do not test exports yet.

Evidence after `75eee42` passes the period picker and Read/Pause/Resume sequence but does not pass report generation: the visible timeout message proves the selected Last 7 days/Yesterday request did not replace the retained Today report. Retaining Report Date and Generated At was truthful, but their unqualified labels made the selected period appear associated with stale content. After deployment, selection must immediately show the chosen-period title, `Showing the last successful report below`, `Displayed Report Date`, and `Last Generated At`. Tap Refresh once. A success must replace the report/range/freshness and state measured elapsed seconds; it must complete within 10 seconds. A timeout must explicitly state that 10 seconds was exceeded and preserve the last report. If timeout recurs, return the contemporaneous Replit backend log for that single request. Read/Pause/Resume is already accepted and need not be repeated unless the successful new report regresses it. Do not test exports.

The deployed presentation passed, but the 10-second request boundary failed before the valid backend response. Direct uncached production measurements were 16.7, 18.9, 15.6 and 17.1 seconds, with a separate health request taking 4.7 seconds. The successful response resolved `2026-07-13 to 2026-07-19` and used `saved_historical_sales_and_activity_records`. The live dependency path is therefore slower than the former client bound. After deployment, select Last 7 days and Refresh once. At 10 seconds the card must say it is still reading saved records and must not issue a duplicate. By 30 seconds it must either replace the retained report with the correct range, new Generated At and measured elapsed seconds, or preserve the retained report with explicit 30-second timeout guidance. Return the completed card. Do not repeat speech controls or test exports.

Functional validation after `8b638a7` passed, but the performance checkpoint did not. One Last 7 days refresh completed in 19.1 seconds and correctly replaced the retained snapshot with range `2026-07-13 to 2026-07-19`, fresh Generated At, historical-only source wording, no present-stock-as-history claim, no WhatsApp send and no duplicate save. Independent uncached production calls also measured 16.7, 18.9, 15.6 and 17.1 seconds, proving persistent latency rather than a one-time startup delay. Protect the accepted picker, stale-state, historical-data and speech behavior. Keep Export Hub blocked. Before another owner test, profile and repair the report path toward the 1–3 second target while retaining one uncached combined canonical source read and truthful failure preservation. Then issue one timed Last 7 days refresh only.

The owner nevertheless repeated the test after documentation-only `3bf0b4c`; it completed correctly but took 27.1 seconds. Record this as additional performance-failure evidence, not a pass. No report code changed in that deployment. Do not ask for another live refresh until a backend performance commit exists and direct timing demonstrates a material improvement. Extending the client timeout is not sufficient.

The backend performance repair now exists in the shared Sheets adapter. Startup performs one background combined source warmup after schema setup; report requests reuse the bounded pharmacy-isolated snapshot, identical concurrent cold requests coalesce, period changes filter locally, and successful Daily Log/Transaction writes update the snapshot before the next report. A five-minute background refresh and ten-minute TTL bound external-source freshness; overflow/warmup failure safely falls back to Sheets. Deterministic delayed-source timings were 250.6 ms cold, 0.057 ms repeat, 0.037 ms different period, 0.038 ms after write-through, and 0.042 ms for daily-log reading, with one Sheets API call. After deployment, wait until startup reports `Report source snapshot warmed`, then perform one isolated two-read Last 7 days timing sequence: record the first Refresh and one immediate second Refresh, both ranges, both Generated At values and both success messages. Do not repeat speech or begin exports.

Live deployment after `b8d738e` did not pass: no warmup-complete line appeared, then Last 7 days measured 19.8 and 26.0 seconds. The result remained truthful but proves repeated Sheets waits. The likely snapshot overflow is now directly observable and repaired: capacity is bounded at 100,000 rows, shell output must show `REPORT_SOURCE_SNAPSHOT_WARMED logs=<n> transactions=<n>`, and each report response carries safe cache readiness/row/age/hit/miss diagnostics. After deployment, do not tap Refresh until the shell line appears. Then run the same two immediate Last 7 days refreshes and return the shell line plus both timing messages. Do not repeat speech or exports.

The next evidence showed warmup succeeded with zero live rows, but Last 7 days still took 14.5 and 20.5 seconds. The shared source layer therefore passed; the delay was the report service's unconditional OpenAI recommendation call. Routine reports now use deterministic local recommendations only, with no tokens or external AI request. Local complete-report timing is 112.3 ms cold and about 0.2 ms thereafter. After deployment and the warmup line, run exactly two immediate Last 7 days refreshes and return both timing messages and Generated At values. Do not repeat speech or exports.

Passed after `342c359`: startup automatically printed `REPORT_SOURCE_SNAPSHOT_WARMED logs=0 transactions=0`. The required immediate Last 7 days refreshes completed in 0.6 and 0.3 seconds, advanced Generated At from `19/07/2026, 20:00:32` to `19/07/2026, 20:00:44`, retained the inclusive `2026-07-13 to 2026-07-19` range, used saved sales/activity records, omitted current stock as historical stock, and stated that nothing was sent to WhatsApp or saved as a duplicate. OpenAI Platform remained unchanged at 6,476 tokens, 22 requests, USD 0.31 spend and USD 3.40 credit. Reporting performance, warmup observability and zero-AI routine generation are complete and protected. Additional Yesterday evidence at 0.3 seconds is accepted as regression evidence; do not repeat reporting.

The active ordered stage is Export Hub integrity. Repository inspection shows only the previously live-tested catalog CSV download; a shared owner Export Hub and genuine Excel, PDF and Word outputs do not yet exist. Implement the smallest shared deterministic inventory/catalog export boundary before asking for live evidence. It must read canonical persisted rows, include pharmacy identity and Kenya generation time, produce safe truthful filenames, preserve CSV as machine-readable interchange, make Excel purpose-specific and readable, and use zero AI/API formatting. Add PDF and Word through the same canonical document model rather than separate copied data paths. Local focused verification must precede one owner action at a time.

The shared Export Hub is implemented. One immutable pharmacy-scoped inventory model now supplies CSV, genuine XLSX, genuine DOCX, paginated PDF, genuine PPTX and print-ready HTML. All formats share canonical values, pharmacy/branch/location identity, Africa/Nairobi generation time, safe filenames, professional green owner styling, bounded page/slide layouts and deterministic local zero-AI generation. The responsive hub presents one format per clear owner choice on narrow screens and two columns when space allows. It neither mutates catalog data nor calls a backend, external formatting service or AI API.

Focused verification passes the 35-row canonical model, cross-pharmacy isolation, CSV escaping, Office/PDF package structure, independent Excel/Word/PowerPoint/PDF readers, multi-page/multi-slide scaling, mobile UI wiring, download behavior, print CSS, zero-AI static protection, JavaScript compilation, catalog workspace, report workflow and architecture checks. First live checkpoint only: deploy, open `+` -> `Export Hub`, require the current pharmacy/branch and `35 medicines`, tap `CSV` once, and capture the in-app success message, downloaded filename and Android Downloads screen. The filename must be a safe pharmacy-name inventory filename ending in the current Kenya date and `.csv`. Do not open the CSV or test Excel/PDF/Word/Presentation/Print until this acquisition checkpoint passes.

Current CSV evidence after `32bcaef` passes deployment, Export Hub discovery, responsive mobile layout, `35 medicines`, `Your pharmacy · Main`, six format availability, and the visible local/pharmacy-isolated/canonical/zero-AI statement. It does not show a CSV action result: the status remains `None yet`, and neither the success message, filename nor Android Downloads entry appears. CSV remains incomplete. Next action is still CSV once; return one combined screenshot showing its success state and Downloads filename. Do not test Excel yet.

CSV acquisition passed on 2026-07-25. A single tap produced `File downloaded (2.53 KB)`, updated the card to `CSV downloaded for 35 medicines at 25/07/2026, 01:11:59 Africa/Nairobi`, and created one new Android Downloads spreadsheet entry beginning `your-pharmacy-inventor…`, size 2.53 KB. The local/pharmacy-isolated/canonical/zero-AI boundary remained visible and OpenAI Platform showed zero tokens and zero requests. No other format was touched and the CSV was not opened, so content inspection remains separate from acquisition. Protect this checkpoint. Next live test is Excel acquisition only: tap Excel once, capture the in-app XLSX success state and Android Downloads entry, and do not open it or test another format.

Before Excel, deploy the shared Export Hub action cleanup revealed by the CSV screenshots. Export Hub must end after its format buttons, status, assurance, Details and close controls; it must not show generic Confirm/Read/Correct/Cancel because format downloads are immediate and read-only. The fix is isolated in the shared action renderer and does not reopen CSV. During the Excel acquisition screenshot, also require that those inherited buttons are absent.

Excel acquisition passed on 2026-07-25 after `f137c10`. The generic action buttons were absent. One tap updated the hub to `XLSX downloaded for 35 medicines at 25/07/2026, 01:21:48 Africa/Nairobi`, produced a 29.49 KB browser download, and created one new 29.49 KB Android Downloads workbook above the protected 2.53 KB CSV. Pharmacy/branch/count, canonical isolation and zero-AI wording remained correct; OpenAI showed zero tokens and requests. The workbook was not opened and no other format was touched. Protect Excel acquisition.

Before PDF, deploy the remaining copy cleanup visible under the cleaned hub: replace generic `Check the details, then confirm.` with `Choose a format to download. No confirmation is required.` Then run PDF acquisition only: confirm that truthful note is visible, tap PDF once, capture its success state and Android Downloads entry, and do not open it or test Word.

PDF acquisition passed on 2026-07-25 after `840642a`. The truthful no-confirmation guidance was visible and generic actions remained absent. One tap updated the hub to `PDF downloaded for 35 medicines at 25/07/2026, 01:29:14 Africa/Nairobi`, produced a 13.63 KB browser download, and created exactly one new Android Downloads PDF above the protected XLSX and CSV. Canonical isolation and zero-AI wording remained visible; OpenAI showed zero tokens and requests. The PDF was not opened and Word was untouched. Protect PDF acquisition. Next live test is Word acquisition only: tap Word once, capture the DOCX success state and Android Downloads entry, and do not open it or test Presentation.

Word acquisition passed on 2026-07-25. One tap updated the hub to `DOCX downloaded for 35 medicines at 25/07/2026, 01:34:13 Africa/Nairobi`, produced a 59.65 KB browser download, and created exactly one new Android Downloads Word document above the protected PDF, XLSX and CSV. The no-confirmation, canonical-isolation and zero-AI boundaries remained correct; OpenAI showed zero tokens and requests. The DOCX was not opened and Presentation was untouched. Protect Word acquisition. Next live test is Presentation acquisition only: tap Presentation once, capture the PPTX success state and Android Downloads entry, and do not open it or test Print.

Presentation acquisition passed on 2026-07-25. One tap updated the hub to `PPTX downloaded for 35 medicines at 25/07/2026, 01:38:17 Africa/Nairobi`, produced a 220.07 KB browser download, and created exactly one new 220 KB Android Downloads presentation above the protected DOCX, PDF, XLSX and CSV. Canonical isolation and zero-AI behavior remained correct; OpenAI showed zero tokens and requests. The PPTX was not opened and Print was untouched. Protect Presentation acquisition. Next live test is Print-view acquisition only: tap Print once, require a new print-ready inventory tab/view with pharmacy identity, Kenya generation time, table header and first canonical medicine rows, and do not tap its `Print inventory` button yet.

Print-view acquisition failed on 2026-07-25 because the 12-column table opened as unreadable miniature desktop content on mobile and the tab retained `about:blank`. The shared repair adds the required mobile viewport, an owner-readable card per medicine with every field explicitly labelled, visible pharmacy identity and Kenya generation time, a canonical/isolated/zero-AI summary, sticky Print and Close controls, and a named local Blob preview. Print media independently restores the professional A4-landscape repeating-header table. Focused verification protects all six formats, canonical equality, pharmacy isolation and zero-AI behavior. After deployment repeat only Print-view acquisition: tap Print once; confirm a readable titled preview, pharmacy identity/time, summary, first two labelled medicine cards and Print/Close controls; do not tap Print inventory.

The `d37cd31` repeat passes readability and complete first-to-last record presence. A remaining long-scroll friction is repaired before closure: mobile review now defaults to compact medicine summaries with essential form/unit, stock and price facts, tap-to-expand complete canonical fields, and local search by name/supplier/barcode/shelf. The first medicine starts expanded for discoverability. Print media hides the review controls/cards and restores the complete landscape table. Next test only: after deployment tap Print once; confirm compact medicine summaries, the first expanded record and search; search `Paracetamol`, confirm exactly one matching summary, expand it and verify its canonical fields; clear search; do not tap Print inventory.

The `6600418` evidence passes the compact list, first expanded record, complete first-to-last catalog, typed Paracetamol one-result match, correct expanded canonical fields and clear-to-35 behavior. Full Print remains open because the attached authoritative rule requires typing-last shared finding first. One shared indexed finder now serves Catalog and Print; Print delegates Scan and Speak to the existing scanner/voice roots, offers only compact truthful Low stock, Out of stock, Expiring soon and A-Z access, and retains typing as fallback across canonical name, aliases/misspellings, strength, form, sale unit, barcode, supplier, shelf and batch. Search/filter state affects screen cards only; printing remains the complete model.

Next live test only: open Export Hub -> Print; confirm summaries and first expanded record; use Scan barcode once on a known saved medicine and confirm one correct local result; clear to 35; use Speak medicine once for a known medicine and confirm the correct local result; clear to 35; type `Paracetamol`, require exactly one correct expandable result, then clear to 35. Do not tap Print inventory. If scanner or browser voice is unavailable, capture the truthful unavailable/permission state rather than substituting another route.

Live evidence after `c637d52` fails this checkpoint: the empty `All medicines` state displayed `0 of 35`, and Scan barcode and Speak medicine did not open their shared capture flows; typed `Par` still found exactly one Paracetamol. The repair separates empty-query scoring from non-empty match thresholds and replaces the fragile Blob-preview-only opener dependency with an authenticated per-preview browser channel plus guarded fallback. Requests still enter the proven shared barcode camera and voice capture roots, results still match only the active Pharmacy Catalog, and clear/reset restores the complete screen model. Permission and unavailable states now return actionable preview guidance. Local Export Hub, catalog, barcode, voice, consistency, architecture, duplicate-safety, pharmacy-isolation and zero-AI checks pass. Do not mark live validation passed. Repeat the same Print Finder test only after deployment; do not tap Print inventory.

Follow-up evidence after `db1709c` passes `35 of 35`, `All medicines`, readable list and canonical Paracetamol inspection. Voice incorrectly required manual settings before any prompt and then hung at startup; scanner hung before permission/UI. Root repair removes cross-tab user-activation loss by hosting Print review inside the same Main App context. First Speak tap now invokes real microphone `getUserMedia`, then the existing Web Speech root with bounded requesting/listening/processing/result/error/cleanup states. First Scan tap invokes the existing camera root directly, keeps its real overlay visible above Print, and returns captured local matches or bounded denial/unavailable/no-match/cancel states. Use the existing canonical Losartan record with barcode `6161109876546`; display `/main-app/fixtures/barcode-losartan-50mg.png` on another screen. No medicine is created or edited. Repeat this one checkpoint only and do not tap Print inventory.

Evidence after `f8fe088` passes the functional voice route through native permission, Listening and local canonical Paracetamol match. It also passes real shared scanner opening, but the first fixture presentation was too small and no barcode was read. Voice status changes visibly blanked/rebuilt the Print surface between states. The final repair keeps the existing iframe stable during voice status/query updates and provides a full-screen responsive Losartan barcode at `/main-app/fixtures/barcode-losartan-50mg-live.html` with a 3000×1600 PNG fallback. Next test only: speak Paracetamol once and confirm no blank flash plus the correct match; clear to 35; display the full-screen live barcode on another screen, scan once and require existing Losartan; clear to 35. Typing already passes and must not be repeated. Do not tap Print inventory.

## Ordered approved improvement 1 - Supplier ordering and truthful fulfilment

Dependency position: after Export Hub format integrity, inside the restocking, supplier, order-list and inventory-intelligence stage. Document/send routes reuse the verified Export Hub root. Implement one shared deterministic Supplier Order Generator with a maximum-three-step owner path: request by voice/text, edit one order card, Send Order. It must support saved reorder-level triggers, owner-requested lines, supplier/category/manual selection and low-stock suggestions using only canonical stock, confirmed reorder levels, pack conversions, supplier assignment, deterministic velocity/lead time and owner preferences. Reorder setup is show labeled suggestion -> accept/edit/skip -> save; missing levels remain `Reorder level not set` with quick setup and no invented quantity. Preserve below/at/above/missing states and auditable level changes.

The editable order card must expose supplier, medicine, form/unit, stock, reorder level, suggested/requested quantity, authoritative conversion, supported estimated cost, notes, unique reference and delivery status, distinguishing calculated/suggested/confirmed/unknown values. Sending must cover supported WhatsApp, email, PDF, print, share sheet and later direct routes without forcing supplier installation or implying endorsement. Prevent duplicates. Statuses Draft, Order Sent, Supplier Viewed only when verifiable, Supplier Confirmed, Partially Confirmed, Rejected, Dispatched, Delivered, Delayed and Cancelled require authoritative evidence; expected delivery remains Unknown/Awaiting supplier confirmation until sourced.

Ordered live checkpoints, one at a time: create a reorder level; accept suggestion; edit suggestion; skip suggestion; missing-level order safety; low-stock order; owner-requested order; supplier-specific order; pack conversion; edit review; supplier grouping; each supported send route; verifiable receipt; supplier confirmation; partial availability; authoritative expected delivery; delay update; dispatch; delivery; duplicate protection; history; export/print; three-step usability; pharmacy isolation; zero-unjustified-LLM behavior. Fix shared roots and continue automatically.

## Ordered approved improvement 2 - Exact form/unit sales and complete pack data

Dependency position: later active-sales, shared editable-card and cross-input consistency stages, with catalog/onboarding capturing exact forms, units, unit prices, conversions and pack-photo data first. Do not repeat closed unrelated tests. The first Fast Action card must visibly prioritize medicine, exact form/unit, quantity, exact unit-specific selling price, payment and Confirm/Correct/Cancel, retain a persistent concise sale summary, large tap targets and minimal scrolling, and move secondary stock/strength/cost/expiry/supplier/barcode/batch/alias/notes details later. One unit's price or conversion may never leak to another unit or strength; ambiguity requires one simple choice; missing price/conversion remains Unknown/confirmation required; unsafe mismatches are blocked.

Implement once across typed, voice, barcode, camera, pack photo, file, catalog, quick add, onboarding, duplicates, corrections, undo, offline, ledger, stock, reports, history and exports. Pack-photo processing follows local recognition -> Pharmacy Catalog -> Source Brain -> OCR -> cache -> approved AI fallback only, extracting every visibly supported brand/generic/strength/form/unit/pack/quantity/barcode/batch/expiry/manufacturer/distributor/registration/printed-price field and labeling image/catalog/suggested/confirmed/unknown provenance without invention or duplicate creation.

Ordered focused live checkpoints, one at a time: typed known-unit sale; voice equivalent; multiple units; unit-specific prices; ambiguous unit; wrong unit-price; missing conversion; box-strip and strip-tablet conversion; supported liquid handling; barcode; camera; pack photo; file; catalog; quick add; duplicate detection; photo completeness; unreadable fields unknown; exact stock/ledger/report/history; correction; undo; offline; shared-card regression; three-step/rush-hour clarity; optional deterministic read-back; zero-unjustified-LLM protection.

## Ordered approved improvement 3 - Export IP, privacy and compliance safeguards

Dependency position: apply shared-root technical safeguards throughout the remaining current Export Hub formats before production-ready closure, with unresolved professional matters retained as pre-launch gates. Preserve the approved clean MS2.0 direction. Use only original or rights-verified layouts, wording, icons, fonts, templates and assets; do not copy proprietary trade dress or use third-party logos/marks without recorded permission or imply endorsement.

Create a machine-readable production asset/dependency registry recording name, source, version, licence, commercial/modification/redistribution rights, attribution/notices, approved use, proof, review status and owner. Unknown or incompatible production assets fail closed, with automated export-path checks and correct distribution notices. Every export route must enforce pharmacy/branch isolation, minimum necessary fields, role/access restrictions, secure download/sharing, retention/deletion, audit, redaction/anonymization, safe fixtures and controlled IDs. Where appropriate include pharmacy, branch, Kenya time, document ID, dataset/version, `Generated by MS2.0`, period/source status and authoritative/calculated/suggested/estimated/awaiting labels. Never claim regulator, medical, legal, supplier, bank or payment-provider approval without evidence.

Continue one case at a time: CSV; Excel; PDF; Word; Presentation; Print; original consistency; cross-format canonical data; isolation; zero AI; metadata/document ID; provenance wording; unauthorized-logo/trade-dress absence; registered licences/notices; anonymized demo output; secure sharing/access; retention/deletion/audit; no false endorsement; controlled unregistered asset fail-closed; controlled incompatible licence blocked; approved fallback; regression. Pre-launch checklist must retain professional review for software/contributor IP, OSS/copyright, KIPI trademark clearance, ODPC/privacy and health data, Pharmacy and Poisons Board matters, supplier communications, payments, terms/notices/DPAs, security/breach and export retention. Do not claim legal compliance from code review alone.

## Print Finder Result — 2026-07-25

Passed after `f88fa99`. Mobile evidence confirms the blank voice flash is gone, spoken Paracetamol resolves exactly one saved record, the committed EAN-13 `6161109876546` scans through the real camera and resolves exactly one saved Losartan record with complete canonical details, and clearing restores `35 of 35`. No catalog mutation, duplicate or AI/API use occurred. Protect typing, voice and barcode finding. The next isolated checkpoint is `Print inventory`: tap it once, inspect the native device print preview/dialog, and do not confirm a physical print unless explicitly requested. The preview must contain the complete 35-record landscape table regardless of the current screen finder state.

Passed — native Android Print inventory. The action opened the system preview, native landscape selection regenerated two selected pages, the first page retained the inventory identity and main table, and the second retained the remaining medicine rows. No printer was selected and no physical print or PDF save occurred. Protect Print view, Finder and native acquisition. Advance to original/cross-format canonical consistency and integrity verification; do not repeat format downloads or print acquisition without regression evidence.

## Export Hub Final Integrity Retest

Shared-root implementation and automated verification now pass over one controlled 35-record snapshot. Fresh filenames include an exact generation timestamp. CSV/XLSX retain the complete ordered 12-field table; PDF is five balanced seven-record pages; DOCX is seven five-record landscape pages; PPTX is one title plus seven readable five-record slides; Print is four balanced 9/9/9/8-record landscape sheets. Every format retains all 35 unique medicines and all canonical fields, package structures are valid, XLSX/PDF/PPTX visual renders are unclipped, DOCX structural page flow is valid, Print headings/identity/traceability repeat, and no routine AI/API route exists.

Keep Export Hub open for one final owner confirmation after deployment. Generate one fresh file of each format from the same unchanged 35-record catalog, then open CSV, Excel, PDF, Word and Presentation once and inspect the updated Print preview once. Confirm readable content and the new timestamped filenames; report only a format that fails to open, clips, loses a record/field or looks unreadable. Do not approve, edit, print, share or upload any output, and do not repeat Finder or earlier acquisition evidence. Close Export Hub only after this concise visual pass.

Excel owner viewing is the active isolated checkpoint and is not yet passed. The first workbook opened correctly and preserved all data, but its single wide table required tiring horizontal scrolling and did not provide an owner-first operational view. After deploying the five-sheet shared XLSX repair, download Excel once and inspect only these tabs: `Inventory Overview`, `Full Inventory`, `Low Stock`, `Expiry Tracking`, and `Suppliers`. Require a calm readable overview, preserved 35-row Full Inventory, visible headers and medicine/primary column while scrolling, clean supplier wrapping, banded rows, compact purpose-specific columns, correct low-stock classification from saved reorder levels, sorted expiry tracking, deterministic supplier totals, and no clipping or formula error. Do not edit, print, share, upload or repeat CSV. Advance automatically to the PDF live-test only after this Excel evidence passes; otherwise stop on the first new Excel defect.

The 2026-07-26 owner workbook evidence failed because the wide overview could pair frozen labels with unrelated scrolled KPI values, visibly implying contradictory medicine totals. After deploying the fail-closed snapshot reconciliation repair, repeat Excel only with one newly generated workbook. Require:

1. Inventory Overview shows four stacked, unambiguous KPIs: Total medicines = 35, Total stock value from the same snapshot, Low stock count, and Expiring soon count.
2. Attention Required contains only Medicine, Stock, Expiry and Reason.
3. Full Inventory contains all 35 unique medicines and all 12 unchanged canonical fields.
4. Low Stock contains only Medicine, Stock, Reorder level, Expiry and Reason and agrees with the overview count.
5. Expiry Tracking contains all 35 medicines once, ordered with recorded expiries first, using only Medicine, Expiry, Batch and Stock.
6. Suppliers contains all 35 medicines once using only Supplier, Medicine, Stock and Shelf.
7. Headers stay visible, the primary column remains visible where applicable, long values wrap, and no phone scroll can visually pair one KPI label with another KPI's value.

Send fresh screenshots of the overview, tab list, Full Inventory after vertical and horizontal scrolling, Low Stock, Expiry Tracking and Suppliers. Do not begin PDF unless every Excel condition passes.

Final Excel presentation retest after the pane-free repair:

1. Pull the latest commit and download one newly generated workbook.
2. Confirm Overview opens as one natural page with no frozen column or split-screen effect; all four KPI labels and values, complete generated metadata, Attention Required headings and empty/message rows remain visible without horizontal movement.
3. Confirm Full Inventory has 35 medicines in the owner-priority order: Medicine, Strength, Form, Unit, Stock, Selling price, Cost price, Expiry, Supplier, Shelf, Batch, Barcode. Scroll normally in both directions; no medicine column stays pinned and no heading/value is clipped.
4. Confirm Low Stock, Expiry Tracking and Suppliers scroll normally with no frozen columns or split panes, have filters and compact purposeful columns, and show full-width plain guidance when empty.
5. Confirm calm typography, wrapping, banding, number formatting and readable widths on phone and desktop.

Return screenshots of Overview, the five-tab list, Full Inventory at the top and after horizontal/vertical movement, Low Stock, Expiry Tracking and Suppliers. If every condition passes, mark Excel Owner Workbook passed and advance automatically to the PDF owner-copy live validation. If any condition fails, stop on Excel and repair only the observed shared XLSX presentation defect.

## Final Excel worksheet-identity retest

Use one newly generated workbook only. The Android viewer's `1/5` page indicator is not sufficient proof of navigation.

1. Open the workbook's sheet/tab selector and verify exactly: `Overview`, `Full Inventory`, `Low Stock`, `Expiry Tracking`, `Suppliers`.
2. Open each named tab directly and verify A1 reads respectively: `Pharmacy Overview`, `Full Inventory`, `Low Stock`, `Expiry Tracking`, `Suppliers`.
3. Confirm Overview contains Workbook contents, the seven owner metrics and Attention required, entirely within columns A–D.
4. Confirm Full Inventory contains 35 medicine rows and its 13 defined working columns through Retail stock value, Batch and Barcode.
5. Confirm Low Stock shows its six-column reorder table or the exact healthy empty message; Expiry Tracking shows 35 rows and seven expiry/action columns; Suppliers shows 35 rows and five supplier/medicine columns.
6. Confirm selecting any working tab never shows Overview content, a wide blank canvas, a frozen column, a split pane, or a second printable page created by empty cells.
7. Do not edit, print, share or upload. If all checks pass, mark Excel Owner Workbook passed and proceed automatically to PDF. Otherwise stop at the first exact tab/content mismatch and keep PDF blocked.

## Excel internal-link compatibility retest

After pulling and restarting the latest build, download one completely fresh workbook:

1. Open the workbook.
2. Tap `Full Inventory` on Overview and confirm the `Full Inventory` worksheet opens at its title.
3. Use the visible strip to tap `Low Stock`, `Expiry Tracking`, and `Suppliers`; confirm each opens the correctly titled worksheet.
4. Tap `← Back to Overview` and confirm it returns to `Pharmacy Overview`.
5. Confirm Full Inventory still contains all 35 medicines.

Do not discover or use the viewer's `1/5` page controls for this checkpoint. Do not edit, print, share or upload. If the standard internal links work, pass Excel and proceed automatically to PDF. If taps do nothing or the viewer remains on Overview, record that exact viewer compatibility limitation, preserve the desktop-compatible Excel workbook, and proceed to PDF as the phone-first owner copy without another broad XLSX redesign.

## PDF Owner Copy live validation

Excel is passed with the third-party viewer limitation documented. Do not redesign or repeat Excel.

After pulling and restarting the latest build, open Export Hub and download one fresh PDF. Open it in the phone's PDF reader and confirm only:

1. Page 1 shows the complete Pharmacy Overview and all summary values without sideways scrolling.
2. Page 2 shows five clear medicine cards with readable stock, prices, supplier and traceability details.
3. The final page shows Medicines 31–35 and nothing is clipped.

Do not edit, print, share or upload the file. If these three views are clear, mark PDF Owner Copy passed and continue automatically to Word. If one view fails, report that page and the exact clipped, missing or unreadable item.

Passed from authoritative Android screenshots. PDF opened as eight portrait pages, required no sideways scrolling, showed the reconciled Overview, retained five intact medicine cards per inventory page and ended with medicines 31–35. Focused empty-value/footer polish is automated and visually verified locally; do not repeat PDF without regression evidence.

## Word Owner Document live validation

Choose Word when the owner wants an editable document for notes, corrections or review. Use Excel for inventory analysis, PDF for easiest phone reading and sharing, and CSV only for system data transfer.

After pulling and restarting the latest build, open Export Hub and download one fresh Word file. Open it in Microsoft Word or Google Docs and confirm only:

1. Page 1 is portrait, comfortably readable without excessive zoom, shows the reconciled owner summary and provides a large general notes/corrections area.
2. Page 2 shows four clearly separated medicine cards. Confirm medicine name, stock and prices are prominent; supplier/traceability are secondary; each card has editable owner notes/corrections lines.
3. Scroll to page 10 and confirm medicines 33-35 are present with no clipping. Tap once in a notes area and confirm the document is editable, but do not save or change pharmacy data.

If those three checks pass, mark Word Owner Document passed and continue automatically to Presentation. Report only a file-open failure, missing medicine, clipping, broken page flow or inability to edit.

Passed from authoritative owner-device screenshots after Replit pulled `5567f92`. The fresh DOCX is ten portrait pages: one readable owner overview and nine review pages with four intact medicine cards per full page, all 35 medicines, and medicines 33–35 on page 10. Focused final polish makes missing stock a smaller `Stock not recorded` label, preserves numeric zero, and adds `Add note or correction here` with restrained writing lines to every card. Microsoft Word rendered the exact production DOCX as ten pages. A typed-note save/reopen round-trip preserved every medicine exactly once and confirmed ordinary editable OOXML with no document protection, macros or flattened pages. Word Owner Copy is passed and protected.

Final owner-device evidence after `c561003` confirms the protected polish in the fresh 104.43 KB download across all ten pages: missing stock is calm, real stock remains prominent, note prompts and working areas are visible, all 35 medicines remain present, and no card is clipped or broken. Word Owner Copy is permanently passed. Do not repeat it without genuine regression evidence.

Permanent gate for every current or future Export Hub format: first state why a pharmacy owner deliberately chooses it instead of every alternative. The shared format registry must carry a unique operational purpose and direct owner-facing explanation. Do not approve duplicate-purpose formats. Preserve the common immutable snapshot, deterministic generation, pharmacy isolation, zero-AI formatting, maintainability and provenance/legal safeguards while designing each renderer for its distinct workflow.

## Presentation Owner Briefing live validation

Choose Presentation when the pharmacy owner needs to brief staff, partners or suppliers on a large screen. Use Word for editable notes and Excel for inventory analysis.

After pulling and restarting the latest build, open Export Hub and download one completely fresh Presentation:

1. Open the PPTX in Microsoft PowerPoint, Google Slides or another presentation application.
2. Confirm slide 1 is a clear `Pharmacy inventory briefing` title with the correct pharmacy identity.
3. Confirm slide 2 is a readable Inventory overview with the reconciled totals.
4. Confirm slide 3 shows medicines 1–5 with medicine names, stock and prices easy to scan and supplier/traceability secondary.
5. Confirm slide 9 shows medicines 31–35, with no missing row, overlap or clipping.

Do not edit, present, print, share or upload the deck. If these four views are clear, mark Presentation Owner Briefing passed and advance to the next repository-defined checkpoint. Report only an open failure, wrong pharmacy identity, missing medicine/value, unreadable text, overlap or clipping.

### Corrective retest — pending

The prior generic ad-supported Android Office app is not a compatibility authority; it returned error (4) for a PPTX that opens in Microsoft PowerPoint. Presentation Owner Briefing remains **PENDING / NOT PASSED**.

1. Pull and restart the protected commit.
2. Open Export Hub and download Presentation.
3. Confirm the main sales chat shows one updated Export Hub card rather than a new export message.
4. Expand Export history and confirm the newest PPTX record shows pharmacy, filename, time, count, purpose, opening guidance and `completed`.
5. Open the file in Microsoft PowerPoint or another standards-compatible presentation application.
6. Confirm nine slides: title, baseline overview, inventory position, value summary, low stock, expiry, suppliers, owner actions and closing decisions.
7. Confirm no clipping, blank slide, broken text, invented claim or medicine-by-medicine dump.

Pass only after owner-device evidence shows the file opens in a compatible presentation app and the one-card/history behavior is correct.
