import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { cardFieldsFor } from "../src/cards/editableCards.js";
import { PharmacyBrain, SourceBrain, AIFallbackAdapter } from "../src/services/brainAdapters.js";
import { catalogItemsToText, parseCatalogText, parseDelimitedInventory } from "../src/services/catalogOnboarding.js";
import { applyApprovedCatalogEdit, createCatalogEditDraft } from "../src/services/catalogWorkspace.js";
import { buildDeterministicNotifications } from "../src/services/notificationCenter.js";
import { CATALOG_IMPORT_FIELD_KEYS, CATALOG_MEDICINE_FIELD_KEYS, medicineRecordFromFields, normalizeExpiryValue, normalizeMedicineReviewRow } from "../src/services/medicineFieldSchema.js";

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
assert(normalizeExpiryValue("Oct-28") === "2028-10" && normalizeExpiryValue("10/28") === "2028-10", "Display-style expiry months must normalize to unambiguous YYYY-MM");

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
const barcodeRecord = medicineRecordFromFields({
  medicine: "Losartan",
  strength: "50 mg",
  form: "tablet",
  unit: "tablet",
  stock: "40",
  selling_price: "25",
  cost_price: "15",
  supplier: "Dawa Bora Wholesale Ltd",
  barcode: "6161109876546",
  batch: "LOS-50T",
  expiry: "2029-06"
}, { source: "scan_review" });
brain.upsertCatalogItem(barcodeRecord);
assert(brain.catalog.at(-1).batches[0]?.batch === "LOS-50T", "Shared review approval must promote a top-level batch into canonical catalog batches");
const savedLosartanReview = normalizeMedicineReviewRow(brain.catalog.at(-1));
assert(savedLosartanReview.stock === "40" && savedLosartanReview.cost_price === "15", "Saved catalog stock and buying price must return to shared reviews through canonical aliases");
assert(savedLosartanReview.form === "tablet" && savedLosartanReview.unit === "tablet" && savedLosartanReview.batch === "LOS-50T", "Saved packaging and batch must return to shared reviews through canonical arrays");
brain.upsertCatalogItem(medicineRecordFromFields({ medicine: "Losartan", barcode: "6161109876546", quantity: "" }, { source: "scan_review" }));
assert(brain.catalog.length === 3, "Repeated barcode approval must not duplicate an existing catalog medicine");
assert(brain.catalog.at(-1).stockLeft === "40" && brain.catalog.at(-1).costPrice === "15" && brain.catalog.at(-1).supplier === "Dawa Bora Wholesale Ltd", "Sparse repeat approval must not erase saved stock or commercial fields");
assert(brain.catalog.at(-1).batches[0]?.batch === "LOS-50T" && brain.catalog.at(-1).batches.length === 1, "Sparse repeat approval must preserve and deduplicate saved traceability");
const refreshed = new PharmacyBrain({ pharmacyId: "shared-field-refresh" });
refreshed.loadCatalog(JSON.parse(JSON.stringify(brain.catalog)));
assert(refreshed.catalog[0].strength === "100 mg" && refreshed.catalog[0].barcode === "6161100000098", "Strength and barcode must persist through refresh serialization");
assert(refreshed.catalog.at(-1).batches[0]?.batch === "LOS-50T" && refreshed.catalog.at(-1).batches[0]?.expiry === "2029-06", "Barcode batch and expiry must persist together through refresh serialization");
refreshed.upsertCatalogItem({ name: "Expiry Check", batches: [{ batch: "E1", expiry: "Oct-28" }] });
assert(refreshed.catalog.at(-1).batches[0].expiry === "2028-10", "Persisted catalog loading must migrate display-style expiry text to canonical YYYY-MM");
const futureExpiry = buildDeterministicNotifications({ catalog: [refreshed.catalog.at(-1)], now: new Date("2026-07-14T00:00:00Z") });
assert(!futureExpiry.some((item) => item.category === "Expiry"), "Oct-28 must never be misread as an expired date in 2001");
const nearExpiry = buildDeterministicNotifications({ catalog: [{ name: "Near Expiry", batches: [{ batch: "N1", expiry: "Jul-26" }] }], now: new Date("2026-07-14T00:00:00Z") });
assert(nearExpiry.some((item) => item.message.includes("end of July 2026")), "Month-only expiry alerts must use the pharmaceutical end-of-month rule and clear wording");

const draft = createCatalogEditDraft(refreshed.catalog[0]);
draft.strength = "125 mg";
draft.barcode = "6161100000128";
const edited = applyApprovedCatalogEdit(refreshed.catalog, draft.id, draft);
assert(edited.valid && edited.catalog.length === refreshed.catalog.length, "Medicine Action Card approval must update without duplication");
assert(edited.updated.strength === "125 mg" && edited.updated.barcode === "6161100000128", "Medicine Action Card must persist approved strength and barcode edits");

assert(app.includes("medicineFieldColumns(CATALOG_IMPORT_FIELD_KEYS)"), "Catalog imports must render from the shared medicine field schema");
assert(app.includes("return normalizeMedicineReviewRow(row)"), "All catalog review rows must normalize through the shared medicine schema");
assert(app.includes("medicineRecordFromFields(fields"), "Shared photo/manual review approval must use canonical medicine persistence");
assert(new AIFallbackAdapter().calls === 0, "Shared medicine display, review, and persistence must remain zero-token");

console.log("Shared medicine field verification passed: CSV, photo/scan, invoice, restock, sale-learning, catalog editing, persistence, sparse optional values, duplicate safety, and zero AI calls.");
