# PharMareen Controlled Live Test Plan

Historical backend/training plan. Canonical MS2.0 owner checkpoint IDs, order and status live only in `../MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`.

Status: PREPARED

Live execution status: NOT STARTED

Rule: run one clear live test at a time only after explicit approval. If any item fails, stop, capture evidence, add or update an eval, fix, rerun regressions, then retest that item only.

## Evidence To Capture

- input sent
- actual reply
- stock/report/audit observed
- pass/fail
- token observation

## Prepared Sequence

1. WhatsApp deterministic sale
   - Send: `panadol2cash`
   - Expect: sale number, total, stock reduction, no AI fallback.

2. Typo sale
   - Send: `pnadol 1 cahs`
   - Expect: Panadol x1 Cash locally.

3. Shorthand sale
   - Send: `amox1mpesa`
   - Expect: medicine, quantity, and M-Pesa resolved locally.

4. Ambiguous medicine
   - Send: `p`
   - Expect: one short clarification, no guessing.

5. No-stock block
   - Send: `ors 9` when ORS stock is zero.
   - Expect: sale blocked, missed demand saved, stock not negative.

6. Stock check
   - Send: `panadol stock`
   - Expect: stock reply, no sale log.

7. Undo by sale number
   - Send: `undo sale N` after a test sale.
   - Expect: one reversal, stock restored once, audit trace kept.

8. Correction by sale number
   - Send: `correct sale N to mpesa` or `correct sale N quantity 1`.
   - Expect: ledger correction, finance/stock reconciliation, audit trace.

9. Report today
   - Send: `report today` or trigger daily report endpoint.
   - Expect: active ledger totals after undo/correction and payment reconciliation.

10. Multi-owner/staff simulated
    - Run staff sale, staff pending correction, owner approval, owner reversal using actor context.
    - Expect: staff/owner audit and namespace isolation.

11. Offline Tap & Talk online
    - Open offline app online and speak a clear known medicine.
    - Expect: editable Sale Ready card from first clear attempt where browser speech permits.

12. Offline Tap & Talk offline
    - Open cached offline app offline and speak or enter a clear known medicine.
    - Expect: local/offline path works or queues without API dependency.

13. Offline media queue online/offline
    - Queue item offline, reconnect, observe sync.
    - Expect: preserved item, one sync, no duplicate.

14. WhatsApp invoice/photo
    - Send controlled invoice/photo only when photo testing is explicitly resumed.
    - Expect: evidence captured without breaking deterministic sale flows.

15. Offline invoice/photo
    - Capture or queue controlled invoice/photo in offline app when photo testing is resumed.
    - Expect: queue preserves evidence and sync path avoids duplicate processing.

16. Editable approval card
    - Open prepared sale or extracted item, edit quantity/payment before approval.
    - Expect: edit visible before submit, saved once, audit clear.

17. Token usage preserved
    - Observe logs/metrics during known deterministic checks.
    - Expect: known commands show no OpenAI/API calls; approved photo extraction is explicitly noted.

## Decision

Prepared for controlled live review. Do not start live testing until explicitly instructed.
