import assert from "node:assert/strict";
import fs from "node:fs";
import {
  completedSaleByReference,
  createSaleAdjustmentReview,
  saleDetailFields,
  saleReferenceFromReceipt
} from "../src/services/saleAdjustmentReview.js";

const transaction = {
  id: "transaction-card-1",
  permanentId: "2026-07-31-sale-1",
  kind: "sale",
  status: "completed",
  saleNumber: 1,
  amount: 108,
  paymentMethod: "cash",
  metadata: {
    medicine: "Ibuprofen",
    form: "tablet",
    unit: "tablet",
    quantity: 6,
    sellingPrice: 18,
    stockAfter: 21
  }
};

assert.deepEqual(saleReferenceFromReceipt("Sale 1\n✅ Ibuprofen x6 recorded · Cash"), { saleNumber: 1 });
assert.equal(completedSaleByReference([transaction], { saleNumber: 1 }), transaction);
assert.equal(completedSaleByReference([transaction], { transactionId: transaction.permanentId }), transaction);
assert.equal(saleDetailFields(transaction).total, 108);

for (const type of ["refund", "return", "credit"]) {
  const review = createSaleAdjustmentReview(transaction, type);
  assert.equal(review.original_sale_number, 1);
  assert.equal(review.adjustment_type, type);
  assert.equal(review.adjustment_quantity, 1);
  assert.equal(review.financial_adjustment, 18);
  assert.equal(review.stock_to_restore, type === "credit" ? 0 : 1);
  assert.equal(review.review_status, "Review only — nothing has changed");
}

const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
assert.match(app, /data-action="open-completed-sale"/);
assert.match(app, /data-action="start-sale-adjustment"[\s\S]*data-adjustment-type="refund"/);
assert.match(app, /data-adjustment-type="return"/);
assert.match(app, /data-adjustment-type="credit"/);
assert.match(app, /saleReference:\s*\{[\s\S]*saleNumber:/);
assert.doesNotMatch(app, /SaleAdjustmentReviewCard[\s\S]{0,500}confirm-card/);

console.log("SALE_ADJUSTMENT_ENTRY_OK receipt=interactive detail=linked options=refund,return,credit mutation=none");
