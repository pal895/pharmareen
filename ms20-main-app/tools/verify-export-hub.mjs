import assert from "node:assert/strict";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  EXPORT_FORMATS, buildCanonicalInventoryExport, buildInventoryCsv, buildInventoryDocx,
  buildInventoryPdf, buildInventoryPptx, buildInventoryXlsx, buildOwnerWorkbookSheets,
  buildPrintHtml, exportFilename, validateInventoryExportSnapshot
} from "../src/services/documentGenerator.js";
import { buildMedicineFinderIndex, searchMedicineFinder } from "../src/services/medicineFinder.js";

const pharmacy = { id: "pharmacy-a", name: "Zuri Pharmacy", branch: "Main", location: "Nairobi, Kenya" };
const items = [
  { name: "Amoxicillin", strength: "500 mg", forms: ["capsule"], units: ["capsule"], sellingPrice: 20, costPrice: 12, stockLeft: 40, reorderLevel: 50, supplier: "AfyaLink", barcode: "616000001", batches: [{ batch: "AMX-1", expiry: "2028-12" }], shelf: "A1" },
  { name: "Zinc Syrup", strength: "20 mg/5 ml", forms: ["syrup"], units: ["bottle"], sellingPrice: 70, costPrice: 45, stockLeft: 12, supplier: "Dawa Bora", barcode: "", batches: [{ batch: "ZIN-2", expiry: "2029-03" }], shelf: "B2" }
];
for (let index = 3; index <= 35; index += 1) items.push({
  name: `Medicine ${String(index).padStart(2, "0")}`, strength: `${index * 5} mg`, forms: ["tablet"], units: ["tablet"],
  sellingPrice: index * 2, costPrice: index, stockLeft: index + 10, supplier: "Verified Supplier",
  barcode: `616${String(index).padStart(9, "0")}`, batches: [{ batch: `BAT-${index}`, expiry: "2029-12" }], shelf: `S${index}`
});
const generatedAt = new Date("2026-07-25T18:00:32.000Z");
const model = buildCanonicalInventoryExport({ pharmacy, items, generatedAt });
const other = buildCanonicalInventoryExport({ pharmacy: { ...pharmacy, id: "pharmacy-b", name: "Other Pharmacy" }, items: [items[0]], generatedAt });
const healthyModel = buildCanonicalInventoryExport({ pharmacy, items: [items[1]], generatedAt });

assert.equal(model.pharmacyId, "pharmacy-a");
assert.equal(model.rows.length, 35);
assert.equal(model.summary.medicineCount, 35);
assert.equal(model.summary.retailStockValue, items.reduce((sum, item) => sum + item.sellingPrice * item.stockLeft, 0));
assert.equal(validateInventoryExportSnapshot(model), true);
assert.ok(Object.isFrozen(model) && Object.isFrozen(model.rows) && model.rows.every(Object.isFrozen));
assert.equal(other.rows.length, 1);
assert.notEqual(model.pharmacyId, other.pharmacyId);
assert.equal(model.generatedKenya.includes("21:00:32"), true);
assert.deepEqual(EXPORT_FORMATS.map((format) => format.id), ["xlsx", "pdf", "docx", "pptx", "print", "csv"]);
assert.deepEqual(EXPORT_FORMATS.filter((format) => format.group === "polished").map((format) => format.id), ["xlsx", "pdf", "docx", "pptx", "print"]);
assert.deepEqual(EXPORT_FORMATS.filter((format) => format.group === "data").map((format) => format.id), ["csv"]);
assert.match(EXPORT_FORMATS.find((format) => format.id === "csv").help, /no visual styling/i);
assert.throws(() => buildCanonicalInventoryExport({ pharmacy, items: [{ ...items[0], name: "" }], generatedAt }), /mandatory medicine name/);
assert.throws(() => buildCanonicalInventoryExport({ pharmacy, items: [items[0], { ...items[0] }], generatedAt }), /duplicate medicine identity/);
assert.throws(() => validateInventoryExportSnapshot({ ...model, summary: { ...model.summary, medicineCount: 714 } }), /medicineCount/);
const healthySheets = buildOwnerWorkbookSheets(healthyModel);
assert.ok(healthySheets[0].merges.includes("A20:D20"));
assert.match(healthySheets[0].rows[19][0], /No medicines currently require attention/);
assert.ok(healthySheets[2].merges.includes("A6:F6"));
assert.match(healthySheets[2].rows[5][0], /No medicines are currently below/);

const outputs = {
  csv: buildInventoryCsv(model), xlsx: buildInventoryXlsx(model), pdf: buildInventoryPdf(model),
  docx: buildInventoryDocx(model), pptx: buildInventoryPptx(model), html: buildPrintHtml(model)
};
assert.deepEqual(
  buildInventoryXlsx(buildCanonicalInventoryExport({ pharmacy, items, generatedAt })),
  outputs.xlsx,
  "Identical immutable input must produce deterministic XLSX bytes"
);
assert.deepEqual(
  buildInventoryPdf(buildCanonicalInventoryExport({ pharmacy, items, generatedAt })),
  outputs.pdf,
  "Identical immutable input must produce deterministic PDF bytes"
);
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
assert.equal((outputs.html.match(/class="print-sheet"/g) || []).length, 4);
assert.equal((outputs.html.match(/class="record-main"/g) || []).length, 35);
assert.match(outputs.html, /font-size:9\.5px/);
assert.match(outputs.html, /Page 4 of 4/);
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
assert.equal(exportFilename(model, "xlsx"), "zuri-pharmacy-inventory-2026-07-25-180032Z.xlsx");

const decodedPackages = Object.fromEntries(["xlsx", "docx", "pptx"].map((format) => [format, new TextDecoder().decode(outputs[format])]));
const decodedPdf = new TextDecoder().decode(outputs.pdf);
const ownerSheets = buildOwnerWorkbookSheets(model);
assert.ok(ownerSheets.every((sheet) => sheet.sourceCount === 35), "Every worksheet must reference the same 35-medicine snapshot");
assert.ok(ownerSheets.every((sheet) => sheet.rows.some((row) => row.some((value) => String(value).includes("35 canonical medicines")))), "Every worksheet must visibly declare the same source count");
assert.equal(ownerSheets.find((sheet) => sheet.name === "Full Inventory").projectionCount, 35);
assert.equal(ownerSheets.find((sheet) => sheet.name === "Expiry Tracking").projectionCount, 35);
assert.equal(ownerSheets.find((sheet) => sheet.name === "Suppliers").projectionCount, 35);
assert.deepEqual(ownerSheets.map((sheet) => sheet.name), ["Overview", "Full Inventory", "Low Stock", "Expiry Tracking", "Suppliers"]);
assert.deepEqual(ownerSheets.map((sheet) => sheet.rows[0][0]), ["Pharmacy Overview", "Full Inventory", "Low Stock", "Expiry Tracking", "Suppliers"]);
assert.equal(new Set(ownerSheets.map((sheet) => sheet.rows[0][0])).size, 5);
assert.deepEqual(ownerSheets[0].rows.slice(10, 17), [
  ["Total medicines", model.summary.medicineCount],
  ["Total units in stock", model.summary.totalStock],
  ["Total stock value (KES)", model.summary.retailStockValue],
  ["Cost stock value (KES)", model.summary.costStockValue],
  ["Potential gross margin (KES)", model.summary.potentialGrossMargin],
  ["Low stock count", model.summary.lowStockCount],
  ["Expiring soon count", model.summary.expiringSoonCount]
]);
assert.deepEqual(ownerSheets[0].rows.slice(4, 9).map((row) => row[0]), ["Overview", "Full Inventory", "Low Stock", "Expiry Tracking", "Suppliers"]);
assert.deepEqual(ownerSheets[0].rows[18], ["Medicine", "Stock", "Expiry", "Reason"]);
assert.ok(ownerSheets[0].widths.reduce((sum, width) => sum + width, 0) <= 46, "Overview must fit a compact phone viewport");
assert.equal(ownerSheets[0].rows.some((row) => row.includes("Supplier") || row.includes("Shelf")), false);
assert.deepEqual(ownerSheets.find((sheet) => sheet.name === "Full Inventory").rows[4], [
  "Medicine", "Strength", "Form", "Unit", "Stock", "Selling price (KES)", "Cost price (KES)",
  "Retail stock value (KES)", "Expiry", "Supplier", "Shelf", "Batch", "Barcode"
]);
assert.deepEqual(ownerSheets.find((sheet) => sheet.name === "Low Stock").rows[4], ["Medicine", "Current stock", "Reorder level", "Suggested reorder quantity", "Supplier", "Reason"]);
assert.deepEqual(ownerSheets.find((sheet) => sheet.name === "Expiry Tracking").rows[4], ["Medicine", "Expiry date", "Urgency", "Stock", "Batch", "Supplier", "Recommended action"]);
assert.deepEqual(ownerSheets.find((sheet) => sheet.name === "Suppliers").rows[4], ["Supplier", "Medicine", "Stock", "Cost price (KES)", "Last known batch"]);
for (const sheet of ownerSheets) {
  assert.ok(sheet.rows[sheet.headerRow - 1].every((value) => String(value).trim()), `${sheet.name} contains a blank mandatory header`);
  const targets = new Set(sheet.hyperlinks.map((link) => link.location));
  for (const target of ["Overview", "Full Inventory", "Low Stock", "Expiry Tracking", "Suppliers"]) {
    assert.ok(targets.has(`'${target}'!A1`), `${sheet.name} must link to ${target}!A1`);
  }
}
assert.equal((decodedPackages.xlsx.match(/<sheet name="/g) || []).length, 5);
for (const sheetName of ["Overview", "Full Inventory", "Low Stock", "Expiry Tracking", "Suppliers"]) {
  assert.match(decodedPackages.xlsx, new RegExp(`<sheet name="${sheetName}"`), `XLSX missing ${sheetName}`);
}
for (const title of ["Pharmacy Overview", "Full Inventory", "Low Stock", "Expiry Tracking", "Suppliers"]) {
  assert.match(decodedPackages.xlsx, new RegExp(`>${title}<`), `XLSX missing visible title ${title}`);
}
assert.doesNotMatch(decodedPackages.xlsx, /<pane\b|xSplit=|ySplit=/, "No worksheet may contain a frozen column or split pane");
assert.equal((decodedPackages.xlsx.match(/showGridLines="0"/g) || []).length, 5);
assert.equal((decodedPackages.xlsx.match(/showRowColHeaders="0"/g) || []).length, 5);
assert.equal((decodedPackages.xlsx.match(/topLeftCell="A1"/g) || []).length, 5);
assert.equal((decodedPackages.xlsx.match(/activeCell="A1" sqref="A1"/g) || []).length, 5);
assert.equal((decodedPackages.xlsx.match(/zoomScale="90"/g) || []).length, 5);
assert.equal((decodedPackages.xlsx.match(/<hyperlink /g) || []).length, 29, "Overview needs five links and every detail sheet needs six");
for (const target of ["Overview", "Full Inventory", "Low Stock", "Expiry Tracking", "Suppliers"]) {
  assert.match(decodedPackages.xlsx, new RegExp(`location="&apos;${target}&apos;!A1"`), `XLSX missing internal link to ${target}!A1`);
}
assert.doesNotMatch(decodedPackages.xlsx, /r:id="[^"]+"[^>]*location=/, "Internal worksheet links must not become external relationships");
assert.equal((decodedPackages.xlsx.match(/<autoFilter ref=/g) || []).length, 4, "Every working data sheet must retain filters");
assert.match(decodedPackages.xlsx, /<dimension ref="A1:D20"\/>/);
assert.match(decodedPackages.xlsx, /<dimension ref="A1:M40"\/>/);
assert.match(decodedPackages.xlsx, /<dimension ref="A1:F6"\/>/);
assert.match(decodedPackages.xlsx, /<dimension ref="A1:G40"\/>/);
assert.match(decodedPackages.xlsx, /<dimension ref="A1:E40"\/>/);
assert.doesNotMatch(decodedPackages.xlsx, /<pageSetup\b|<printOptions\b|<pageMargins\b/);
assert.match(decodedPackages.xlsx, /<TitlesOfParts>/);
for (const sheetName of ["Overview", "Full Inventory", "Low Stock", "Expiry Tracking", "Suppliers"]) {
  assert.match(decodedPackages.xlsx, new RegExp(`<vt:lpstr>${sheetName}</vt:lpstr>`), `Workbook metadata missing ${sheetName}`);
}
assert.match(decodedPackages.xlsx, /Low stock/);
assert.match(decodedPackages.xlsx, /At or below reorder level/);
assert.match(decodedPackages.xlsx, /Total stock value \(KES\)/);
assert.match(decodedPackages.xlsx, /Expiring soon count/);
assert.match(decodedPackages.xlsx, /Last known batch/);
assert.match(decodedPackages.xlsx, /fgColor rgb="FFF1F7F5"/);
assert.match(decodedPackages.xlsx, /wrapText="1" vertical="center"/);
for (const item of items) {
  assert.match(outputs.csv, new RegExp(item.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")), `CSV missing ${item.name}`);
  for (const format of ["xlsx", "docx", "pptx"]) {
    assert.match(decodedPackages[format], new RegExp(item.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")), `${format.toUpperCase()} missing ${item.name}`);
  }
  assert.match(decodedPdf, new RegExp(item.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")), `PDF missing ${item.name}`);
  assert.match(outputs.html, new RegExp(`class="record-main"[\\s\\S]*?${item.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`), `Print missing ${item.name}`);
}
assert.equal((decodedPackages.pptx.match(/<p:sldId /g) || []).length, 8);
assert.equal((decodedPackages.docx.match(/w:type="page"/g) || []).length, 6);
assert.equal((decodedPdf.match(/\/Type \/Page\b/g) || []).length, 8);
assert.equal((decodedPdf.match(/\/MediaBox \[0 0 595 842\]/g) || []).length, 8);
assert.match(decodedPdf, /Pharmacy Overview/);
assert.match(decodedPdf, /At a glance/);
assert.match(decodedPdf, /Medicines 1-5 of 35/);
assert.match(decodedPdf, /Medicines 31-35 of 35/);
for (const match of decodedPackages.pptx.matchAll(/<a:off x="(\d+)" y="(\d+)"\/><a:ext cx="(\d+)" cy="(\d+)"\/>/g)) {
  const [, x, y, width, height] = match.map(Number);
  assert.ok(x + width <= 12192000, `PPTX shape overflows horizontally: ${x + width}`);
  assert.ok(y + height <= 6858000, `PPTX shape overflows vertically: ${y + height}`);
}

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
assert.match(appSource, /Choose Excel for editing and analysis, or PDF for the easiest phone reading and sharing\. No confirmation is required\./);
assert.match(appSource, /Choose Excel when you want to search, filter, edit or analyze your complete pharmacy inventory\. For the easiest phone reading and sharing experience, choose PDF\./);
assert.match(appSource, /For the best experience, open this file in Microsoft Excel or Google Sheets\./);
assert.match(appSource, /<h3>Polished owner copies<\/h3>/);
assert.match(appSource, /<h3>Technical data transfer<\/h3>/);
assert.match(appSource, /CSV preserves the records for other systems, but it cannot carry colours, fonts, spacing or page design\./);
assert.match(cssSource, /\.export-data-section/);
assert.match(appSource, /state\.printPreview = \{ model, bridgeId, query: "", message: "" \}/);
assert.match(appSource, /printFrame\.srcdoc = buildPrintHtml/);
assert.match(appSource, /window\.__ms20FinderRequest/);
assert.match(appSource, /refreshPrintPreviewDom/);
assert.match(appSource, /cameraOverlayIsRendered === state\.camera\.open/);
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

const outputDir = join(process.cwd(), ".export-hub-verification", "artifacts");
await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });
await Promise.all([
  writeFile(join(outputDir, exportFilename(model, "csv")), outputs.csv), writeFile(join(outputDir, exportFilename(model, "xlsx")), outputs.xlsx),
  writeFile(join(outputDir, exportFilename(model, "pdf")), outputs.pdf), writeFile(join(outputDir, exportFilename(model, "docx")), outputs.docx),
  writeFile(join(outputDir, exportFilename(model, "pptx")), outputs.pptx), writeFile(join(outputDir, exportFilename(model, "print.html")), outputs.html)
]);
console.log(`Export Hub verification passed: 35 canonical records in six formats, pharmacy isolation, balanced pagination, fresh filenames, deterministic zero-AI renderers. 4,200-record finder index ${buildMs.toFixed(1)} ms; exact search ${searchMs.toFixed(1)} ms. Artifacts: ${outputDir}`);
