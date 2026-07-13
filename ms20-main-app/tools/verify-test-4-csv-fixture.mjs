import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SourceBrain } from "../src/services/brainAdapters.js";
import { catalogItemsToText, parseCatalogText, parseDelimitedInventory } from "../src/services/catalogOnboarding.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const csv = fs.readFileSync(path.join(root, "fixtures/test-4-csv-import.csv"), "utf8");
const parsed = parseDelimitedInventory(csv, new SourceBrain());
const expectedNames = ["Aspirin", "Atenolol", "Erythromycin", "Folic Acid"];
const assert = (condition, message) => { if (!condition) throw new Error(message); };

assert(parsed.aiRequired === false, "CSV fixture parsing must remain zero-token");
assert(parsed.unclear.length === 0, "CSV fixture must not contain unclear rows");
assert(parsed.items.length === 4, "CSV fixture must produce exactly four review rows");
assert(parsed.items.map((item) => item.name).join("|") === expectedNames.join("|"), "CSV fixture must preserve its four Source Brain identities and order");
assert(parsed.items.every((item) => item.source === "source_brain_match"), "Every CSV fixture medicine must be recognized by Source Brain");
assert(parsed.items.map((item) => item.strength).join("|") === "75 mg|50 mg|250 mg|5 mg", "CSV fixture strengths must map into the editable review rows");
const reviewRows = parseCatalogText(catalogItemsToText(parsed.items));
assert(reviewRows.map((item) => item.strength).join("|") === "75 mg|50 mg|250 mg|5 mg", "CSV strengths must survive intermediate review-card serialization");
assert(parsed.items.every((item) => item.form === "tablet" && item.unit === "tablet"), "CSV fixture form and unit mapping must remain exact");
assert(parsed.items.every((item) => item.selling_price && item.cost_price && item.stock && item.batch && item.expiry), "CSV fixture commercial and traceability fields must map into review");

console.log("Test 4 CSV fixture verification passed: four new Source Brain medicines, complete mapped review fields, zero AI calls.");
