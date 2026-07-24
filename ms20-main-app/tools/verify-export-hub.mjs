import assert from "node:assert/strict";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  EXPORT_FORMATS, buildCanonicalInventoryExport, buildInventoryCsv, buildInventoryDocx,
  buildInventoryPdf, buildInventoryPptx, buildInventoryXlsx, buildPrintHtml, exportFilename
} from "../src/services/documentGenerator.js";

const pharmacy = { id: "pharmacy-a", name: "Zuri Pharmacy", branch: "Main", location: "Nairobi, Kenya" };
const items = [
  { name: "Amoxicillin", strength: "500 mg", forms: ["capsule"], units: ["capsule"], sellingPrice: 20, costPrice: 12, stockLeft: 40, supplier: "AfyaLink", barcode: "616000001", batches: [{ batch: "AMX-1", expiry: "2028-12" }], shelf: "A1" },
  { name: "Zinc Syrup", strength: "20 mg/5 ml", forms: ["syrup"], units: ["bottle"], sellingPrice: 70, costPrice: 45, stockLeft: 12, supplier: "Dawa Bora", barcode: "", batches: [{ batch: "ZIN-2", expiry: "2029-03" }], shelf: "B2" }
];
for (let index = 3; index <= 35; index += 1) items.push({
  name: `Medicine ${String(index).padStart(2, "0")}`, strength: `${index * 5} mg`, forms: ["tablet"], units: ["tablet"],
  sellingPrice: index * 2, costPrice: index, stockLeft: index + 10, supplier: "Verified Supplier",
  barcode: `616${String(index).padStart(9, "0")}`, batches: [{ batch: `BAT-${index}`, expiry: "2029-12" }], shelf: `S${index}`
});
const generatedAt = new Date("2026-07-19T17:00:32.000Z");
const model = buildCanonicalInventoryExport({ pharmacy, items, generatedAt });
const other = buildCanonicalInventoryExport({ pharmacy: { ...pharmacy, id: "pharmacy-b", name: "Other Pharmacy" }, items: [items[0]], generatedAt });

assert.equal(model.pharmacyId, "pharmacy-a");
assert.equal(model.rows.length, 35);
assert.equal(other.rows.length, 1);
assert.notEqual(model.pharmacyId, other.pharmacyId);
assert.equal(model.generatedKenya.includes("20:00:32"), true);
assert.deepEqual(EXPORT_FORMATS.map((format) => format.id), ["csv", "xlsx", "pdf", "docx", "pptx", "print"]);

const outputs = {
  csv: buildInventoryCsv(model), xlsx: buildInventoryXlsx(model), pdf: buildInventoryPdf(model),
  docx: buildInventoryDocx(model), pptx: buildInventoryPptx(model), html: buildPrintHtml(model)
};
assert.match(outputs.csv, /^\ufeffMS2\.0 Pharmacy Inventory/);
assert.match(outputs.csv, /Amoxicillin,500 mg,capsule,capsule,20,12,40/);
assert.equal(new TextDecoder().decode(outputs.pdf.slice(0, 8)), "%PDF-1.4");
for (const format of ["xlsx", "docx", "pptx"]) assert.equal(new TextDecoder().decode(outputs[format].slice(0, 2)), "PK");
assert.match(outputs.html, /Generated locally by MS2\.0 with no AI formatting/);
assert.match(outputs.html, /name="viewport" content="width=device-width,initial-scale=1"/);
assert.match(outputs.html, /Review before printing/);
assert.match(outputs.html, /data-label="Medicine">Amoxicillin/);
assert.match(outputs.html, /@media\(max-width:720px\)/);
assert.match(outputs.html, /@media print/);
assert.match(outputs.html, /Close view/);
assert.match(outputs.html, /Find a medicine/);
assert.match(outputs.html, /Name, supplier, barcode or shelf/);
assert.match(outputs.html, /class="medicine-card"[^>]*data-search=/);
assert.match(outputs.html, /35 medicines shown · Tap a medicine to view every field/);
assert.match(outputs.html, /card\.hidden=!card\.dataset\.search\.includes\(query\)/);
assert.equal(exportFilename(model, "xlsx"), "zuri-pharmacy-inventory-2026-07-19.xlsx");

const source = await readFile(new URL("../src/services/documentGenerator.js", import.meta.url), "utf8");
assert.doesNotMatch(source, /fetch\s*\(|OpenAI|chat\.completions|responses\.create/);
const appSource = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
const cssSource = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");
assert.match(appSource, /data-action="open-export-hub">Export Hub/);
assert.match(appSource, /buildCanonicalInventoryExport\(\{ pharmacy: state\.pharmacy, items: pharmacyBrain\.catalog \}\)/);
assert.match(appSource, /download-inventory-export/);
assert.match(appSource, /card\.type === "CatalogWorkspaceCard" \|\| card\.type === "ExportHubCard"/);
assert.match(appSource, /card\.type === "ExportHubCard"\) return "Choose a format to download\. No confirmation is required\."/);
assert.match(appSource, /URL\.createObjectURL\(new Blob\(\[printHtml\]/);
assert.doesNotMatch(appSource, /printWindow\.document\.write/);
assert.doesNotMatch(appSource, /Export Hub[\s\S]{0,1000}(OpenAI|fetch\s*\()/);
assert.match(cssSource, /@media \(max-width: 520px\)[^{]*\{[^}]*\.export-format-grid/);

const outputDir = join(process.cwd(), ".export-hub-verification");
await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });
await Promise.all([
  writeFile(join(outputDir, "inventory.csv"), outputs.csv), writeFile(join(outputDir, "inventory.xlsx"), outputs.xlsx),
  writeFile(join(outputDir, "inventory.pdf"), outputs.pdf), writeFile(join(outputDir, "inventory.docx"), outputs.docx),
  writeFile(join(outputDir, "inventory.pptx"), outputs.pptx), writeFile(join(outputDir, "inventory-print.html"), outputs.html)
]);
console.log(`Export Hub verification passed: canonical model, pharmacy isolation, six formats, deterministic zero-AI renderers. Artifacts: ${outputDir}`);
