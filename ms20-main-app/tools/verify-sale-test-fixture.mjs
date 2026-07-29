import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { assessSaleTestMedicine } from "../src/services/saleTestFixture.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixtureManifest = JSON.parse(fs.readFileSync(path.join(root, "fixtures", "launch-sale-test-medicines.json"), "utf8"));
const septrinFixture = fixtureManifest.fixtures.find((fixture) => fixture.fixture_id === "launch-sale-septrin-bottle");
assert.ok(septrinFixture, "The reusable Septrin launch-sale fixture must exist.");

const septrin = {
  id: septrinFixture.stable_catalog_id,
  name: septrinFixture.canonical_name,
  form: septrinFixture.form,
  unit: septrinFixture.unit,
  stock: septrinFixture.current_stock,
  selling_price: septrinFixture.selling_price,
  cost_price: septrinFixture.buying_price,
  barcode: septrinFixture.barcode,
  batch: septrinFixture.batch,
  expiry: septrinFixture.expiry,
  aliases: septrinFixture.aliases,
};
const ready = assessSaleTestMedicine({ medicine: septrin, catalog: [septrin], quantity: 1, requireBuyingPrice: true });
assert.equal(ready.ready, true);
assert.deepEqual(
  {
    canonicalName: ready.beforeState.canonicalName,
    currentStock: ready.beforeState.currentStock,
    unit: ready.beforeState.unit,
    form: ready.beforeState.form,
    sellingPrice: ready.beforeState.sellingPrice,
    buyingPrice: ready.beforeState.buyingPrice,
  },
  { canonicalName: "Septrin", currentStock: 12, unit: "bottle", form: "suspension", sellingPrice: 180, buyingPrice: 120 },
);

const zinc = { id: "zinc", name: "Zinc", form: "syrup", unit: "syrup", stock: "", selling_price: 70 };
const unsuitable = assessSaleTestMedicine({ medicine: zinc, catalog: [zinc], quantity: 1 });
assert.equal(unsuitable.ready, false);
assert.ok(unsuitable.issues.includes("numeric_current_stock_missing"), "Blank Zinc stock must fail stock-sensitive preflight.");

assert.ok(assessSaleTestMedicine({ medicine: septrin, catalog: [septrin], quantity: 13 }).issues.includes("insufficient_stock"));
assert.ok(assessSaleTestMedicine({ medicine: septrin, catalog: [septrin], requireBarcode: true }).issues.includes("barcode_missing"));
assert.ok(assessSaleTestMedicine({ medicine: septrin, catalog: [septrin], requireReorderLevel: true }).issues.includes("reorder_level_missing"));
assert.ok(assessSaleTestMedicine({ medicine: septrin, catalog: [septrin, { ...septrin, id: "septrin-copy" }] }).issues.includes("duplicate_or_alias_conflict"));

const appSource = fs.readFileSync(path.join(root, "src", "app.js"), "utf8");
const contracts = fs.readFileSync(path.join(root, "src", "contracts", "integrationContracts.js"), "utf8");
assert.ok(contracts.includes('"SaleCard"'), "SaleCard must remain part of the shared editable-card contract.");
for (const action of ["confirm-card", "read-card", "correct-card", "reject-card"]) {
  assert.ok(appSource.includes(`data-action="${action}"`), `The authoritative shared card must preserve ${action}.`);
}
assert.ok(appSource.includes("medicineDetailTemplate(card"), "Sale reviews must use the shared medicine-card renderer.");
assert.ok(appSource.includes("startVoiceCapture"), "Voice sales must use the shared voice-capture root.");
assert.ok(!appSource.includes("TestSaleCard"), "No simplified test-only sale card may bypass the owner workflow.");

console.log("SALE_TEST_FIXTURE_OK canonical=Septrin stock=12 unit=bottle selling_price=180 buying_price=120 shared_sale_card=protected");
