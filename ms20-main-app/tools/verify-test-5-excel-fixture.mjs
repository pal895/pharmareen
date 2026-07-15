import fs from "node:fs";
import { SourceBrain } from "../src/services/brainAdapters.js";
import { readXlsxInventory } from "../src/services/excelInventory.js";
import { catalogItemsToText, createPasteImportCard, parseCatalogText, parseDelimitedInventory, prepareCatalogImport } from "../src/services/catalogOnboarding.js";

const bytes = fs.readFileSync(new URL("../fixtures/test-5-excel-import.xlsx", import.meta.url));
const manifest = JSON.parse(fs.readFileSync(new URL("../fixtures/test-5-excel-import.json", import.meta.url), "utf8"));
const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
const text = await readXlsxInventory(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
const parsed = parseDelimitedInventory(text, new SourceBrain());
const rows = parseCatalogText(catalogItemsToText(parsed.items));
const reviewCard = createPasteImportCard(catalogItemsToText(parsed.items), {
  source: "test-5-excel-import.xlsx",
  method: "excel file",
  reviewFeedback: "Read 3 medicine(s) from Excel file test-5-excel-import.xlsx. Check every value. Nothing is saved until approval."
});
const repeatedImport = prepareCatalogImport(parsed.items, parsed.items);
const mixedImport = prepareCatalogImport([...parsed.items, { name: "Acyclovir", strength: "5%", form: "cream" }], parsed.items);
const assert = (condition, message) => { if (!condition) throw new Error(message); };

assert(parsed.aiRequired === false && parsed.unclear.length === 0, "XLSX parsing must be complete and zero-token");
assert(parsed.items.length === 3 && rows.length === 3, "XLSX fixture must produce three editable review rows");
assert(parsed.items.map((item) => item.name).join("|") === "Cetirizine|Co-Amoxiclav|Paracetamol", "XLSX source order and canonical medicine identities must survive");
assert(parsed.items.every((item) => item.source === "source_brain_match"), "Every fixture medicine must pass Source Brain");
assert(rows.every((item) => item.strength && item.pack_size && item.selling_price && item.cost_price && item.stock && item.supplier && item.batch && item.expiry && item.shelf), "All supported XLSX fields must reach shared review rows");
assert(rows.every((item) => !item.barcode), "Unsupported fixture barcodes must remain blank");
assert(manifest.expectedCatalogCountBeforeApproval === 32 && manifest.expectedCatalogCountAfterApproval === 35, "Fixture catalog boundary is stale");
assert(app.includes("readXlsxInventory(file)") && !app.includes("Excel binary parsing adapter is reserved"), "The live XLSX route must use the local adapter, not a placeholder");
assert(reviewCard.source === "test-5-excel-import.xlsx" && reviewCard.fields.method === "excel file", "The shared review card must retain XLSX acquisition provenance");
assert(reviewCard.fields.review_feedback.includes("Nothing is saved until approval"), "XLSX provenance must be visible in honest owner language");
assert(repeatedImport.hasNewItems === false && repeatedImport.newItems.length === 0 && repeatedImport.existing.length === 3, "Repeating the approved XLSX must produce no approvable rows");
assert(repeatedImport.existingNames.join("|") === "Cetirizine|Co-Amoxiclav|Paracetamol", "Repeat-import feedback must name the existing medicines");
assert(mixedImport.newItems.length === 1 && mixedImport.newItems[0].name === "Acyclovir" && mixedImport.existing.length === 3, "Mixed files must review only genuinely new medicines");
assert(app.includes('createFileImportReviewCard(parsed, name, "Excel", pharmacyBrain.catalog)'), "The live XLSX route must compare the file with the saved catalog before review");
assert(app.includes('card.fields.entry_mode = "no_changes"') && app.includes('card.fields?.entry_mode === "no_changes"'), "A repeat file must render a non-approvable no-changes result");
assert(app.includes("I could not read this older Excel file") && app.includes("Nothing was saved."), "Unsupported legacy XLS must fail honestly and safely");

console.log("Test 5 XLSX verification passed: local extraction, complete shared review fields, repeat-import suppression, mixed-file partitioning, honest blanks, and zero AI calls.");
