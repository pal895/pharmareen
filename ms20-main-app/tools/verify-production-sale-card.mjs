import assert from "node:assert/strict";
import fs from "node:fs";
import { prepareProductionSaleCard, productionSaleSummary, saleFieldsFromTransaction } from "../src/services/productionSaleCard.js";

const catalogMedicine = {
  name: "Septrin", strength: "100 ml", forms: ["suspension"], units: ["bottle"],
  sellingPrice: 180, stockLeft: 12
};
const card = prepareProductionSaleCard({
  type: "SaleCard",
  status: "ready",
  fields: { medicine: "septrin", quantity: 1, payment: "mpesa" }
}, { status: "matched", matches: [catalogMedicine] });

assert.equal(card.productionSaleCardVersion, "1.0");
assert.deepEqual(card.saleIssues, []);
assert.deepEqual(card.fields, {
  medicine: "Septrin", quantity: 1, payment: "mpesa", strength: "100 ml",
  form: "suspension", unit: "bottle", selling_price: 180, expected_total: 180,
  stock_before: 12, stock_after: 11, sale_status: "Review before recording"
});
assert.match(productionSaleSummary(card.fields), /Septrin · suspension · bottle · 1 × KES 180 = KES 180 · M-Pesa/);

const multiUnit = prepareProductionSaleCard({
  type: "SaleCard", fields: { medicine: "Paracetamol", form: "tablet", unit: "pack", quantity: 2, payment: "cash" }
}, {
  status: "matched",
  matches: [{
    name: "Paracetamol", forms: ["tablet"], units: ["tablet", "pack"], stockLeft: 100,
    unitPrices: { tablet: 5, pack: 50 }, unitConversions: { tablet: 1, pack: 10 }
  }]
});
assert.equal(multiUnit.fields.selling_price, 50);
assert.equal(multiUnit.fields.expected_total, 100);
assert.equal(multiUnit.fields.stock_after, 80);
assert.deepEqual(multiUnit.saleOptions.units, ["tablet", "pack"]);

const unsafe = prepareProductionSaleCard({
  type: "SaleCard", fields: { medicine: "Unknown", quantity: 20, payment: "" }
}, { status: "not_found", matches: [] });
assert.ok(unsafe.saleIssues.includes("medicine_not_uniquely_matched"));
assert.ok(unsafe.saleIssues.includes("form_unknown"));
assert.ok(unsafe.saleIssues.includes("selling_unit_unknown"));
assert.ok(unsafe.saleIssues.includes("unit_price_unknown"));
assert.ok(unsafe.saleIssues.includes("payment_unknown"));

const transactionFields = saleFieldsFromTransaction({
  status: "failed", amount: 180, paymentMethod: "mpesa",
  metadata: { medicine: "Septrin", form: "suspension", unit: "bottle", quantity: 1, sellingPrice: 180, stockBefore: 12, stockAfter: 11 }
});
assert.equal(transactionFields.sale_status, "failed");
assert.equal(transactionFields.expected_total, 180);
assert.equal(transactionFields.form, "suspension");

const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
assert.match(app, /productionSaleCardBody\(card\.fields/);
assert.match(app, /productionSaleCardBody\(saleFieldsFromTransaction\(item\)/);
assert.match(app, /card\.type = "SaleCard";\s+card\.title = "Check voice result"/);
assert.match(app, /function canRecordInstantly[\s\S]*?return false;/);
assert.doesNotMatch(app, /VoiceReviewCard/);

console.log("Production Sales Card verified: one shared model/renderer covers typed, voice, queue and transaction recovery.");
