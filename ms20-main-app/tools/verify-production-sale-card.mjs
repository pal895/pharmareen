import assert from "node:assert/strict";
import fs from "node:fs";
import { prepareProductionSaleCard, productionSaleSummary, saleFieldsFromTransaction } from "../src/services/productionSaleCard.js";
import { parseLocalCommand } from "../src/services/localIntelligence.js";

const catalogMedicine = {
  name: "Septrin", strength: "100 ml", forms: ["suspension"], units: ["bottle"],
  sellingPrice: 180, costPrice: 120, stockLeft: 12, supplier: "MedSource Kenya",
  barcode: "6160001112223", batches: [{ batch: "SEP-100S", expiry: "2028-09" }], aliases: ["Co-trimoxazole"]
};
const card = prepareProductionSaleCard({
  type: "SaleCard",
  status: "ready",
  fields: { medicine: "septrin", quantity: 1, payment: "mpesa" }
}, { status: "matched", matches: [catalogMedicine] });

assert.equal(card.productionSaleCardVersion, "1.0");
assert.deepEqual(card.saleIssues, []);
assert.deepEqual(Object.fromEntries([
  "medicine", "quantity", "payment", "strength", "form", "unit", "selling_price",
  "expected_total", "stock_before", "stock_after", "sale_status"
].map((key) => [key, card.fields[key]])), {
  medicine: "Septrin", quantity: 1, payment: "mpesa", strength: "100 ml",
  form: "suspension", unit: "bottle", selling_price: 180, expected_total: 180,
  stock_before: 12, stock_after: 11, sale_status: "Review before recording"
});
assert.match(productionSaleSummary(card.fields), /Septrin · suspension · bottle · 1 × KES 180 = KES 180 · M-Pesa/);
assert.equal(card.fields.cost_price, 120);
assert.equal(card.fields.supplier, "MedSource Kenya");
assert.equal(card.fields.barcode, "6160001112223");
assert.equal(card.fields.batch, "SEP-100S");
assert.equal(card.fields.expiry, "2028-09");
assert.equal(card.fields.aliases, "Co-trimoxazole");

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

const parseCatalog = [{
  id: "paracetamol", name: "Paracetamol", strength: "500 mg", forms: ["tablet"], units: ["tablet"],
  sellingPrice: 5, costPrice: 3, stockLeft: 100, supplier: "Test Supplier", barcode: "123",
  batches: [{ batch: "PCM-1", expiry: "2028-12" }], aliases: ["Panadol"]
}];
for (const [command, quantity, payment] of [
  ["paracetamol cash", 1, "cash"],
  ["paracetamol 2 cash", 2, "cash"],
  ["paracetamol2cash", 2, "cash"],
  ["paracetamol two cash", 2, "cash"],
  ["paracetamol one m-pesa", 1, "mpesa"]
]) {
  const parsed = parseLocalCommand(command, parseCatalog);
  assert.equal(parsed.cardType, "SaleCard", `${command} must route to SaleCard`);
  assert.equal(parsed.fields.medicine, "Paracetamol", `${command} must exclude payment and quantity from medicine`);
  assert.equal(parsed.fields.quantity, quantity);
  assert.equal(parsed.fields.payment, payment);
}

for (const [command, quantity, unit, payment] of [
  ["paracetamol one packet cash", 1, "packet", "cash"],
  ["paracetamol 2 packets m-pesa", 2, "packet", "mpesa"],
  ["Panadol one strip cash", 1, "strip", "cash"],
  ["paracetamol 3 tabs credit", 3, "tablet", "credit"]
]) {
  const parsed = parseLocalCommand(command, parseCatalog);
  assert.equal(parsed.cardType, "SaleCard");
  assert.equal(parsed.fields.medicine, "Paracetamol");
  assert.equal(parsed.fields.quantity, quantity);
  assert.equal(parsed.fields.unit, unit);
  assert.equal(parsed.fields.payment, payment);
}

const packetSale = prepareProductionSaleCard({
  type: "SaleCard", fields: { medicine: "Paracetamol", unit: "packet", quantity: 1, payment: "cash" }
}, {
  status: "matched",
  matches: [{
    name: "Paracetamol", forms: ["tablet"], units: ["tablet", "packet"], baseStockUnit: "tablet",
    stockLeft: 100, unitPrices: { tablet: 5, packet: 90 }, unitConversions: { tablet: 1, packet: 20 }
  }]
});
assert.equal(packetSale.fields.selling_price, 90);
assert.equal(packetSale.fields.stock_deduction, 20);
assert.equal(packetSale.fields.stock_after, 80);
assert.deepEqual(packetSale.saleIssues, []);

const missingPacketFacts = prepareProductionSaleCard({
  type: "SaleCard", fields: { medicine: "Paracetamol", unit: "packet", quantity: 1, payment: "cash" }
}, { status: "matched", matches: [{ name: "Paracetamol", forms: ["tablet"], units: ["tablet"], stockLeft: 100, sellingPrice: 5 }] });
assert.ok(missingPacketFacts.saleIssues.includes("pack_conversion_unknown"));
assert.ok(missingPacketFacts.saleIssues.includes("unit_price_unknown"));

const existingMedicineUnknownBox = prepareProductionSaleCard({
  type: "SaleCard", fields: { medicine: "Paracetamol", quantity: 1, unit: "box", payment: "cash" }
}, {
  status: "matched", matches: [{
    name: "Paracetamol", strength: "500 mg", forms: ["tablet"], units: ["tablet"],
    baseStockUnit: "tablet", sellingPrice: 10, costPrice: 5, stockLeft: 100,
    supplier: "EastCare Pharma", batch: "PAR-500C", expiry: "2029-06", aliases: ["PCM"]
  }]
});
assert.equal(existingMedicineUnknownBox.fields.medicine, "Paracetamol");
assert.equal(existingMedicineUnknownBox.fields.unit, "box");
assert.equal(existingMedicineUnknownBox.fields.base_stock_unit, "tablet");
assert.equal(existingMedicineUnknownBox.fields.current_stock, 100);
assert.equal(existingMedicineUnknownBox.fields.strength, "500 mg");
assert.equal(existingMedicineUnknownBox.fields.supplier, "EastCare Pharma");
assert.ok(existingMedicineUnknownBox.saleIssues.includes("pack_conversion_unknown"));
assert.ok(existingMedicineUnknownBox.saleIssues.includes("unit_price_unknown"));
assert.match(existingMedicineUnknownBox.validation, /how many tablets are in one box/i);
assert.equal(missingPacketFacts.fields.stock_after, "");

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
const packFixtures = JSON.parse(fs.readFileSync(new URL("../fixtures/sale-pack-hierarchy.json", import.meta.url), "utf8"));
const ownerApproval = JSON.parse(fs.readFileSync(new URL("../fixtures/production-sale-card-owner-approval.json", import.meta.url), "utf8"));
assert.equal(ownerApproval.status, "PASS / PROTECTED");
assert.deepEqual(ownerApproval.layout, ["compact cream", "Fast action", "Stock & details", "Traceability"]);
assert.equal(ownerApproval.approvedBoxEvidence.baseUnitsPerSellingUnit, 12);
assert.equal(ownerApproval.approvedBoxEvidence.unitPriceKes, 100);
assert.equal(ownerApproval.approvedBoxEvidence.expectedTotalKes, 100);
assert.match(ownerApproval.approvedBoxEvidence.clarification, /How many tablets are in one box\?/);
assert.equal(packFixtures.medicines.length, 3);
assert.equal(packFixtures.medicines[0].unitConversions.packet, 20);
assert.equal(packFixtures.unknownUnitScenarios.length, 3);
assert.equal(packFixtures.unknownUnitScenarios[2].medicine, "Paracetamol");
assert.deepEqual(packFixtures.unknownUnitScenarios[2].missing, ["unitConversion", "unitPrice"]);
assert.match(app, /productionSaleCardBody\(card\.fields/);
assert.match(app, /productionSaleCardBody\(saleFieldsFromTransaction\(item\)/);
assert.match(app, /card\.type = "SaleCard";\s+card\.title = "Check voice result"/);
assert.match(app, /card\.fields = \{ \.\.\.card\.fields, transcript: text \};/, "The voice adapter must preserve medicine, quantity, requested unit and payment parsed before Sale preparation.");
assert.match(app, /function canRecordInstantly[\s\S]*?return false;/);
assert.doesNotMatch(app, /VoiceReviewCard/);
assert.match(app, />Fast action<\/button>/);
assert.match(app, />Stock &amp; details<\/button>/);
assert.match(app, />Traceability<\/button>/);
assert.match(app, /sale-approval-grid/, "The default approval view must remain compact.");
assert.match(app, /card\.ui\?\.editing/, "Full editable fields must stay behind the explicit correction state.");
assert.match(app, /sale-edit-field-voice/, "Every editable Sale field must expose the shared contextual Mic pattern.");
assert.match(app, /startSaleEditFieldVoice[\s\S]*?startVoiceCapture/, "Sale field microphones must delegate to the shared capture root.");
for (const field of ["supplier", "barcode", "batch", "expiry", "aliases", "note"]) {
  assert.match(app, new RegExp(`PRODUCTION_SALE_EDITABLE_FIELDS[\\s\\S]*?"${field}"`), `Slide 3 ${field} must use the shared editable-field registry.`);
}
assert.match(app, /contextualEditableFieldTemplate/, "Catalog and Sale correction fields must share one inline field component.");
assert.doesNotMatch(app, /sale-edit-field-voice[\s\S]{0,300}scrollChatToBottom/, "Sale field voice must never own a scroll-to-bottom path.");
assert.match(app, /refreshProductionSaleCardControls\(card\)/);
assert.match(app, /function saveApprovedSalePackFacts[\s\S]*medicine\.unitConversions[\s\S]*medicine\.unitPrices/, "Approved conversion and price must attach to the existing catalog medicine.");
assert.match(app, /function rejectCard[\s\S]*?removeCard\(cardId\)/, "Cancel must remove only the unsaved draft.");
assert.match(app, /function confirmCard[\s\S]*?recordCard\(card\)/, "Only Confirm may reach sale recording.");
assert.match(app, /recordCard\(card\);[\s\S]*?removeCard\(cardId\)/, "Recording must remain behind the confirmation boundary.");

console.log("Production Sales Card verified: one shared model/renderer covers typed, voice, queue and transaction recovery.");
