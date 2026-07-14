# Trusted result consistency

Consistency is a product, trust, and operational-safety requirement. Every live-approved result becomes a trusted baseline for the same entity and applicable workflow behavior. Later actions, refreshes, adapters, sync, reports, notifications, and presentation improvements must preserve its meaningful facts unless the owner deliberately changes them or a verified improvement changes behavior without losing correct data.

## Canonical safe-merge rule

- Normalize fixture, parser, import, review, and saved-catalog shapes before comparison or persistence.
- A valid supplied value updates the canonical record.
- Absent values, empty sparse values, placeholders, and failed extraction results preserve meaningful saved values.
- An explicit owner-approved catalog edit may clear the selected field; temporary workflow shapes may not imply clearing.
- Repeated actions must preserve identity, aliases, strength, packaging, stock, prices, supplier, barcode, batch/expiry, shelf, category, and reorder settings where applicable.
- Duplicate resolution and batch merging must remain deterministic, local, and duplicate-safe.

## Trusted baseline fields

For each live-approved behavior retain: correct input, displayed result, saved result, required stable fields, legitimately changeable fields, persistence/refresh expectations, duplicate expectations, and local-first/zero-token expectations. Presentation may improve only if the same trusted facts and actions remain available.

Protected evidence currently covers invoice and second-invoice approval, Paste List partitioning, CSV field persistence, SHOW ME and Medicine Action Cards, approved/cancelled catalog edits, row movement integrity, sale-time learning, basic sales, restocking, and Losartan barcode onboarding/repeat recognition. Focused contract tests protect these baselines instead of repeating every owner test.

## Before every relevant commit

1. Identify previously approved behavior in the change's blast radius.
2. Identify the trusted values before the action.
3. Confirm the result still contains those values.
4. Check for blanks, duplicates, incorrect renames, or incompatible structures.
5. Confirm sparse input preserves meaningful values.
6. Confirm refresh reproduces the same state.
7. Confirm repeating the action is safe and duplicate-free.
8. Confirm the improvement does not weaken accepted behavior.
9. Confirm local-first and zero-token guarantees remain intact.
10. Run focused regression protection.

Run `npm run verify:consistency` before commits affecting medicine normalization, adapters, scanning, cards, approval, persistence, catalog loading, sync, stock, batches, expiry, pricing, or duplicate prevention.
