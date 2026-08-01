import assert from "node:assert/strict";
import fs from "node:fs";
import {
  completedSaleByReference,
  createSaleAdjustmentReview,
  SaleAdjustmentEngine,
  saleDetailFields,
  saleReferenceFromReceipt
} from "../src/services/saleAdjustmentReview.js";

const transaction = {
  id: "transaction-card-1", permanentId: "2026-07-31-sale-1", kind: "sale",
  status: "completed", saleNumber: 1, amount: 108, paymentMethod: "cash",
  metadata: { medicine: "Ibuprofen", form: "tablet", unit: "tablet", quantity: 6,
    sellingPrice: 18, baseStockDeduction: 6, stockAfter: 21 }
};
assert.deepEqual(saleReferenceFromReceipt("Sale 1\nIbuprofen x6 recorded"), { saleNumber: 1 });
assert.equal(completedSaleByReference([transaction], { transactionId: transaction.permanentId }), transaction);
assert.equal(saleDetailFields(transaction).total, 108);

const returnReview = createSaleAdjustmentReview(transaction, "return", 2);
assert.equal(returnReview.stock_to_restore, 2);
const refundReview = createSaleAdjustmentReview(transaction, "refund", 1);
assert.equal(refundReview.stock_to_restore, 0, "refund must not assume stock return");
assert.equal(createSaleAdjustmentReview(transaction, "refund", 1, [], { restoreStock: true }).stock_to_restore, 1);
assert.equal(createSaleAdjustmentReview(transaction, "credit").stock_to_restore, 0);
assert.match(createSaleAdjustmentReview({ ...transaction, paymentMethod: "mixed" }, "credit").payment_impact, /no mixed refund/);

const engine = new SaleAdjustmentEngine({ now: () => new Date("2026-07-31T08:00:00Z") });
const first = engine.confirm(engine.review(transaction, "return", 2, { reviewId: "adjust-1" }));
assert.equal(first.created, true);
assert.equal(first.record.original_transaction_id, transaction.permanentId);
assert.equal(engine.confirm(first.record).duplicate, true, "double confirmation must be idempotent");
assert.equal(engine.review(transaction, "credit", 4).remaining_quantity, 4);
engine.confirm(engine.review(transaction, "credit", 4, { reviewId: "adjust-2" }));
assert.equal(engine.review(transaction, "return", 1), null, "fully adjusted sale must be blocked");

const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
for (const marker of [
  'data-action="open-completed-sale"', 'data-adjustment-type="refund"',
  'data-adjustment-type="return"', 'data-adjustment-type="credit"',
  'data-action="confirm-sale-adjustment"', 'data-action="open-sale-adjustment"',
  'data-action="open-adjustment-original"', "syncAdapter.queueAction"
]) assert.match(app, new RegExp(marker));
for (const text of [
  "Should this medicine go back into stock?", "Money back + medicine back in stock",
  "Stock added back", "record #", "for Sale", "Previously adjusted",
  "Remaining before this adjustment", "Remaining after confirmation",
  "is already fully adjusted. No stock or money changed."
]) assert.ok(app.includes(text), `Missing shared adjustment wording: ${text}`);
assert.match(app, /adjustmentQuantity <= 1 \? "disabled"/);
assert.match(app, /adjustmentQuantity >= remainingQuantity \? "disabled"/);

const css = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
assert.match(css, /\.refund-stock-choice button\[aria-pressed="true"\][\s\S]*background:\s*var\(--accent\)/);
assert.match(app, /aria-pressed="\$\{!fields\.restore_stock\}"[\s\S]*✓[\s\S]*Money only/);
assert.doesNotMatch(app, /Does returned stock come back into inventory\?/);

console.log("SALE_ADJUSTMENT_WORKFLOW_OK review=shared confirm=idempotent ledger=linked offline=queued");
