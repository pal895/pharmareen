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
- Live evidence after `e4da9fa` verified the four-row CSV review renders and shared row movement preserves complete rows. A clean Paste List containing four already-saved medicines correctly created no duplicates, but its result was hidden in collapsed diagnostics; the shared CatalogImport note now exposes safe no-op review outcomes and the paste editor uses an owner-facing, full-width medicine-list field.
- Live evidence after `0eaa499` verified all-existing feedback and the improved paste editor. A mixed Paste List then correctly excluded saved Amitriptyline and reviewed only new Quinine Sulfate; the shared visible feedback now also explains this mixed partition instead of leaving the omitted existing row unexplained.
- Live evidence after `904c501` closed the mixed draft without saving, then the unknown-medicine sale command `Quinine Sulfate 1 cash` correctly opened a Medicine Match / sale-time learning review. Its shared renderer exposed every field as one long phone form and labeled both sale quantity and current stock as `Quantity`; shared single-medicine reviews now use three-slide progressive disclosure and distinct canonical labels. The Quinine draft remains unapproved.
- Live evidence after `d6027d6` verified all three compact panels and their navigation. The remaining raw `message` label and mobile textarea resize artifact are normalized at the shared field/style boundary; the Quinine draft remains unapproved.
- Live evidence after `3de02cb` verified local EAN-13 capture of the controlled Losartan fixture, Source Brain-gated recognition, a complete unsaved review, explicit approval, catalog growth from 25 to 26, and persistence after refresh. The saved record retained name, strength, form, unit, stock, prices, supplier, barcode, and expiry, but lost `LOS-50T`: shared review records exposed top-level `batch`/`expiry` while Pharmacy Brain normalization only retained a prebuilt `batches[]` array. Canonical normalization now promotes those reviewed traceability fields into `batches[]` for barcode, photo, manual, and other shared review approvals.
- Live evidence after `0e232c5` verified deployment and repeated Losartan recognition without creating a 27th medicine, but the repeat review displayed blank Quantity even though the saved catalog held stock 40. The repeat path read flat fixture-shaped fields directly from a canonical saved record, and sparse upserts could replace durable values with empty strings. Barcode matches now enter the shared canonical review normalizer, and shared catalog merging preserves meaningful saved stock, commercial, location, and traceability values when an incoming review is sparse.
- Live evidence after `e158ec9` verified the complete repeated Losartan review retained stock 40, buying price 15, selling price 25, supplier, packaging, barcode, batch `LOS-50T`, and expiry `2029-06`; the unapproved review left the Pharmacy Catalog at 26 medicines. The next isolated Source Brain fixture is Loperamide 2 mg capsule, EAN-13 `6161109876553`, prepared for new-medicine barcode coverage without overlapping the known live catalog.
- Live evidence after `0d7ce83` verified Loperamide recognition, approval, refresh persistence, and repeat-scan consistency across all trusted fields; cancellation left the catalog duplicate-safe at 27 medicines. The next prepared barcode fixture is valid EAN-13 `6161109876560` with intentionally no registry mapping, for verifying an honest unsaved unknown-barcode fallback without invented medicine data.
- Live evidence after `0ba0aaa` verified the unregistered EAN-13 decoded locally with only its barcode populated and no invented medicine data. The shared card still displayed generic confirmation guidance and an active Confirm button while medicine identity was blank. All progressive medicine reviews now inherit one identity-readiness gate in visible guidance, button state, and the confirmation action boundary.
- Live evidence after `0874b68` verified the unregistered barcode's clear missing-match message, disabled Confirm action, safe cancellation, and unchanged 27-item catalog. Barcode coverage is complete. The next prepared fixture is a realistic controlled B2 shelf photo containing Prednisolone and Septrin; its isolated filename mapping is Source Brain-gated and converges into the shared two-row catalog review without saving before approval.
- Live evidence after `53cea3a` verified the Shelf photo acquisition route and its safe unmatched fallback: the Android photo picker changed the selected fixture's filename, so the filename-only controlled-fixture boundary produced a blank, disabled review and saved nothing. Controlled shelf fixtures now carry a verified SHA-256 identity and photo-library/camera acquisition retains the actual File for content hashing; filename remains a fast path, unknown content still follows the safe normal review pipeline, and Source Brain/readiness gates remain mandatory.
- Live evidence after `a72ce33` showed Google Photos also re-encoded the selected image, changing its exact SHA-256 bytes; the review again stayed blank, disabled, and unsaved. Controlled fixture identity now adds a bounded visual fingerprint plus aspect-ratio check after the filename and exact-hash paths, tolerating harmless image encoding changes without turning on general shelf recognition or weakening the unknown-image safety boundary.

## Shared-root conclusions and drift

- Permanent trusted-result rule: every approved result is a baseline. Later workflows and UX improvements must preserve its meaningful canonical facts unless the owner explicitly changes them. Empty, absent, placeholder, or failed-extraction values never erase trusted catalog data. Apply the checklist and fast `npm run verify:consistency` gate documented in `trusted-result-consistency.md` before every relevant commit.

- Medicine identity fields and persistence converge through the canonical medicine field schema; strength and barcode are not CSV-only.
- Reviewed batch and expiry values must converge into canonical `batches[]` during Pharmacy Brain normalization even when the originating shared card supplies flat fields.
- Every saved-catalog record reopened in a review must pass through canonical field normalization; never manually read only one storage shape. Sparse approvals must not erase durable pharmacy values, while explicit catalog edits remain the owner-controlled way to clear or replace them.
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

Pull/restart Replit once and select the same controlled B2 image through `+` -> `Shelf photo`. Do not approve it. Verify one unsaved two-row review appears for Prednisolone and Septrin with the prepared stock, price, supplier, batch, expiry, and shelf values, while the saved catalog remains at 27 medicines.
