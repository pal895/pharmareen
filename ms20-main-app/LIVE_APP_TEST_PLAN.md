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
