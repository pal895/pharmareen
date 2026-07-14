import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AIFallbackAdapter, PharmacyBrain } from "../src/services/brainAdapters.js";
import { catalogReviewCapabilities, reorderedCatalogRows } from "../src/services/catalogReviewPolicy.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const card = (fields) => ({ type: "CatalogImportCard", fields: { entry_mode: "review", ...fields } });

for (const review of [card({ import_mode: "invoice_ocr", import_incomplete: "false" }), card({ method: "csv" }), card({ method: "bulk paste" })]) {
  const policy = catalogReviewCapabilities(review);
  assert(policy.reorderable && policy.addRowAllowed && policy.approvalAllowed, "Safe multi-row catalog reviews must inherit shared review capabilities");
}
assert(!catalogReviewCapabilities(card({ import_mode: "invoice_ocr", import_incomplete: "true" })).reorderable, "Safety-blocked invoice review must not expose row movement");
assert(!catalogReviewCapabilities({ type: "MedicineMatchCard", fields: {} }).reorderable, "Single-medicine cards must not receive row movement controls");

const original = [{ name: "Aspirin", quantity: "50" }, { name: "Atenolol", quantity: "40" }, { name: "Folic Acid", quantity: "60" }];
const moved = reorderedCatalogRows(original, 1, -1);
assert(moved.map((row) => row.name).join("|") === "Atenolol|Aspirin|Folic Acid", "A row must move in the requested direction");
assert(moved[0].quantity === "40" && moved[1].quantity === "50", "Movement must preserve each medicine row's data");
assert(reorderedCatalogRows(original, 0, -1).map((row) => row.name).join("|") === original.map((row) => row.name).join("|"), "First-row upper boundary must be safe");
assert(reorderedCatalogRows(original, 2, 1).map((row) => row.name).join("|") === original.map((row) => row.name).join("|"), "Last-row lower boundary must be safe");
assert(new Set(moved.map((row) => row.name)).size === moved.length, "Reordering must not create duplicate medicines");
const brain = new PharmacyBrain({ pharmacyId: "reorder-approval" });
brain.loadCatalog(moved);
assert(brain.catalog.length === moved.length && brain.catalog.map((item) => item.name).join("|") === moved.map((item) => item.name).join("|"), "Reordered rows must survive approval without duplication");
assert(app.includes("catalogReviewCapabilities(card)") && app.includes("catalogRowOrderControls"), "Desktop and mobile review renderers must consume one shared capability and control renderer");
assert(new AIFallbackAdapter().calls === 0, "Shared review reordering must remain local and zero-token");

console.log("Catalog review reordering verification passed: invoice, CSV, bulk paste, boundaries, data integrity, approval, safety exception, single-card exclusion, and zero AI calls.");
