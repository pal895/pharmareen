import assert from "node:assert/strict";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  EXPORT_FORMATS, buildCanonicalInventoryExport, buildInventoryCsv, buildInventoryDocx,
  buildInventoryPdf, buildInventoryPptx, buildInventoryXlsx, buildOwnerWorkbookSheets,
  buildPrintHtml, exportFilename, protectCsvSpreadsheetText, validateInventoryExportSnapshot, validateInventoryPptxPackage
} from "../src/services/documentGenerator.js";
import { exportCompletionSummary, exportFormat } from "../src/services/exportFormatMetadata.js";
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
assert.equal(new Set(EXPORT_FORMATS.map((format) => format.purpose)).size, EXPORT_FORMATS.length);
assert.ok(EXPORT_FORMATS.every((format) => format.cardHelp && format.purpose && format.recommendedApplication && format.nextAction));
for (const format of EXPORT_FORMATS) {
  for (const key of ["id", "label", "extension", "mime", "purpose", "recommendedApplication", "fallbackApplications", "nextAction", "historyDescription", "completionWording", "regenerationWording", "icon", "createsFile", "downloadCapability", "printBehavior", "safetyNotes", "expiryBehavior", "accessibilityLabel"]) {
    assert.ok(Object.hasOwn(format, key), `${format.id} metadata is missing ${key}`);
  }
  assert.equal(exportFormat(format.id), format);
}
assert.match(EXPORT_FORMATS.find((format) => format.id === "xlsx").purpose, /Analyze, filter, reconcile/i);
assert.match(EXPORT_FORMATS.find((format) => format.id === "pdf").purpose, /read-only phone sharing/i);
assert.match(EXPORT_FORMATS.find((format) => format.id === "docx").purpose, /Review, correct, approve/i);
assert.match(EXPORT_FORMATS.find((format) => format.id === "pptx").cardHelp, /management, staff, suppliers, investors or lenders/i);
assert.match(EXPORT_FORMATS.find((format) => format.id === "csv").purpose, /another system or import workflow/i);
assert.equal(exportCompletionSummary("pptx", "completed", 35), "Presentation completed — 35 medicines");
assert.equal(exportCompletionSummary("csv", "completed", 35), "CSV completed — 35 medicines");
assert.equal(exportCompletionSummary("print", "print_dialog_opened"), "Print dialog opened");
assert.equal(protectCsvSpreadsheetText("=1+1"), "'=1+1");
assert.equal(protectCsvSpreadsheetText(" @SUM(A1:A2)"), "' @SUM(A1:A2)");
assert.equal(protectCsvSpreadsheetText("001234"), "001234");
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
const csvSecurityModel = buildCanonicalInventoryExport({
  pharmacy: { id: "csv-security", name: "Afya, Dawa Pharmacy", branch: "Main", location: "Nairobi, Kenya" },
  items: [
    {
      name: '=HYPERLINK("https://invalid.example","Dawa")', strength: "5 mg\nextended", forms: ["tablet"],
      units: ["tablet"], sellingPrice: 12.5, costPrice: 3.75, stockLeft: 1000000,
      supplier: 'Dawa "Bora", Nairobi', barcode: "001234567890",
      batches: [{ batch: "+CMD", expiry: "2029-12" }], shelf: "@A-01"
    },
    {
      name: "Café dawa – watoto", strength: "", forms: ["syrup"], units: ["bottle"],
      sellingPrice: 0, costPrice: "", stockLeft: 0, supplier: "O'Connell Pharma",
      barcode: "000000000007", batches: [], shelf: ""
    }
  ],
  generatedAt
});
const securedCsv = buildInventoryCsv(csvSecurityModel);
function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  const source = text.replace(/^\ufeff/, "");
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if (quoted) {
      if (character === '"' && source[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        cell += character;
      }
    } else if (character === '"') {
      quoted = true;
    } else if (character === ",") {
      row.push(cell);
      cell = "";
    } else if (character === "\r" && source[index + 1] === "\n") {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      index += 1;
    } else {
      cell += character;
    }
  }
  assert.equal(quoted, false, "CSV contains an unmatched quote");
  assert.equal(row.length, 0, "CSV must end with CRLF and no partial record");
  return rows;
}
const parsedCsv = parseCsv(outputs.csv);
const parsedSecuredCsv = parseCsv(securedCsv);
const canonicalHeader = ["Medicine", "Strength", "Form", "Unit", "Selling price (KES)", "Cost price (KES)", "Stock", "Supplier", "Barcode", "Batch", "Expiry", "Shelf"];
assert.deepEqual(parsedCsv[0], canonicalHeader);
assert.equal(parsedCsv.length, 36);
assert.ok(parsedCsv.every((row) => row.length === canonicalHeader.length));
assert.deepEqual(parsedCsv[1], ["Amoxicillin", "500 mg", "capsule", "capsule", "20", "12", "40", "AfyaLink", "616000001", "AMX-1", "2028-12", "A1"]);
assert.equal(parsedSecuredCsv.length, 3);
assert.ok(parsedSecuredCsv.every((row) => row.length === canonicalHeader.length));
assert.equal(parsedSecuredCsv[1][0], '\'=HYPERLINK("https://invalid.example","Dawa")');
assert.equal(parsedSecuredCsv[1][1], "5 mg extended");
assert.equal(parsedSecuredCsv[1][7], 'Dawa "Bora", Nairobi');
assert.equal(parsedSecuredCsv[1][8], "'001234567890");
assert.equal(parsedSecuredCsv[2][8], "'000000000007");
assert.ok(securedCsv.startsWith("\ufeffMedicine,Strength,Form,Unit,Selling price (KES),Cost price (KES),Stock,Supplier,Barcode,Batch,Expiry,Shelf\r\n"));
assert.equal(securedCsv.endsWith("\r\n"), true);
assert.equal(securedCsv.includes("\0"), false);
assert.equal(securedCsv.replaceAll("\r\n", "").includes("\n"), false);
assert.match(securedCsv, /"'=HYPERLINK\(""https:\/\/invalid\.example"",""Dawa""\)"/);
assert.match(securedCsv, /5 mg extended/);
assert.match(securedCsv, /"Dawa ""Bora"", Nairobi"/);
assert.match(securedCsv, /,'\+CMD,/);
assert.match(securedCsv, /,'@A-01/);
assert.match(securedCsv, /'001234567890/);
assert.match(securedCsv, /'000000000007/);
assert.match(securedCsv, /Café dawa – watoto/);
assert.match(securedCsv, /O'Connell Pharma/);
assert.match(securedCsv, /,12\.5,3\.75,1000000,/);
assert.match(securedCsv, /,0,,0,/);
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
assert.deepEqual(
  buildInventoryDocx(buildCanonicalInventoryExport({ pharmacy, items, generatedAt })),
  outputs.docx,
  "Identical immutable input must produce deterministic DOCX bytes"
);
assert.deepEqual(
  buildInventoryPptx(buildCanonicalInventoryExport({ pharmacy, items, generatedAt })),
  outputs.pptx,
  "Identical immutable input must produce deterministic PPTX bytes"
);
assert.deepEqual(validateInventoryPptxPackage(outputs.pptx), { valid: true, entryCount: 29, slideCount: 9 });
assert.throws(() => validateInventoryPptxPackage(outputs.pptx.slice(0, -8)), /end record is missing or truncated/);
const zeroAndMissingPdf = new TextDecoder().decode(buildInventoryPdf(buildCanonicalInventoryExport({
  pharmacy,
  items: [{ name: "Zero Stock Example", stockLeft: 0, sellingPrice: 0, costPrice: "", supplier: "", barcode: "", batches: [], shelf: "" }],
  generatedAt
})));
const zeroAndMissingDocx = new TextDecoder().decode(buildInventoryDocx(buildCanonicalInventoryExport({
  pharmacy,
  items: [{ name: "Zero Stock Example", stockLeft: 0, sellingPrice: 0, costPrice: "", supplier: "", barcode: "", batches: [], shelf: "" }],
  generatedAt
})));
const missingStockDocx = new TextDecoder().decode(buildInventoryDocx(buildCanonicalInventoryExport({
  pharmacy,
  items: [{ name: "Missing Stock Example", stockLeft: "", sellingPrice: 10, costPrice: 5, supplier: "", barcode: "", batches: [], shelf: "" }],
  generatedAt
})));
assert.match(zeroAndMissingPdf, /Stock 0/);
assert.match(zeroAndMissingPdf, /Selling KES 0 \| Cost KES Not recorded/);
assert.match(zeroAndMissingPdf, /Expiry: Not recorded/);
assert.doesNotMatch(zeroAndMissingPdf, /Supplier:|Batch:|Shelf:|Barcode:/);
assert.match(zeroAndMissingDocx, /Selling KES 0 \| Cost KES Not recorded/);
assert.match(zeroAndMissingDocx, /<w:pStyle w:val="StockValue"\/>[\s\S]*?>0</);
assert.match(missingStockDocx, /<w:pStyle w:val="StockMissing"\/>[\s\S]*?>Stock not recorded</);
assert.doesNotMatch(missingStockDocx, /<w:pStyle w:val="StockValue"\/>/);
assert.doesNotMatch(zeroAndMissingDocx, /<w:pStyle w:val="StockValue"\/>[\s\S]*?>Not recorded</);
assert.match(zeroAndMissingDocx, /Expiry: Not recorded/);
assert.match(zeroAndMissingDocx, /Supplier: Not recorded/);
assert.doesNotMatch(zeroAndMissingDocx, /Batch:|Shelf:|Barcode:/);
assert.match(outputs.csv, /^\ufeffMedicine,Strength,Form,Unit,Selling price \(KES\),Cost price \(KES\),Stock,Supplier,Barcode,Batch,Expiry,Shelf\r\n/);
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
assert.equal(exportFilename(model, "csv"), "zuri-pharmacy-inventory-2026-07-25-180032Z.csv");
assert.equal(exportFormat("csv").mime, "text/csv; charset=utf-8");

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
  for (const format of ["xlsx", "docx"]) {
    assert.match(decodedPackages[format], new RegExp(item.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")), `${format.toUpperCase()} missing ${item.name}`);
  }
  assert.match(decodedPdf, new RegExp(item.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")), `PDF missing ${item.name}`);
  assert.equal((decodedPdf.match(new RegExp(item.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g")) || []).length, 1, `PDF must contain ${item.name} exactly once in the inventory section`);
  assert.match(outputs.html, new RegExp(`class="record-main"[\\s\\S]*?${item.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`), `Print missing ${item.name}`);
}
assert.equal((decodedPackages.pptx.match(/<p:sldId /g) || []).length, 9);
assert.match(decodedPackages.pptx, /Pharmacy owner briefing/);
assert.match(decodedPackages.pptx, /The pharmacy has a clear inventory baseline/);
assert.match(decodedPackages.pptx, /The strongest next step is completing missing operating data/);
assert.match(decodedPackages.pptx, /Recorded inventory carries measurable working capital/);
assert.match(decodedPackages.pptx, /Low-stock items require a purchasing decision/);
assert.match(decodedPackages.pptx, /No near-term expiry is flagged/);
assert.match(decodedPackages.pptx, /Supplier concentration shapes purchasing resilience/);
assert.match(decodedPackages.pptx, /Keep the next inventory cycle decision-ready/);
assert.match(decodedPackages.pptx, /Make the inventory decisions that matter/);
assert.doesNotMatch(decodedPackages.pptx, /Inventory review \|/);
assert.equal((decodedPackages.docx.match(/w:type="page"/g) || []).length, 9);
assert.equal((decodedPdf.match(/\/Type \/Page\b/g) || []).length, 8);
assert.equal((decodedPdf.match(/\/MediaBox \[0 0 595 842\]/g) || []).length, 8);
assert.match(decodedPdf, /Pharmacy Overview/);
assert.match(decodedPdf, /At a glance/);
assert.match(decodedPdf, /Medicines 1-5 of 35/);
assert.match(decodedPdf, /Medicines 31-35 of 35/);
assert.doesNotMatch(decodedPdf, /Supplier: -|Batch: -|Shelf: -|Barcode: -|Stock -|Cost KES -/);
assert.match(decodedPdf, /Generated by MS2\.0 \| Pharmacy inventory/);
assert.match(decodedPackages.docx, /Editable Pharmacy Inventory/);
assert.match(decodedPackages.docx, /Use this document to review inventory, record corrections and add working notes\./);
assert.match(decodedPackages.docx, /General owner notes \/ corrections/);
assert.equal((decodedPackages.docx.match(/OWNER NOTES \/ CORRECTIONS/g) || []).length, 35);
assert.equal((decodedPackages.docx.match(/Add note or correction here/g) || []).length, 35);
assert.match(decodedPackages.docx, /ms20\.word-owner-copy\.v2/);
assert.doesNotMatch(decodedPackages.docx, /w:documentProtection|vbaProject|<w:drawing/);
assert.match(decodedPackages.docx, /<w:t xml:space="preserve"> <\/w:t>/);
assert.equal((decodedPackages.docx.match(/<w:tbl>/g) || []).length, 37);
assert.match(decodedPackages.docx, /<w:pgSz w:w="12240" w:h="15840"\/>/);
assert.doesNotMatch(decodedPackages.docx, /w:orient="landscape"/);
assert.equal((decodedPackages.docx.match(/<w:tblW w:w="9360" w:type="dxa"\/>/g) || []).length, 37);
assert.equal((decodedPackages.docx.match(/<w:tblInd w:w="120" w:type="dxa"\/>/g) || []).length, 37);
assert.match(decodedPackages.docx, /Medicines 1-4 of 35 \| Page 2 of 10/);
assert.match(decodedPackages.docx, /Medicines 33-35 of 35 \| Page 10 of 10/);
for (const item of items) {
  const escaped = item.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  assert.equal((decodedPackages.docx.match(new RegExp(`>${escaped}<`, "g")) || []).length, 1, `DOCX must contain ${item.name} exactly once`);
}
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
const metadataSource = await readFile(new URL("../src/services/exportFormatMetadata.js", import.meta.url), "utf8");
const cssSource = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");
const provenance = JSON.parse(await readFile(new URL("../provenance-registry.json", import.meta.url), "utf8"));
assert.equal(provenance.schema, "ms20.provenance-registry.v1");
assert.ok(provenance.entries.some((entry) => entry.name === "MS2.0 shared medicine finder" && entry.review_status === "approved"));
assert.ok(provenance.entries.every((entry) => entry.source && entry.licence && entry.approved_use && entry.proof && entry.owner));
assert.match(appSource, /data-action="open-export-hub">Export Hub/);
assert.match(appSource, /buildCanonicalInventoryExport\(\{ pharmacy: state\.pharmacy, items: pharmacyBrain\.catalog \}\)/);
assert.match(appSource, /download-inventory-export/);
assert.match(source, /anchor\.download = filename/);
assert.match(appSource, /card\.type === "CatalogWorkspaceCard" \|\| card\.type === "ExportHubCard"/);
assert.match(appSource, /Choose Excel for calculations and reconciliation, PDF for read-only sharing and phone viewing/);
assert.match(metadataSource, /Open the downloaded workbook in Excel or another compatible spreadsheet application\./);
assert.match(metadataSource, /Open the editable file in Microsoft Word or another compatible document editor\./);
assert.match(metadataSource, /Open the downloaded presentation in Microsoft PowerPoint for the best experience\./);
assert.match(metadataSource, /Use browser Print and choose an available printer\./);
assert.match(metadataSource, /Open in Microsoft Excel, Google Sheets or LibreOffice Calc to inspect the rows, or import it into another compatible system\./);
assert.match(metadataSource, /text\/csv; charset=utf-8/);
assert.match(appSource, /ms20\.export-history\.v1/);
assert.match(appSource, /previous\.filter\(\(item\) => item\.id !== record\.id\)/);
assert.match(appSource, /EXPORT_HISTORY_KEY_PREFIX.*state\.pharmacy\.id/s);
assert.doesNotMatch(appSource, /function recordExportEvent[\s\S]{0,1200}addFeed\(/);
assert.match(appSource, /function ensureExportHubCard\(\)/);
assert.match(appSource, /state\.cards = state\.cards\.filter\(\(item\) => item\.type !== "ExportHubCard" \|\| item === card\)/);
assert.match(appSource, /card\.fields\.last_download = record\.summary/);
assert.match(appSource, /summary: exportCompletionSummary\(item\.format, item\.status, item\.medicineCount\)/);
assert.match(appSource, /summary: exportCompletionSummary\(format, recordStatus, model\.rows\.length\)/);
assert.doesNotMatch(exportCompletionSummary("csv", "completed", 35), /Open in|inspect the rows|import it/i);
assert.match(appSource, /data-action="open-export-hub" data-history="true"/);
assert.match(appSource, /Files stay in your device Downloads\. History keeps metadata only\./);
assert.match(appSource, /<h3>Polished owner copies<\/h3>/);
assert.match(appSource, /<h3>Technical data transfer<\/h3>/);
assert.match(appSource, /CSV preserves the records for other systems, but it cannot carry colours, fonts, spacing or page design\./);
assert.match(cssSource, /\.export-data-section/);
assert.match(appSource, /state\.printPreview = \{ model, bridgeId, query: "", message: "", exportCardId: targetCardId \}/);
assert.match(appSource, /printFrame\.srcdoc = buildPrintHtml/);
assert.match(appSource, /window\.__ms20PrintStatus/);
assert.match(outputs.html, /ms20OpenPrintDialog/);
assert.match(outputs.html, /status:"print_dialog_opened"/);
assert.doesNotMatch(`${appSource}\n${source}`, /Printed successfully|physical print completed|status:\s*"completed"[\s\S]{0,80}format:\s*"print"/i);
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
assert.doesNotMatch(metadataSource, /OpenAI|fetch\s*\(|chat\.completions|responses\.create/);
assert.match(cssSource, /@media \(max-width: 520px\)[^{]*\{[^}]*\.export-format-grid/);
assert.match(cssSource, /\.print-preview-overlay/);

const outputDir = join(process.cwd(), ".export-hub-verification", "artifacts");
await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });
await Promise.all([
  writeFile(join(outputDir, exportFilename(model, "csv")), outputs.csv), writeFile(join(outputDir, exportFilename(model, "xlsx")), outputs.xlsx),
  writeFile(join(outputDir, exportFilename(model, "pdf")), outputs.pdf), writeFile(join(outputDir, exportFilename(model, "docx")), outputs.docx),
  writeFile(join(outputDir, exportFilename(model, "pptx")), outputs.pptx), writeFile(join(outputDir, exportFilename(model, "print.html")), outputs.html),
  writeFile(join(outputDir, "csv-security-fixture.csv"), securedCsv)
]);
console.log(`Export Hub verification passed: 35 canonical records in six formats, pharmacy isolation, balanced pagination, fresh filenames, deterministic zero-AI renderers. 4,200-record finder index ${buildMs.toFixed(1)} ms; exact search ${searchMs.toFixed(1)} ms. Artifacts: ${outputDir}`);
