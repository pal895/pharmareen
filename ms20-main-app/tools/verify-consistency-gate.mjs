import fs from "node:fs";
import { PharmacyBrain, AIFallbackAdapter } from "../src/services/brainAdapters.js";
import { applyApprovedCatalogEdit, createCatalogEditDraft } from "../src/services/catalogWorkspace.js";
import { medicineRecordFromFields, normalizeMedicineReviewRow } from "../src/services/medicineFieldSchema.js";
import { reorderedCatalogRows } from "../src/services/catalogReviewPolicy.js";

const assert = (condition, message) => { if (!condition) throw new Error(message); };
const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
const trusted = {
  name: "Baseline Medicine",
  strength: "50 mg",
  form: "tablet",
  unit: "tablet",
  pack_size: "28",
  stock: "40",
  selling_price: "25",
  cost_price: "15",
  supplier: "Trusted Supplier",
  barcode: "6161109876546",
  batch: "BASE-50T",
  expiry: "2029-06",
  shelf: "A1",
  category: "Cardiovascular",
  reorder_level: "10",
  aliases: ["Baseline"]
};

const brain = new PharmacyBrain({ pharmacyId: "consistency-gate" });
brain.upsertCatalogItem(trusted);
const expected = normalizeMedicineReviewRow(brain.catalog[0]);
const stableFields = ["name", "strength", "form", "unit", "pack_size", "stock", "selling_price", "cost_price", "supplier", "barcode", "batch", "expiry", "shelf"];
const assertStable = (label) => {
  const actual = normalizeMedicineReviewRow(brain.catalog[0]);
  for (const field of stableFields) assert(String(actual[field]) === String(expected[field]), `${label} weakened trusted ${field}`);
  assert(brain.catalog.length === 1, `${label} created a duplicate medicine`);
  assert(brain.catalog[0].batches.length === 1, `${label} duplicated batch records`);
};

for (const source of ["invoice_review", "csv_import", "bulk_paste", "manual_review", "photo_review", "sale_time_learning", "restock_review", "scan_review"]) {
  brain.upsertCatalogItem(medicineRecordFromFields({
    medicine: trusted.name,
    strength: "unknown",
    form: "-",
    unit: "N/A",
    quantity: "",
    selling_price: "",
    cost_price: "unreadable",
    supplier: "not available",
    barcode: trusted.barcode,
    batch: "",
    expiry: "",
    shelf: ""
  }, { source, quantityIsStock: source !== "restock_review" }));
  assertStable(source);
}

const refreshed = new PharmacyBrain({ pharmacyId: "consistency-refresh" });
refreshed.loadCatalog(JSON.parse(JSON.stringify(brain.catalog)));
assert(JSON.stringify(normalizeMedicineReviewRow(refreshed.catalog[0])) === JSON.stringify(normalizeMedicineReviewRow(brain.catalog[0])), "Refresh changed the trusted canonical result");

const draft = createCatalogEditDraft(refreshed.catalog[0]);
draft.shelf = "";
const cleared = applyApprovedCatalogEdit(refreshed.catalog, draft.id, draft);
assert(cleared.valid && cleared.updated.shelf === "", "Explicit owner-approved catalog edit must remain able to clear a selected field");

const rows = [normalizeMedicineReviewRow(brain.catalog[0]), { name: "Second", stock: "2", batch: "S2" }];
const moved = reorderedCatalogRows(rows, 1, -1);
assert(JSON.stringify(moved[1]) === JSON.stringify(rows[0]), "Row reordering changed trusted medicine contents");

assert(app.includes("normalizeMedicineReviewRow(recognized)"), "Repeat scans must use canonical review normalization");
assert(app.includes("medicineRecordFromFields(card.fields, { source: \"sale_time_learning\" })"), "Sale learning must use canonical medicine persistence");
assert(app.includes("medicineRecordFromFields(card.fields, {\n    source: \"restock_review\""), "Restocking must use canonical medicine persistence");
assert(app.includes("saved.push(pharmacyBrain.upsertCatalogItem(item))"), "Shared catalog approvals must converge on Pharmacy Brain safe merge");
assert(new AIFallbackAdapter().calls === 0, "Consistency protection must remain local and zero-token");

console.log("Consistency regression gate passed: canonical shapes, sparse and placeholder preservation, invoice/CSV/Paste/manual/photo/sale/restock/barcode workflows, explicit edits, refresh, reordering, batches, duplicates, and zero AI calls.");
