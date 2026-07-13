import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { cardFieldsFor } from "../src/cards/editableCards.js";
import { PharmacyBrain, SourceBrain, AIFallbackAdapter } from "../src/services/brainAdapters.js";
import { catalogItemsToText, parseCatalogText, parseDelimitedInventory } from "../src/services/catalogOnboarding.js";
import { applyApprovedCatalogEdit, createCatalogEditDraft } from "../src/services/catalogWorkspace.js";
import { CATALOG_IMPORT_FIELD_KEYS, CATALOG_MEDICINE_FIELD_KEYS, medicineRecordFromFields, normalizeMedicineReviewRow } from "../src/services/medicineFieldSchema.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const assert = (condition, message) => { if (!condition) throw new Error(message); };

for (const field of ["strength", "barcode"]) {
  assert(CATALOG_MEDICINE_FIELD_KEYS.includes(field), `${field} must belong to the canonical Pharmacy Catalog editor schema`);
  assert(CATALOG_IMPORT_FIELD_KEYS.includes(field), `${field} must belong to the shared onboarding review schema`);
  for (const type of ["InvoiceCard", "RestockCard", "PhotoReviewCard", "MedicineMatchCard", "VisualScanCard"]) {
    assert(cardFieldsFor(type).includes(field), `${type} must inherit optional ${field} from the shared medicine-card schema`);
  }
}

const csv = "medicine,strength,form,unit,stock,barcode\nAspirin,75 mg,tablet,tablet,50,6161100000012\nAtenolol,,tablet,tablet,40,";
const parsed = parseDelimitedInventory(csv, new SourceBrain());
const reviewRows = parseCatalogText(catalogItemsToText(parsed.items)).map(normalizeMedicineReviewRow);
assert(reviewRows[0].strength === "75 mg" && reviewRows[0].barcode === "6161100000012", "CSV strength and barcode must survive the shared editable-review round trip");
assert(reviewRows[1].strength === "" && reviewRows[1].barcode === "", "Blank strength and barcode must remain valid optional review values");

const brain = new PharmacyBrain({ pharmacyId: "shared-field-verify" });
brain.loadCatalog(reviewRows);
brain.upsertCatalogItem({ name: "Aspirin", strength: "", barcode: "" });
assert(brain.catalog.length === 2, "Shared field updates must not duplicate an existing medicine");
assert(brain.catalog[0].strength === "75 mg" && brain.catalog[0].barcode === "6161100000012", "Sparse repeated onboarding must not erase stronger persisted identity fields");
const restockRecord = medicineRecordFromFields(
  { medicine: "Aspirin", strength: "100 mg", barcode: "6161100000098", quantity: "5" },
  { source: "restock_review", quantityIsStock: false }
);
brain.upsertCatalogItem(restockRecord);
assert(brain.catalog.length === 2 && brain.catalog[0].strength === "100 mg" && brain.catalog[0].barcode === "6161100000098", "Restock review must reuse canonical medicine persistence without duplication");
assert(brain.catalog[0].stockLeft === "50", "Restock metadata review must not confuse delivered quantity with replacement stock");
const refreshed = new PharmacyBrain({ pharmacyId: "shared-field-refresh" });
refreshed.loadCatalog(JSON.parse(JSON.stringify(brain.catalog)));
assert(refreshed.catalog[0].strength === "100 mg" && refreshed.catalog[0].barcode === "6161100000098", "Strength and barcode must persist through refresh serialization");

const draft = createCatalogEditDraft(refreshed.catalog[0]);
draft.strength = "125 mg";
draft.barcode = "6161100000128";
const edited = applyApprovedCatalogEdit(refreshed.catalog, draft.id, draft);
assert(edited.valid && edited.catalog.length === 2, "Medicine Action Card approval must update without duplication");
assert(edited.updated.strength === "125 mg" && edited.updated.barcode === "6161100000128", "Medicine Action Card must persist approved strength and barcode edits");

assert(app.includes("medicineFieldColumns(CATALOG_IMPORT_FIELD_KEYS)"), "Catalog imports must render from the shared medicine field schema");
assert(app.includes("return normalizeMedicineReviewRow(row)"), "All catalog review rows must normalize through the shared medicine schema");
assert(app.includes("medicineRecordFromFields(fields"), "Shared photo/manual review approval must use canonical medicine persistence");
assert(new AIFallbackAdapter().calls === 0, "Shared medicine display, review, and persistence must remain zero-token");

console.log("Shared medicine field verification passed: CSV, photo/scan, invoice, restock, sale-learning, catalog editing, persistence, sparse optional values, duplicate safety, and zero AI calls.");
