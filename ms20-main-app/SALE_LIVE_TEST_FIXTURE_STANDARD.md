# MS2.0 Sale Live-Test Fixture Standard

Authority: `../MS2.0_MASTER_LIVE_TEST_SEQUENCE.md` and `../docs/engineering-memory/launch-readiness-roadmap.md`.

This standard applies before every owner test involving a sale, payment, stock reduction/preservation, refund, cancellation, offline sale, synchronization, report, multiuser attribution, loyalty reward or Demo Mode sale.

## Mandatory preflight

Codex must inspect the selected live catalog record before giving owner steps. `src/services/saleTestFixture.js` is the deterministic readiness boundary and `fixtures/launch-sale-test-medicines.json` is the reusable reference manifest.

Verify, where relevant:

- canonical medicine name and stable catalog identity;
- numeric Current stock and sufficient test quantity;
- exact form, selling unit and selling price for that unit;
- buying price when profit/cost is tested;
- barcode for scanning;
- reorder level for stock intelligence;
- expiry/batch for expiry or batch behavior;
- no unresolved duplicate record or conflicting alias.

Never select a medicine merely because it exists. Never let the owner discover a missing prerequisite mid-test. A failed preflight blocks the actual test until one clear fixture setup is completed.

## Reusable launch fixture

`launch-sale-septrin-bottle` is the first reusable reference:

- Septrin; stable ID `septrin`;
- suspension sold by bottle;
- reference stock 12; minimum test quantity 1;
- selling price KES 180; buying price KES 120;
- batch `SEP-100S`; expiry `2028-09`.

These reference values come from controlled fixture data and MS2-LT-054 owner evidence. They are not permission to overwrite live pharmacy data. Before each test, verify the live record still matches the scenario and capture its actual before-state. If a prior test changed stock or another required value, reconcile it explicitly and safely; never silently reset genuine pharmacy data.

Septrin is not approved for barcode or reorder-intelligence tests until those missing values are supplied and verified. Use an appropriate verified fixture such as the controlled Losartan barcode record where the scenario requires it.

## Before/after evidence

When stock changes or preservation are under test:

1. Capture a visible numeric before-stock screenshot.
2. Record medicine ID/name, quantity, form, unit, unit price and expected total.
3. Run only the named transition.
4. Capture the final payment/sync state.
5. Capture a visible numeric after-stock screenshot and compare it with the declared expected consequence.

Blank stock is never evidence of stock preservation. The preliminary Zinc MS2-LT-054 run remains supporting payment-flow evidence; Septrin `12 → 12` is the authoritative stock assertion.

## Authoritative sale-card rule

All test routes must use the production shared-root `SaleCard`, shared medicine matcher, shared voice capture, editable-card renderer, Transaction Completion Engine and normal queue/sync boundaries. Do not create or use a simplified test-only sale card.

The flow must show or preserve canonical medicine, quantity, payment, form/unit, exact unit price, expected total, stock/payment consequence, and Waiting/Paid/Failed/Cancelled state. Review flows preserve Confirm, Correct, Read and Cancel plus protected voice viewport/focus behavior. Multiuser and offline tests additionally preserve staff attribution and local/sync state.

The shared Production Sales Card must visibly prove exact form, selling unit, unit price, total and stock consequence before any fixture is eligible. Unit-specific price and conversion maps belong to the canonical catalog record. Missing or ambiguous values are `Unknown`/explicit-choice blockers, never inferred defaults. The card upgrade awaits owner live approval; no milestone fixture may run until that approval.

Production Sales Card recovery tests must additionally prove that payment and quantity tokens are excluded from medicine identity for spaced, compact and voice commands; that the selected live fixture hydrates all existing catalog facts; and that absent optional supplier/barcode/alias/notes values remain truthful blanks without blocking a safe sale.

## Permanent friction capture

Observe the entire shared sale flow whenever another test naturally passes through it. Record unrelated friction immediately. Fix a launch-blocking shared-root cause before it spreads, add regression coverage, preserve valid evidence already collected and avoid repeating proven portions unnecessarily. Friction does not silently disappear merely because another checkpoint supplied the route.
# Compact Production Sales Card presentation

Every sale fixture must exercise the single shared Production Sales Card. The default fixture view must keep approval facts and actions visible with minimal scrolling; complete stock/detail and traceability facts remain on-demand. Full inputs and their Catalog-shared contextual microphones appear only after Correct. A fixture-specific or permanently expanded Sale card is invalid.

Fixture execution must also retain one continuous viewport across repeated quantity/payment controls, all tabs, speech controls, Correct, at least two contextual field microphones, one manual edit, permission failure/retry, and keyboard open/close. Inline mutation may not call chat-bottom scrolling or focus the composer. The sale remains unconfirmed during this presentation checkpoint.

Pack fixtures must define pharmacy-owned `baseStockUnit`, `unitConversions` and `unitPrices`; no fixture may rely on a global pack assumption. Known conversion/price must calculate base deduction and total. Missing price or conversion must remain a blocked compact correction. `fixtures/sale-pack-hierarchy.json` provides distinct known, partial and missing relationship classes.
