import fs from "node:fs";
import { SourceBrain } from "../src/services/brainAdapters.js";
import { readXlsxInventory } from "../src/services/excelInventory.js";
import { catalogItemsToText, parseCatalogText, parseDelimitedInventory } from "../src/services/catalogOnboarding.js";

const bytes = fs.readFileSync(new URL("../fixtures/test-5-excel-import.xlsx", import.meta.url));
const manifest = JSON.parse(fs.readFileSync(new URL("../fixtures/test-5-excel-import.json", import.meta.url), "utf8"));
const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
const text = await readXlsxInventory(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
const parsed = parseDelimitedInventory(text, new SourceBrain());
const rows = parseCatalogText(catalogItemsToText(parsed.items));
const assert = (condition, message) => { if (!condition) throw new Error(message); };

assert(parsed.aiRequired === false && parsed.unclear.length === 0, "XLSX parsing must be complete and zero-token");
assert(parsed.items.length === 3 && rows.length === 3, "XLSX fixture must produce three editable review rows");
assert(parsed.items.map((item) => item.name).join("|") === "Cetirizine|Co-Amoxiclav|Paracetamol", "XLSX source order and canonical medicine identities must survive");
assert(parsed.items.every((item) => item.source === "source_brain_match"), "Every fixture medicine must pass Source Brain");
assert(rows.every((item) => item.strength && item.pack_size && item.selling_price && item.cost_price && item.stock && item.supplier && item.batch && item.expiry && item.shelf), "All supported XLSX fields must reach shared review rows");
assert(rows.every((item) => !item.barcode), "Unsupported fixture barcodes must remain blank");
assert(manifest.expectedCatalogCountBeforeApproval === 32 && manifest.expectedCatalogCountAfterApproval === 35, "Fixture catalog boundary is stale");
assert(app.includes("readXlsxInventory(file)") && !app.includes("Excel binary parsing adapter is reserved"), "The live XLSX route must use the local adapter, not a placeholder");
assert(app.includes("I could not read this older Excel file") && app.includes("Nothing was saved."), "Unsupported legacy XLS must fail honestly and safely");

console.log("Test 5 XLSX verification passed: local extraction, three Source Brain rows, complete shared review fields, honest blanks, and zero AI calls.");
