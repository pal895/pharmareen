# Current MS2.0 live validation state

## Preserved state

- Repository baseline before the shared-row fix: `937cc3f` on `main`, already pushed but not pulled into Replit.
- Replit is live on `1dff3b2`; its current UI does not prove the expiry, notification-pruning, bottom-search, or shared-row fixes.
- Current stage: finish CSV onboarding validation. The Notifications test is paused except for confirming removal of the four known false expiry alerts after deployment.

## Completed and protected live behavior

- Two invoice onboarding fixtures passed review, correction, approval, persistence, and export; invoice row ordering is protected.
- Clean bulk-paste onboarding passed and must not be repeated without regression evidence.
- CSV imported four medicines and increased the saved catalog from 21 to 25 without duplication. Strength, quantity, prices, supplier, batch, and optional blank barcode reached the catalog and Medicine Action Card.
- `SHOW ME`, complete catalog browsing, strict multi-term search, filtered `Open & edit`, draft-safe Medicine Action Cards, basic Cefixime sale, and basic Cefixime restock are live-approved.

## Current unresolved validation

- Deploy and live-confirm canonical month expiry handling removes the four false alerts produced from values such as `Oct-28`.
- Confirm the synchronized bottom catalog search added at `937cc3f`.
- Confirm shared row movement appears in a safe CSV or bulk-paste review and moves one intact row. Do not approve prepared existing data or create duplicates during this check.
- Live evidence after `6476f7c` verified false expiry alerts were removed and the synchronized bottom catalog search appeared. File and Paste List quick actions then exposed a shared interaction-lifecycle failure before a review could open.
- Live evidence after `60b2014` showed four import-approval alerts: repeated Paste List taps created empty drafts but did not navigate to the new card, making Operations appear hung while Notifications remained available. Empty repeated drafts now consolidate safely and every opened card is focused immediately.
- Live evidence after `b011b6b` showed the retained blank draft still blocked Operations after its notification was dismissed. Resume now discards every truly empty Paste input draft and isolates any unreadable non-empty card so operational workspaces cannot be locked by one draft.
- Live evidence after `481835d` verified MS2.0 Assistant and SHOW ME open again. Two valid import reviews reached isolation cards because of a renderer defect, and the bottom close label wrapped poorly; unreadable raw drafts now move to bounded local quarantine on resume and every shared bottom close control displays only `x`.
- Live evidence after `91a8d7e` verified the File picker opens, but selecting the Test 4 CSV produced an isolation card. Exact reproduction found a stale `incompleteInvoice` action-template reference left behind by the capability migration; completed CSV/Paste reviews now consume `correctionAllowed` from the shared policy and have full render regression coverage.

## Shared-root conclusions and drift

- Medicine identity fields and persistence converge through the canonical medicine field schema; strength and barcode are not CSV-only.
- Multi-row review movement was generic in persistence but its UI was incorrectly gated by invoice mode. The shared CatalogImport review policy now owns reorder, add-row, editing, approval, and correction capabilities.
- All `data-action` controls now delegate through one stable application-root lifecycle. Every card inherits the same safe close action at both the top and bottom so long editable cards do not require a full upward scroll.
- Safe invoice, CSV, bulk-paste, and future compatible multi-row CatalogImport reviews inherit ordering. Incomplete invoices intentionally hide ordering and add-row controls until safe; single-medicine cards exclude ordering.
- Context parsers may differ, but supported fields must converge before editable review. Excel parsing and genuine barcode decoding remain future stages, not part of this fix.

## Remaining live-test sequence

1. Finish the combined CSV-stage validation: false alerts removed, bottom search present, and one shared row move works without approval.
2. Validate Excel onboarding only after its adapter is ready.
3. Cover remaining non-clean paste variants, then manual creation and sale-time learning.
4. Validate barcode/shelf/photo onboarding, then broader Medicine Action Card cases.
5. Run Mic Test 2 before broader sales and restocking coverage.
6. Validate reports/export integrity, then the full Notifications stage once catalog dates are trustworthy.
7. Continue to Digital Operations Assistant and Operational Intelligence.

Do not repeat the two passed invoice fixtures, clean paste fixture, filtered catalog action, strict Zinc search, basic Cefixime sale, or basic Cefixime restock unless new regression evidence appears.

## Permanent reusable-behavior rule

Whenever an editable-medicine behavior is reusable, implement it once in the shared editable-card or editable-list capability and make every applicable workflow inherit it. Preserve one canonical implementation and focused regression protection. Permit an exception only when a context-specific safety or workflow reason is documented and tested; never duplicate shared behavior screen by screen.

## Next action

After this shared-row commit is pushed, pull/restart Replit once and perform only the combined paused-stage validation described above. Do not advance to Excel onboarding from that test.
