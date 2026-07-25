import assert from "node:assert/strict";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  EXPORT_FORMATS, buildCanonicalInventoryExport, buildInventoryCsv, buildInventoryDocx,
  buildInventoryPdf, buildInventoryPptx, buildInventoryXlsx, buildPrintHtml, exportFilename
} from "../src/services/documentGenerator.js";
import { buildMedicineFinderIndex, searchMedicineFinder } from "../src/services/medicineFinder.js";

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
assert.match(outputs.html, /Fast medicine finder/);
assert.match(outputs.html, /Scan barcode/);
assert.match(outputs.html, /Speak medicine/);
assert.match(outputs.html, /Type only if needed/);
assert.match(outputs.html, /Name, alias, strength, form, unit, barcode, supplier, shelf or batch/);
assert.match(outputs.html, /class="medicine-card"[^>]*data-finder-id=/);
assert.match(outputs.html, /35 of 35 medicines shown/);
assert.match(outputs.html, /ms20:finder-request/);
assert.match(outputs.html, /result=>wanted\?result\.value>=54:result\.value>0/);
assert.match(outputs.html, /BroadcastChannel/);
assert.match(outputs.html, /finder-status/);
assert.equal(exportFilename(model, "xlsx"), "zuri-pharmacy-inventory-2026-07-19.xlsx");

const finderFixture = [
  { name: "Paracetamol", aliases: ["Panadol"], strength: "500 mg", forms: ["tablet"], units: ["tablet"], barcode: "616111", supplier: "EastCare Pharma", shelf: "D3", batches: [{ batch: "PAR-500C", expiry: "2026-09" }], stockLeft: 4, reorderLevel: 5 },
  { name: "Ibuprofen", aliases: ["Brufen"], strength: "200 mg", forms: ["tablet"], units: ["tablet"], barcode: "616222", supplier: "AfyaLink", shelf: "C3", stockLeft: 0, reorderLevel: 5 }
];
const finderIndex = buildMedicineFinderIndex(finderFixture, { now: generatedAt });
for (const query of ["Paracetamol", "Panadol", "Paracetmol", "500 mg", "616111", "EastCare", "D3", "PAR-500C"]) {
  assert.equal(searchMedicineFinder(finderIndex, query)[0]?.name, "Paracetamol", `Finder failed for ${query}`);
}
assert.ok(searchMedicineFinder(finderIndex, "tablet").some((entry) => entry.name === "Paracetamol"));
assert.deepEqual(searchMedicineFinder(finderIndex, "", { filter: "lowStock" }).map((entry) => entry.name), ["Ibuprofen", "Paracetamol"]);
assert.deepEqual(searchMedicineFinder(finderIndex, "", { filter: "outOfStock" }).map((entry) => entry.name), ["Ibuprofen"]);
assert.deepEqual(searchMedicineFinder(finderIndex, "", { filter: "expiringSoon" }).map((entry) => entry.name), ["Paracetamol"]);
assert.equal(searchMedicineFinder(finderIndex, "").length, 2);

const scaleItems = Array.from({ length: 4200 }, (_, index) => ({
  id: `scale-${index}`, name: `Scale Medicine ${index}`, aliases: [`SM${index}`], strength: `${index + 1} mg`,
  forms: ["tablet"], units: ["tablet"], barcode: `900${String(index).padStart(9, "0")}`,
  supplier: `Supplier ${index % 20}`, shelf: `S${index % 200}`, batches: [{ batch: `B${index}`, expiry: "2028-12" }],
  stockLeft: index % 50, reorderLevel: 5
}));
const scaleStart = performance.now();
const scaleIndex = buildMedicineFinderIndex(scaleItems, { now: generatedAt });
const buildMs = performance.now() - scaleStart;
const searchStart = performance.now();
assert.equal(searchMedicineFinder(scaleIndex, "Scale Medicine 4199")[0]?.name, "Scale Medicine 4199");
const searchMs = performance.now() - searchStart;
assert.equal(scaleIndex.length, 4200);
assert.ok(buildMs < 1000, `4,200-record index build took ${buildMs.toFixed(1)} ms`);
assert.ok(searchMs < 150, `4,200-record search took ${searchMs.toFixed(1)} ms`);

const source = await readFile(new URL("../src/services/documentGenerator.js", import.meta.url), "utf8");
const finderSource = await readFile(new URL("../src/services/medicineFinder.js", import.meta.url), "utf8");
assert.doesNotMatch(`${source}\n${finderSource}`, /fetch\s*\(|OpenAI|chat\.completions|responses\.create/);
const appSource = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
const cssSource = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");
const provenance = JSON.parse(await readFile(new URL("../provenance-registry.json", import.meta.url), "utf8"));
assert.equal(provenance.schema, "ms20.provenance-registry.v1");
assert.ok(provenance.entries.some((entry) => entry.name === "MS2.0 shared medicine finder" && entry.review_status === "approved"));
assert.ok(provenance.entries.every((entry) => entry.source && entry.licence && entry.approved_use && entry.proof && entry.owner));
assert.match(appSource, /data-action="open-export-hub">Export Hub/);
assert.match(appSource, /buildCanonicalInventoryExport\(\{ pharmacy: state\.pharmacy, items: pharmacyBrain\.catalog \}\)/);
assert.match(appSource, /download-inventory-export/);
assert.match(appSource, /card\.type === "CatalogWorkspaceCard" \|\| card\.type === "ExportHubCard"/);
assert.match(appSource, /card\.type === "ExportHubCard"\) return "Choose a format to download\. No confirmation is required\."/);
assert.match(appSource, /state\.printPreview = \{ model, bridgeId, query: "", message: "" \}/);
assert.match(appSource, /printFrame\.srcdoc = buildPrintHtml/);
assert.match(appSource, /window\.__ms20FinderRequest/);
assert.match(appSource, /startVoiceCapture\(/);
assert.match(appSource, /shared_voice_capture/);
assert.match(appSource, /openLightweightCamera\("barcode"\)/);
assert.match(appSource, /handleFinderRequest/);
assert.match(appSource, /Camera could not open\. Allow camera access in browser settings/);
assert.match(appSource, /getUserMedia\(\{ audio: true, video: false \}\)/);
assert.match(appSource, /Microphone access was denied\. Allow it in browser settings/);
assert.match(appSource, /Microphone did not start\. Tap Speak medicine to retry/);
assert.doesNotMatch(appSource, /printWindow\.document\.write/);
assert.doesNotMatch(appSource, /Export Hub[\s\S]{0,1000}(OpenAI|fetch\s*\()/);
assert.match(cssSource, /@media \(max-width: 520px\)[^{]*\{[^}]*\.export-format-grid/);
assert.match(cssSource, /\.print-preview-overlay/);

const outputDir = join(process.cwd(), ".export-hub-verification");
await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });
await Promise.all([
  writeFile(join(outputDir, "inventory.csv"), outputs.csv), writeFile(join(outputDir, "inventory.xlsx"), outputs.xlsx),
  writeFile(join(outputDir, "inventory.pdf"), outputs.pdf), writeFile(join(outputDir, "inventory.docx"), outputs.docx),
  writeFile(join(outputDir, "inventory.pptx"), outputs.pptx), writeFile(join(outputDir, "inventory-print.html"), outputs.html)
]);
console.log(`Export Hub verification passed: canonical model, pharmacy isolation, six formats, deterministic zero-AI renderers. 4,200-record finder index ${buildMs.toFixed(1)} ms; exact search ${searchMs.toFixed(1)} ms. Artifacts: ${outputDir}`);
