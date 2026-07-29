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

Some exact unit/pack/price presentation remains governed by MS2-LT-049. Until it is implemented and protected, a test needing that truth must stop if the authoritative flow cannot prove it.

## Permanent friction capture

Observe the entire shared sale flow whenever another test naturally passes through it. Record unrelated friction immediately. Fix a launch-blocking shared-root cause before it spreads, add regression coverage, preserve valid evidence already collected and avoid repeating proven portions unnecessarily. Friction does not silently disappear merely because another checkpoint supplied the route.
