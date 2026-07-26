import { buildStoredZip, xml } from "./ooxmlPackage.js";
import { buildMedicineFinderIndex, medicineFinderClientScript } from "./medicineFinder.js";

export const EXPORT_FORMATS = Object.freeze([
  { id: "xlsx", group: "polished", label: "Excel", help: "Styled workbook for sorting, filtering and review" },
  { id: "pdf", group: "polished", label: "PDF", help: "Elegant fixed, paginated owner copy" },
  { id: "docx", group: "polished", label: "Word", help: "Editable professional document" },
  { id: "pptx", group: "polished", label: "Presentation", help: "Landscape inventory briefing slides" },
  { id: "print", group: "polished", label: "Print", help: "Print-ready browser layout" },
  { id: "csv", group: "data", label: "CSV data file", help: "Plain data transfer for systems and imports — no visual styling" }
]);

const COLUMNS = Object.freeze([
  ["medicine", "Medicine"], ["strength", "Strength"], ["form", "Form"], ["unit", "Unit"],
  ["sellingPrice", "Selling price (KES)"], ["costPrice", "Cost price (KES)"], ["stock", "Stock"],
  ["supplier", "Supplier"], ["barcode", "Barcode"], ["batch", "Batch"], ["expiry", "Expiry"], ["shelf", "Shelf"]
]);
const PRINT_COLUMNS = Object.freeze([
  ["medicine", "Medicine"], ["strength", "Strength"], ["form", "Form"], ["unit", "Unit"],
  ["sellingPrice", "Sell KES"], ["costPrice", "Cost KES"], ["stock", "Stock"], ["supplier", "Supplier"]
]);
const PRINT_RECORDS_PER_PAGE = 9;
const PDF_RECORDS_PER_PAGE = 7;
const OFFICE_RECORDS_PER_PAGE = 5;

export function buildCanonicalInventoryExport({ pharmacy, items, generatedAt = new Date() }) {
  const pharmacyId = clean(pharmacy?.id);
  if (!pharmacyId) throw new Error("A pharmacy identity is required for export isolation.");
  const instant = generatedAt instanceof Date ? generatedAt : new Date(generatedAt);
  if (Number.isNaN(instant.getTime())) throw new Error("A valid generation time is required.");
  const sourceItems = Array.isArray(items) ? items : [];
  const finderIndex = buildMedicineFinderIndex(sourceItems, { now: instant });
  const finderByPosition = new Map(finderIndex.map((entry) => [entry.position, entry.id]));
  const rows = sourceItems.map((item, position) => {
    const batch = Array.isArray(item?.batches) ? item.batches[0] || {} : {};
    return Object.freeze({
      finderId: finderByPosition.get(position) || `medicine-${position}`,
      medicine: clean(item?.name || item?.medicine), strength: clean(item?.strength),
      form: clean(first(item?.forms) || item?.form), unit: clean(first(item?.units) || item?.unit),
      sellingPrice: numberOrBlank(item?.sellingPrice ?? item?.selling_price),
      costPrice: numberOrBlank(item?.costPrice ?? item?.cost_price),
      stock: numberOrBlank(item?.stockLeft ?? item?.stock ?? item?.current_stock),
      reorderLevel: numberOrBlank(item?.reorderLevel ?? item?.reorder_level),
      supplier: clean(item?.supplier || batch.supplier), barcode: clean(item?.barcode),
      batch: clean(batch.batch || item?.batch), expiry: clean(batch.expiry || item?.expiry),
      shelf: clean(item?.shelf || item?.location)
    });
  });
  const frozenRows = Object.freeze(rows);
  const frozenFinderIndex = Object.freeze(finderIndex.map((entry) => Object.freeze({
    ...entry,
    flags: Object.freeze({ ...(entry.flags || {}) })
  })));
  const summary = Object.freeze(inventorySummary(frozenRows, frozenFinderIndex));
  const snapshot = Object.freeze({
    schema: "ms20.inventory-export.v1", pharmacyId,
    pharmacyName: clean(pharmacy?.name) || "Pharmacy",
    branch: clean(pharmacy?.branch) || "Main", location: clean(pharmacy?.location) || "Kenya",
    generatedIso: instant.toISOString(), generatedKenya: kenyaTime(instant),
    title: "Pharmacy Inventory", columns: COLUMNS, rows: frozenRows,
    finderIndex: frozenFinderIndex, summary
  });
  validateInventoryExportSnapshot(snapshot);
  return snapshot;
}

export function validateInventoryExportSnapshot(model) {
  if (!model || model.schema !== "ms20.inventory-export.v1") throw new Error("The inventory export snapshot is invalid.");
  if (!clean(model.pharmacyId) || !clean(model.pharmacyName)) throw new Error("The inventory export snapshot is missing pharmacy identity.");
  if (!Array.isArray(model.rows) || !Array.isArray(model.finderIndex)) throw new Error("The inventory export snapshot is incomplete.");
  const identities = new Set();
  model.rows.forEach((row, index) => {
    if (!clean(row?.medicine)) throw new Error(`Inventory export row ${index + 1} is missing the mandatory medicine name.`);
    const identity = clean(row.medicine).toLocaleLowerCase("en");
    if (identities.has(identity)) throw new Error(`Inventory export contains duplicate medicine identity: ${row.medicine}.`);
    identities.add(identity);
    for (const field of ["sellingPrice", "costPrice", "stock", "reorderLevel"]) {
      if (row[field] !== "" && (!Number.isFinite(row[field]) || row[field] < 0)) {
        throw new Error(`Inventory export row ${index + 1} has an invalid ${field} value.`);
      }
    }
  });
  if (model.rows.length !== model.finderIndex.length) throw new Error("Inventory export reconciliation failed: finder and medicine counts differ.");
  const expected = inventorySummary(model.rows, model.finderIndex);
  for (const key of Object.keys(expected)) {
    if (model.summary?.[key] !== expected[key]) throw new Error(`Inventory export reconciliation failed for ${key}.`);
  }
  return true;
}

export function buildCatalogCsv(items = []) {
  return buildInventoryCsv(buildCanonicalInventoryExport({ pharmacy: { id: "legacy", name: "Pharmacy" }, items }));
}

export function buildInventoryCsv(model) {
  const metadata = [
    ["MS2.0 Pharmacy Inventory"], ["Pharmacy", model.pharmacyName], ["Branch", model.branch],
    ["Location", model.location], ["Generated (Africa/Nairobi)", model.generatedKenya], []
  ];
  const rows = [COLUMNS.map(([, label]) => label), ...model.rows.map((row) => COLUMNS.map(([key]) => row[key]))];
  return `\ufeff${[...metadata, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n")}`;
}

export function buildInventoryXlsx(model) {
  validateInventoryExportSnapshot(model);
  const sheets = buildOwnerWorkbookSheets(model);
  validateOwnerWorkbookSheets(model, sheets);
  const sheetOverrides = sheets.map((_, index) => `<Override PartName="/xl/worksheets/sheet${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("");
  const sheetNodes = sheets.map((sheet, index) => `<sheet name="${xml(sheet.name)}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`).join("");
  const workbookRelationships = sheets.map((_, index) => [`rId${index + 1}`, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", `worksheets/sheet${index + 1}.xml`]);
  return buildStoredZip([
    ["[Content_Types].xml", `<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>${sheetOverrides}<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>`],
    ["_rels/.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "xl/workbook.xml"], ["rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"], ["rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties", "docProps/app.xml"]])],
    ["xl/workbook.xml", `<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><bookViews><workbookView activeTab="0"/></bookViews><sheets>${sheetNodes}</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>`],
    ["xl/_rels/workbook.xml.rels", rels([...workbookRelationships, [`rId${sheets.length + 1}`, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "styles.xml"]])],
    ...sheets.map((sheet, index) => [`xl/worksheets/sheet${index + 1}.xml`, buildXlsxSheetXml(sheet)]),
    ["xl/styles.xml", xlsxStyles()], ["docProps/core.xml", coreProps(model)], ["docProps/app.xml", appProps("Microsoft Excel")]
  ].map(([name, contents]) => ({ name, contents })));
}

export function buildInventoryDocx(model) {
  const pages = balancedChunks(model.rows, OFFICE_RECORDS_PER_PAGE);
  const body = pages.map((rows, pageIndex) => [
    wordP(model.title, "Title"),
    wordP(`${model.pharmacyName} | ${model.branch} | ${model.location}`, "Subtitle"),
    wordP(`Generated ${model.generatedKenya} Africa/Nairobi | Page ${pageIndex + 1} of ${pages.length}`, "Meta"),
    wordP(`${model.rows.length} canonical medicine records | Pharmacy-isolated | Generated locally with zero AI formatting`, "Summary"),
    ...rows.map(wordMedicineBlock),
    pageIndex < pages.length - 1 ? '<w:p><w:r><w:br w:type="page"/></w:r></w:p>' : ""
  ].join("")).join("");
  const document = `<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${body}<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/><w:pgMar w:top="576" w:right="720" w:bottom="576" w:left="720" w:header="360" w:footer="360"/></w:sectPr></w:body></w:document>`;
  return buildStoredZip([
    entry("[Content_Types].xml", `<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>`),
    entry("_rels/.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "word/document.xml"], ["rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"], ["rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties", "docProps/app.xml"]])),
    entry("word/document.xml", document), entry("word/_rels/document.xml.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "styles.xml"]])),
    entry("word/styles.xml", wordStyles()), entry("docProps/core.xml", coreProps(model)), entry("docProps/app.xml", appProps("Microsoft Word"))
  ]);
}

export function buildInventoryPptx(model) {
  const chunks = balancedChunks(model.rows, OFFICE_RECORDS_PER_PAGE);
  const slides = [titleSlide(model), ...chunks.map((rows, index) => tableSlide(model, rows, index + 1, chunks.length))];
  const overrides = slides.map((_, i) => `<Override PartName="/ppt/slides/slide${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>`).join("");
  const slideIds = slides.map((_, i) => `<p:sldId id="${256 + i}" r:id="rId${i + 2}"/>`).join("");
  const slideRels = slides.map((_, i) => [`rId${i + 2}`, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide", `slides/slide${i + 1}.xml`]);
  const entries = [
    entry("[Content_Types].xml", `<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/><Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>${overrides}<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>`),
    entry("_rels/.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "ppt/presentation.xml"], ["rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"], ["rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties", "docProps/app.xml"]])),
    entry("ppt/presentation.xml", `<?xml version="1.0"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>${slideIds}</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>`),
    entry("ppt/_rels/presentation.xml.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster", "slideMasters/slideMaster1.xml"], ...slideRels])),
    entry("ppt/slideMasters/slideMaster1.xml", slideMaster()), entry("ppt/slideMasters/_rels/slideMaster1.xml.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml"], ["rId2", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme", "../theme/theme1.xml"]])),
    entry("ppt/slideLayouts/slideLayout1.xml", slideLayout()), entry("ppt/slideLayouts/_rels/slideLayout1.xml.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster", "../slideMasters/slideMaster1.xml"]])),
    entry("ppt/theme/theme1.xml", pptTheme()), entry("docProps/core.xml", coreProps(model)), entry("docProps/app.xml", appProps("Microsoft PowerPoint")),
    ...slides.flatMap((contents, i) => [entry(`ppt/slides/slide${i + 1}.xml`, contents), entry(`ppt/slides/_rels/slide${i + 1}.xml.rels`, rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml"]]))])
  ];
  return buildStoredZip(entries);
}

export function buildInventoryPdf(model) {
  const pages = balancedChunks(model.rows, PDF_RECORDS_PER_PAGE);
  if (!pages.length) pages.push([]);
  const objects = [null];
  const add = (value) => (objects.push(value), objects.length - 1);
  const font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");
  const bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>");
  const pageIds = [];
  const pagesId = add("");
  pages.forEach((rows, pageIndex) => {
    const stream = pdfPage(model, rows, pageIndex + 1, pages.length);
    const content = add(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
    pageIds.push(add(`<< /Type /Page /Parent ${pagesId} 0 R /MediaBox [0 0 842 595] /Resources << /Font << /F1 ${font} 0 R /F2 ${bold} 0 R >> >> /Contents ${content} 0 R >>`));
  });
  objects[pagesId] = `<< /Type /Pages /Count ${pageIds.length} /Kids [${pageIds.map((id) => `${id} 0 R`).join(" ")}] >>`;
  const catalog = add(`<< /Type /Catalog /Pages ${pagesId} 0 R >>`);
  let pdf = "%PDF-1.4\n%MS20\n";
  const offsets = [0];
  for (let i = 1; i < objects.length; i += 1) { offsets[i] = pdf.length; pdf += `${i} 0 obj\n${objects[i]}\nendobj\n`; }
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length}\n0000000000 65535 f \n${offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n `).join("\n")}\ntrailer\n<< /Size ${objects.length} /Root ${catalog} 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return new TextEncoder().encode(pdf);
}

export function buildPrintHtml(model, { bridgeId = "", initialQuery = "", initialMessage = "" } = {}) {
  const cells = (row) => COLUMNS.map(([key, label]) => `<td data-label="${xml(label)}">${xml(row[key] === "" ? "—" : row[key])}</td>`).join("");
  const detailRows = (row) => COLUMNS.map(([key, label]) => `<div class="field"><strong>${xml(label)}</strong><span>${xml(row[key] === "" ? "—" : row[key])}</span></div>`).join("");
  const mobileCards = model.rows.map((row, index) => `<details class="medicine-card" data-finder-id="${xml(row.finderId)}"${index === 0 ? " open" : ""}><summary><span><strong>${xml(row.medicine || "Unnamed medicine")}</strong><small>${xml([row.strength, row.form, row.unit].filter(Boolean).join(" · ") || "Details not recorded")}</small></span><span class="quick-facts"><b>Stock ${xml(row.stock === "" ? "—" : row.stock)}</b><small>KES ${xml(row.sellingPrice === "" ? "—" : row.sellingPrice)}</small></span></summary><div class="details-grid">${detailRows(row)}</div></details>`).join("");
  const printPages = balancedChunks(model.rows, PRINT_RECORDS_PER_PAGE).map((rows, pageIndex, pages) => `<section class="print-sheet"><header><h2>${xml(model.title)}</h2><p><strong>${xml(model.pharmacyName)}</strong> · ${xml(model.branch)} · ${xml(model.location)}<br>Generated ${xml(model.generatedKenya)} Africa/Nairobi · Page ${pageIndex + 1} of ${pages.length}</p></header><table><thead><tr>${PRINT_COLUMNS.map(([, label]) => `<th>${xml(label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr class="record-main">${PRINT_COLUMNS.map(([key]) => `<td>${xml(row[key] === "" ? "—" : row[key])}</td>`).join("")}</tr><tr class="record-trace"><td colspan="${PRINT_COLUMNS.length}"><strong>Barcode</strong> ${xml(row.barcode || "—")} <strong>Batch</strong> ${xml(row.batch || "—")} <strong>Expiry</strong> ${xml(row.expiry || "—")} <strong>Shelf</strong> ${xml(row.shelf || "—")}</td></tr>`).join("")}</tbody></table><footer>${model.rows.length} canonical medicine records · Pharmacy-isolated · Generated locally by MS2.0 with zero AI formatting.</footer></section>`).join("");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>MS2.0 | ${xml(model.title)} | Print preview</title><style>
  :root{font-family:Arial,sans-serif;color:#19332f;background:#eef5f3;color-scheme:light}*{box-sizing:border-box}body{margin:0}.page{max-width:1200px;margin:0 auto;padding:20px}.toolbar{position:sticky;top:0;z-index:2;display:flex;gap:10px;align-items:center;padding:12px 0;background:#eef5f3}.action{min-height:46px;padding:10px 18px;border:1px solid #086c5c;border-radius:24px;background:#086c5c;color:#fff;font:700 16px Arial;cursor:pointer}.action.secondary{background:#fff;color:#086c5c}.eyebrow{margin:8px 0 4px;color:#536b66;font-size:14px;font-weight:700}h1{margin:0 0 8px;color:#086c5c;font-size:30px}.meta{margin:0 0 10px;font-size:16px;line-height:1.5}.summary{margin:0 0 18px;padding:12px 14px;border-left:5px solid #086c5c;background:#dff1ec;font-size:16px}.mobile-review,.print-pages{display:none}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;background:#fff;font-size:12px}th{background:#086c5c;color:#fff;text-align:left}th,td{padding:7px;border:1px solid #c9d8d4;vertical-align:top;overflow-wrap:anywhere}tbody tr:nth-child(even){background:#f1f7f5}footer{margin:16px 0;color:#536b66;line-height:1.5}
  @media(max-width:720px){.page{padding:14px}.toolbar{justify-content:stretch}.action{flex:1;padding:10px 12px}h1{font-size:26px}.meta,.summary{font-size:15px}.table-wrap{display:none}.mobile-review{display:block}.finder-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}.finder-action{min-height:46px;border:1px solid #086c5c;border-radius:23px;background:#fff;color:#086c5c;font:700 15px Arial}.search-label{display:block;margin:0 0 8px;font-weight:700}.search{width:100%;min-height:48px;margin-bottom:10px;padding:10px 14px;border:1px solid #7e9b95;border-radius:12px;background:#fff;color:#19332f;font:16px Arial}.filter{width:100%;min-height:46px;margin-bottom:10px;padding:8px 12px;border:1px solid #7e9b95;border-radius:12px;background:#fff;color:#19332f;font:15px Arial}.review-help{margin:0 0 12px;color:#536b66;font-size:14px}.medicine-list{display:grid;gap:10px}.medicine-card{border:1px solid #b7cdc8;border-radius:14px;background:#fff;box-shadow:0 2px 8px rgba(25,51,47,.06);overflow:hidden}.medicine-card[hidden]{display:none}.medicine-card summary{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;min-height:68px;padding:12px 14px;cursor:pointer}.medicine-card summary>span:first-child{display:grid;gap:4px}.medicine-card summary strong{font-size:17px}.medicine-card small{color:#536b66;font-size:13px}.quick-facts{display:grid;gap:4px;text-align:right}.quick-facts b{color:#086c5c;font-size:14px}.details-grid{border-top:1px solid #d6e3df}.field{display:grid;grid-template-columns:minmax(112px,42%) 1fr;gap:10px;min-height:42px;padding:10px 12px;border-bottom:1px solid #e1ebe8;font-size:15px;line-height:1.35}.field:last-child{border-bottom:0}.field strong{color:#536b66}footer{font-size:14px}}
  @page{size:A4 landscape;margin:9mm}@media print{:root{background:#fff}.page{max-width:none;margin:0;padding:0}.toolbar,.eyebrow,.summary,.mobile-review,.screen-title,.screen-meta,.table-wrap,.screen-footer{display:none!important}.print-pages{display:block}.print-sheet{break-after:page;page-break-after:always}.print-sheet:last-child{break-after:auto;page-break-after:auto}.print-sheet header{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin:0 0 7px}.print-sheet h2{margin:0;color:#086c5c;font-size:18px}.print-sheet header p{margin:0;text-align:right;font-size:9.5px;line-height:1.35}.print-sheet table{table-layout:fixed;font-size:9.5px}.print-sheet thead{display:table-header-group}.print-sheet th{padding:5px 6px}.print-sheet td{padding:5px 6px;line-height:1.25}.print-sheet th:nth-child(1){width:18%}.print-sheet th:nth-child(2){width:11%}.print-sheet th:nth-child(3),.print-sheet th:nth-child(4){width:9%}.print-sheet th:nth-child(5),.print-sheet th:nth-child(6),.print-sheet th:nth-child(7){width:8%}.record-main{break-inside:avoid}.record-trace{break-inside:avoid;background:#f1f7f5;color:#405a55}.record-trace td{padding:4px 7px 7px;border-top:0}.record-trace strong{margin-left:16px;color:#19332f}.record-trace strong:first-child{margin-left:0}.print-sheet footer{font-size:8.5px;margin-top:7px}}
  </style></head><body><main class="page"><div class="toolbar"><button class="action" type="button" onclick="window.print()">Print inventory</button><button class="action secondary" type="button" onclick="window.close()">Close view</button></div><p class="eyebrow">Review before printing</p><h1 class="screen-title">${xml(model.title)}</h1><p class="meta screen-meta"><strong>${xml(model.pharmacyName)}</strong><br>${xml(model.branch)} · ${xml(model.location)}<br>Generated ${xml(model.generatedKenya)} Africa/Nairobi</p><p class="summary">${model.rows.length} canonical medicine records · Pharmacy-isolated · Generated locally with zero AI formatting</p><section class="mobile-review" aria-label="Mobile inventory review"><label class="search-label" for="medicine-search">Fast medicine finder</label><div class="finder-actions"><button class="finder-action" id="finder-scan" type="button">Scan barcode</button><button class="finder-action" id="finder-voice" type="button">Speak medicine</button></div><p class="review-help" id="finder-status" aria-live="polite"></p><select class="filter" id="medicine-filter" aria-label="Quick medicine filter"><option value="all">All medicines</option><option value="lowStock">Low stock</option><option value="outOfStock">Out of stock</option><option value="expiringSoon">Expiring soon</option><option value="az">A–Z</option></select><label class="search-label" for="medicine-search">Type only if needed</label><input class="search" id="medicine-search" type="search" placeholder="Name, alias, strength, form, unit, barcode, supplier, shelf or batch" autocomplete="off"><p class="review-help" id="review-count">${model.rows.length} of ${model.rows.length} medicines shown · Tap a medicine to view every field.</p><div class="medicine-list">${mobileCards}</div></section><div class="table-wrap"><table><thead><tr>${COLUMNS.map(([, label]) => `<th>${xml(label)}</th>`).join("")}</tr></thead><tbody>${model.rows.map((row) => `<tr>${cells(row)}</tr>`).join("")}</tbody></table></div><footer class="screen-footer">${model.rows.length} canonical medicine records. Generated locally by MS2.0 with no AI formatting.</footer><div class="print-pages">${printPages}</div></main><script>${medicineFinderClientScript(model.finderIndex, { bridgeId, initialQuery, initialMessage })}</script></body></html>`;
}

export function exportFilename(model, extension) {
  const pharmacy = model.pharmacyName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "pharmacy";
  const marker = model.generatedIso.replace(/\.\d{3}Z$/, "Z").replaceAll(":", "").replace("T", "-");
  return `${pharmacy}-inventory-${marker}.${extension}`;
}

export function downloadBlobFile({ filename, contents, mime }) {
  const blob = contents instanceof Blob ? contents : new Blob([contents], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename;
  document.body.appendChild(anchor); anchor.click(); anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadTextFile({ filename, contents, mime = "text/plain;charset=utf-8" }) { downloadBlobFile({ filename, contents, mime }); }
export function buildBulkPasteTemplate() { return ["MS2.0 BULK PASTE TEMPLATE", "Enter one medicine per line.", "Format: medicine name form selling price", "Remove these instructions before pasting your medicine lines."].join("\n"); }
export function buildDocumentCard({ title, document, format, itemCount = 0, status = "ready" }) { return { id: `card-document-${Date.now()}`, type: "DocumentExportCard", title, source: "MS2.0 documents", confidence: 1, status, aiRequired: false, fields: { document, format, items: String(itemCount), status: "Ready to download" }, validation: "Generated locally from canonical pharmacy records." }; }

export function buildOwnerWorkbookSheets(model) {
  validateInventoryExportSnapshot(model);
  const stockNumber = (row) => typeof row.stock === "number" ? row.stock : Number(row.stock);
  const finderFlags = new Map(model.finderIndex.map((entry) => [entry.id, entry.flags]));
  const lowStock = model.rows.filter((row) => finderFlags.get(row.finderId)?.lowStock === true)
    .sort((a, b) => stockNumber(a) - stockNumber(b) || a.medicine.localeCompare(b.medicine));
  const expiryRows = [...model.rows]
    .sort((a, b) => (a.expiry ? 0 : 1) - (b.expiry ? 0 : 1) || a.expiry.localeCompare(b.expiry) || a.medicine.localeCompare(b.medicine));
  const supplierRowsSorted = [...model.rows]
    .sort((a, b) => (a.supplier || "Not recorded").localeCompare(b.supplier || "Not recorded") || a.medicine.localeCompare(b.medicine));
  const attentionRows = model.rows.map((row) => {
    const flags = finderFlags.get(row.finderId) || {};
    const reasons = [flags.lowStock ? "Low stock" : "", flags.expiringSoon ? "Expiring soon" : ""].filter(Boolean);
    return { row, reason: reasons.join(" and ") };
  }).filter((entry) => entry.reason)
    .sort((a, b) => a.reason.localeCompare(b.reason) || stockNumber(a.row) - stockNumber(b.row) || a.row.medicine.localeCompare(b.row.medicine));
  const commonMeta = [
    [model.title], [`${model.pharmacyName} · ${model.branch} · ${model.location}`],
    [`Generated ${model.generatedKenya} Africa/Nairobi · ${model.summary.medicineCount} canonical medicines`]
  ];
  const fullRows = [
    [model.title], ["Pharmacy", model.pharmacyName], ["Branch", model.branch],
    ["Location", model.location], ["Generated (Africa/Nairobi)", `${model.generatedKenya} · ${model.summary.medicineCount} canonical medicines`], [],
    COLUMNS.map(([, label]) => label), ...model.rows.map((row) => COLUMNS.map(([key]) => row[key]))
  ];
  const overviewRows = [
    ...commonMeta, [],
    ["Total medicines", model.summary.medicineCount],
    ["Total stock value (KES)", model.summary.retailStockValue],
    ["Low stock count", model.summary.lowStockCount],
    ["Expiring soon count", model.summary.expiringSoonCount],
    ["Attention required"], ["Medicine", "Stock", "Expiry", "Reason"],
    ...(attentionRows.length
      ? attentionRows.map(({ row, reason }) => [row.medicine, row.stock, row.expiry, reason])
      : [["No medicines currently require attention.", "", "", ""]])
  ];
  const lowStockRows = [
    ...commonMeta, ["Action list · at or below the saved reorder level"],
    ["Medicine", "Stock", "Reorder level", "Expiry", "Reason"],
    ...(lowStock.length ? lowStock.map((row) => [row.medicine, row.stock, row.reorderLevel, row.expiry, "At or below reorder level"]) : [["No medicines are currently at or below their saved reorder level."]])
  ];
  const expiryTrackingRows = [
    ...commonMeta, ["All medicines · recorded expiries first"],
    ["Medicine", "Expiry", "Batch", "Stock"],
    ...expiryRows.map((row) => [row.medicine, row.expiry, row.batch, row.stock])
  ];
  const supplierRows = [
    ...commonMeta, ["Supplier and shelf responsibility"],
    ["Supplier", "Medicine", "Stock", "Shelf"],
    ...supplierRowsSorted.map((row) => [row.supplier || "Not recorded", row.medicine, row.stock, row.shelf])
  ];
  const sheets = [
    ownerSheet("Inventory Overview", overviewRows, { sourceCount: model.summary.medicineCount, projectionCount: attentionRows.length, headerRow: 10, freezeRows: 10, freezeColumns: 1, merges: ["A1:D1", "A2:D2", "A3:D3", "A9:D9"], widths: [28, 18, 18, 24], overview: true }),
    ownerSheet("Full Inventory", fullRows, { sourceCount: model.summary.medicineCount, projectionCount: model.rows.length, headerRow: 7, freezeRows: 7, freezeColumns: 1, widths: autoXlsxWidths(fullRows, [26, 14, 13, 12, 17, 16, 11, 24, 18, 14, 13, 10]) }),
    ownerSheet("Low Stock", lowStockRows, { sourceCount: model.summary.medicineCount, projectionCount: lowStock.length, headerRow: 5, freezeRows: 5, freezeColumns: 1, merges: ["A1:E1", "A2:E2", "A3:E3", "A4:E4", ...(lowStock.length ? [] : ["A6:E6"])], widths: [26, 12, 16, 15, 25], alert: true }),
    ownerSheet("Expiry Tracking", expiryTrackingRows, { sourceCount: model.summary.medicineCount, projectionCount: expiryRows.length, headerRow: 5, freezeRows: 5, freezeColumns: 1, merges: ["A1:D1", "A2:D2", "A3:D3", "A4:D4"], widths: [26, 16, 18, 12] }),
    ownerSheet("Suppliers", supplierRows, { sourceCount: model.summary.medicineCount, projectionCount: supplierRowsSorted.length, headerRow: 5, freezeRows: 5, freezeColumns: 1, merges: ["A1:D1", "A2:D2", "A3:D3", "A4:D4"], widths: [28, 26, 12, 12] })
  ];
  validateOwnerWorkbookSheets(model, sheets);
  return sheets;
}
function ownerSheet(name, rows, options) { return { name, rows, ...options }; }
function inventorySummary(rows, finderIndex) {
  const flagsById = new Map(finderIndex.map((entry) => [entry.id, entry.flags || {}]));
  return {
    medicineCount: rows.length,
    totalStock: rows.reduce((sum, row) => sum + (Number(row.stock) || 0), 0),
    retailStockValue: rows.reduce((sum, row) => sum + (Number(row.sellingPrice) || 0) * (Number(row.stock) || 0), 0),
    lowStockCount: rows.filter((row) => flagsById.get(row.finderId)?.lowStock === true).length,
    expiringSoonCount: rows.filter((row) => flagsById.get(row.finderId)?.expiringSoon === true).length
  };
}
function validateOwnerWorkbookSheets(model, sheets) {
  const expectedNames = ["Inventory Overview", "Full Inventory", "Low Stock", "Expiry Tracking", "Suppliers"];
  if (sheets.length !== expectedNames.length || sheets.some((sheet, index) => sheet.name !== expectedNames[index])) {
    throw new Error("Owner workbook reconciliation failed: worksheet responsibilities changed.");
  }
  for (const sheet of sheets) {
    if (sheet.sourceCount !== model.summary.medicineCount) {
      throw new Error(`Owner workbook reconciliation failed: ${sheet.name} uses a different medicine snapshot.`);
    }
    const header = sheet.rows[sheet.headerRow - 1] || [];
    if (!header.length || header.some((value) => !clean(value))) {
      throw new Error(`Owner workbook reconciliation failed: ${sheet.name} has a blank mandatory header.`);
    }
  }
  const overview = sheets[0];
  const summaryPairs = new Map(overview.rows.slice(4, 8).map((row) => [row[0], row[1]]));
  const expectedSummary = new Map([
    ["Total medicines", model.summary.medicineCount],
    ["Total stock value (KES)", model.summary.retailStockValue],
    ["Low stock count", model.summary.lowStockCount],
    ["Expiring soon count", model.summary.expiringSoonCount]
  ]);
  for (const [label, value] of expectedSummary) {
    if (summaryPairs.get(label) !== value) throw new Error(`Owner workbook reconciliation failed: ${label} does not match the export snapshot.`);
  }
  const canonicalNames = model.rows.map((row) => row.medicine).sort();
  const fullNames = sheets[1].rows.slice(sheets[1].headerRow).map((row) => row[0]).sort();
  const expiryNames = sheets[3].rows.slice(sheets[3].headerRow).map((row) => row[0]).sort();
  const supplierNames = sheets[4].rows.slice(sheets[4].headerRow).map((row) => row[1]).sort();
  for (const [sheetName, names] of [["Full Inventory", fullNames], ["Expiry Tracking", expiryNames], ["Suppliers", supplierNames]]) {
    if (names.length !== canonicalNames.length || names.some((name, index) => name !== canonicalNames[index])) {
      throw new Error(`Owner workbook reconciliation failed: ${sheetName} is missing or duplicating medicines.`);
    }
  }
  const sourceNames = new Set(canonicalNames);
  const lowStockNames = sheets[2].projectionCount ? sheets[2].rows.slice(sheets[2].headerRow).map((row) => row[0]) : [];
  const attentionNames = overview.projectionCount ? overview.rows.slice(overview.headerRow).map((row) => row[0]) : [];
  if ([...lowStockNames, ...attentionNames].some((name) => !sourceNames.has(name))) {
    throw new Error("Owner workbook reconciliation failed: an attention sheet contains a medicine outside the export snapshot.");
  }
  if (sheets[2].projectionCount !== model.summary.lowStockCount) {
    throw new Error("Owner workbook reconciliation failed: low-stock count does not match the export snapshot.");
  }
  return true;
}
function autoXlsxWidths(rows, caps) {
  return caps.map((cap, column) => Math.min(cap, Math.max(11, ...rows.map((row) => String(row[column] ?? "").length + 2))));
}
function buildXlsxSheetXml(sheet) {
  const maxColumns = Math.max(...sheet.rows.map((row) => row.length));
  const rowXml = sheet.rows.map((row, rowIndex) => {
    const rowNumber = rowIndex + 1;
    const isHeader = rowNumber === sheet.headerRow;
    const isData = rowNumber > sheet.headerRow;
    const height = rowNumber === 1 ? 32 : isHeader ? 30 : isData ? 25 : rowNumber <= 4 ? 22 : 24;
    return `<row r="${rowNumber}" ht="${height}" customHeight="1">${row.map((value, columnIndex) => {
      let style = 0;
      if (rowNumber === 1) style = 1;
      else if (isHeader) style = 2;
      else if (sheet.overview && rowNumber >= 5 && rowNumber <= 8 && columnIndex === 0) style = 6;
      else if (sheet.overview && rowNumber >= 5 && rowNumber <= 8 && columnIndex === 1) style = 7;
      else if (sheet.overview && rowNumber === 9) style = 8;
      else if (isData && sheet.alert) style = columnIndex === 2 ? 10 : (rowNumber - sheet.headerRow) % 2 === 0 ? 4 : 0;
      else if (isData) style = (rowNumber - sheet.headerRow) % 2 === 0 ? 4 : 0;
      if (typeof value === "number" && ![1, 2, 6, 7, 8, 10].includes(style)) style = style === 4 ? 5 : 3;
      return xlsxCell(value, rowNumber, columnIndex + 1, style);
    }).join("")}</row>`;
  }).join("");
  const widths = sheet.widths.map((width, index) => `<col min="${index + 1}" max="${index + 1}" width="${width}" customWidth="1"/>`).join("");
  const topLeft = `${columnName(sheet.freezeColumns + 1)}${sheet.freezeRows + 1}`;
  const pane = `<pane xSplit="${sheet.freezeColumns}" ySplit="${sheet.freezeRows}" topLeftCell="${topLeft}" activePane="bottomRight" state="frozen"/>`;
  const mergeXml = sheet.merges?.length ? `<mergeCells count="${sheet.merges.length}">${sheet.merges.map((ref) => `<mergeCell ref="${ref}"/>`).join("")}</mergeCells>` : "";
  const lastRow = Math.max(sheet.headerRow, sheet.rows.length);
  const filter = `<autoFilter ref="A${sheet.headerRow}:${columnName(maxColumns)}${lastRow}"/>`;
  return `<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0" showGridLines="0">${pane}<selection pane="bottomRight" activeCell="${topLeft}" sqref="${topLeft}"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="20"/><cols>${widths}</cols><sheetData>${rowXml}</sheetData>${mergeXml}${filter}<printOptions horizontalCentered="1"/><pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/><pageSetup orientation="landscape" paperSize="9" fitToWidth="1" fitToHeight="0"/></worksheet>`;
}
function xlsxCell(value, row, column, style) { const ref = `${columnName(column)}${row}`; return typeof value === "number" ? `<c r="${ref}" s="${style}"><v>${value}</v></c>` : `<c r="${ref}" s="${style}" t="inlineStr"><is><t>${xml(value)}</t></is></c>`; }
function columnName(value) { let result = ""; for (let n = value; n; n = Math.floor((n - 1) / 26)) result = String.fromCharCode(65 + ((n - 1) % 26)) + result; return result; }
function xlsxStyles() { return `<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0"/></numFmts><fonts count="5"><font><sz val="10"/><color rgb="FF19332F"/><name val="Aptos"/></font><font><b/><sz val="20"/><color rgb="FF086C5C"/><name val="Aptos Display"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Aptos"/></font><font><b/><sz val="10"/><color rgb="FF536B66"/><name val="Aptos"/></font><font><b/><sz val="15"/><color rgb="FF086C5C"/><name val="Aptos Display"/></font></fonts><fills count="7"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF086C5C"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF1F7F5"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEDF7F4"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFF3CD"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFDFF1EC"/></patternFill></fill></fills><borders count="3"><border/><border><right style="thin"><color rgb="FFE5ECEA"/></right><bottom style="thin"><color rgb="FFD9E5E1"/></bottom></border><border><bottom style="medium"><color rgb="FF086C5C"/></bottom></border></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="11"><xf fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf fontId="1" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf><xf fontId="2" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf><xf fontId="0" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="164" fontId="0" fillId="3" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf><xf fontId="3" fillId="4" borderId="1" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="164" fontId="4" fillId="4" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf><xf fontId="4" fillId="6" borderId="2" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf><xf fontId="0" fillId="5" borderId="1" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="164" fontId="3" fillId="5" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`; }
function wordP(text, style) { return `<w:p><w:pPr><w:pStyle w:val="${style}"/></w:pPr><w:r><w:t>${xml(text)}</w:t></w:r></w:p>`; }
function wordMedicineBlock(row) {
  const value = (key) => row[key] === "" ? "—" : row[key];
  return [
    wordP(`${value("medicine")} | ${value("strength")} | ${value("form")} | ${value("unit")}`, "Medicine"),
    wordP(`Selling price KES ${value("sellingPrice")} | Cost price KES ${value("costPrice")} | Stock ${value("stock")} | Supplier ${value("supplier")}`, "Detail"),
    wordP(`Barcode ${value("barcode")} | Batch ${value("batch")} | Expiry ${value("expiry")} | Shelf ${value("shelf")}`, "Trace")
  ].join("");
}
function wordStyles() { return `<?xml version="1.0"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:spacing w:after="80"/></w:pPr><w:rPr><w:rFonts w:ascii="Aptos"/><w:sz w:val="21"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:spacing w:after="100"/></w:pPr><w:rPr><w:b/><w:color w:val="086C5C"/><w:sz w:val="40"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:pPr><w:spacing w:after="50"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Meta"><w:name w:val="Meta"/><w:pPr><w:spacing w:after="80"/></w:pPr><w:rPr><w:color w:val="536B66"/><w:sz w:val="18"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Summary"><w:name w:val="Summary"/><w:pPr><w:spacing w:after="140"/></w:pPr><w:rPr><w:b/><w:color w:val="086C5C"/><w:sz w:val="19"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Medicine"><w:name w:val="Medicine"/><w:pPr><w:keepNext/><w:spacing w:before="110" w:after="35"/><w:pBdr><w:top w:val="single" w:sz="8" w:color="B7CDC8"/></w:pBdr></w:pPr><w:rPr><w:b/><w:color w:val="19332F"/><w:sz w:val="23"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Detail"><w:name w:val="Detail"/><w:pPr><w:keepNext/><w:spacing w:after="30"/></w:pPr><w:rPr><w:sz w:val="20"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Trace"><w:name w:val="Trace"/><w:pPr><w:spacing w:after="70"/></w:pPr><w:rPr><w:color w:val="536B66"/><w:sz w:val="18"/></w:rPr></w:style></w:styles>`; }
function titleSlide(model) { return slideXml([shapeText(1, model.title, 700000, 1150000, 10800000, 900000, 5000, true, "086C5C"), shapeText(2, `${model.pharmacyName}\n${model.branch} | ${model.location}`, 700000, 2500000, 10800000, 1200000, 2400, false, "19332F"), shapeText(3, `${model.rows.length} medicines\nGenerated ${model.generatedKenya} Africa/Nairobi`, 700000, 4300000, 10800000, 1000000, 1800, false, "536B66")]); }
function tableSlide(model, rows, index, total) {
  const headers = ["Medicine", "Identity", "Prices", "Stock", "Supplier", "Traceability", "Expiry / shelf"];
  const widths = [1900000, 1800000, 1250000, 800000, 1800000, 2250000, 1700000];
  const values = (row) => [
    row.medicine, [row.strength, row.form, row.unit].filter(Boolean).join("\n"),
    `Sell ${row.sellingPrice || "—"}\nCost ${row.costPrice || "—"}`, String(row.stock === "" ? "—" : row.stock),
    row.supplier || "—", `Barcode ${row.barcode || "—"}\nBatch ${row.batch || "—"}`, `Expiry ${row.expiry || "—"}\nShelf ${row.shelf || "—"}`
  ];
  let y = 1300000;
  const shapes = [shapeText(1, `${model.title} | ${index} of ${total}`, 500000, 250000, 11200000, 650000, 3500, true, "086C5C")];
  let id = 2; let x = 350000;
  headers.forEach((header, i) => { shapes.push(shapeText(id++, header, x, y, widths[i], 500000, 1600, true, "FFFFFF", "086C5C")); x += widths[i]; });
  y += 500000;
  rows.forEach((row, r) => { x = 350000; values(row).forEach((value, i) => { shapes.push(shapeText(id++, value, x, y, widths[i], 780000, 1600, i === 0, "19332F", r % 2 ? "F1F7F5" : "FFFFFF")); x += widths[i]; }); y += 780000; });
  shapes.push(shapeText(id, `${model.pharmacyName} | ${model.branch} | ${model.location} | Generated ${model.generatedKenya}`, 500000, 6250000, 11200000, 300000, 1200, false, "536B66"));
  return slideXml(shapes);
}
function slideXml(shapes) { return `<?xml version="1.0"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="0" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>${shapes.join("")}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`; }
function shapeText(id, text, x, y, cx, cy, size, bold, color, fill = "FFFFFF") { return `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="Text ${id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="${fill}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="70000" rIns="70000" tIns="35000" bIns="35000"/><a:lstStyle/><a:p><a:r><a:rPr lang="en-KE" sz="${size}" b="${bold ? 1 : 0}"><a:solidFill><a:srgbClr val="${color}"/></a:solidFill></a:rPr><a:t>${xml(text)}</a:t></a:r><a:endParaRPr lang="en-KE"/></a:p></p:txBody></p:sp>`; }
function slideMaster() { return `<?xml version="1.0"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>`; }
function slideLayout() { return `<?xml version="1.0"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld></p:sldLayout>`; }
function pptTheme() { return `<?xml version="1.0"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="MS2.0"><a:themeElements><a:clrScheme name="MS2.0"><a:dk1><a:srgbClr val="19332F"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="536B66"/></a:dk2><a:lt2><a:srgbClr val="F1F7F5"/></a:lt2><a:accent1><a:srgbClr val="086C5C"/></a:accent1><a:accent2><a:srgbClr val="C9D8D4"/></a:accent2><a:accent3><a:srgbClr val="58A696"/></a:accent3><a:accent4><a:srgbClr val="D3A229"/></a:accent4><a:accent5><a:srgbClr val="7E9B95"/></a:accent5><a:accent6><a:srgbClr val="B7CDC8"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="MS2.0"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme><a:fmtScheme name="MS2.0"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme></a:themeElements></a:theme>`; }
function pdfPage(model, rows, page, total) {
  const lines = [];
  const t = (x, y, size, text, bold = false) => lines.push(`BT /F${bold ? 2 : 1} ${size} Tf ${x} ${y} Td (${pdfEscape(text)}) Tj ET`);
  const rule = (y) => lines.push(`0.72 0.82 0.80 RG 0.8 w 36 ${y} m 806 ${y} l S`);
  t(36, 557, 20, model.title, true);
  t(36, 536, 10, `${model.pharmacyName} | ${model.branch} | ${model.location}`);
  t(36, 520, 9, `Generated ${model.generatedKenya} Africa/Nairobi | Page ${page} of ${total}`);
  t(742, 557, 9, `${model.rows.length} medicines`, true);
  rows.forEach((row, index) => {
    const y = 483 - index * 65;
    rule(y + 17);
    t(42, y, 11, row.medicine || "Unnamed medicine", true);
    t(220, y, 9, `${row.strength || "—"} | ${row.form || "—"} | ${row.unit || "—"}`);
    t(510, y, 9, `Sell KES ${row.sellingPrice === "" ? "—" : row.sellingPrice} | Cost KES ${row.costPrice === "" ? "—" : row.costPrice} | Stock ${row.stock === "" ? "—" : row.stock}`, true);
    t(42, y - 18, 9, `Supplier: ${truncate(row.supplier || "—", 40)}`);
    t(360, y - 18, 9, `Barcode: ${row.barcode || "—"} | Batch: ${row.batch || "—"}`);
    t(650, y - 18, 9, `Expiry: ${row.expiry || "—"} | Shelf: ${row.shelf || "—"}`);
  });
  t(36, 24, 8, `${model.rows.length} canonical medicine records | Pharmacy-isolated | Generated locally by MS2.0 with zero AI formatting.`);
  return lines.join("\n");
}
function rels(values) { return `<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${values.map(([id, type, target]) => `<Relationship Id="${id}" Type="${type}" Target="${target}"/>`).join("")}</Relationships>`; }
function coreProps(model) { return `<?xml version="1.0"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>${xml(model.title)}</dc:title><dc:creator>MS2.0</dc:creator><cp:lastModifiedBy>MS2.0</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">${model.generatedIso}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">${model.generatedIso}</dcterms:modified></cp:coreProperties>`; }
function appProps(application) { return `<?xml version="1.0"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>${application}</Application><AppVersion>1.0</AppVersion></Properties>`; }
function entry(name, contents) { return { name, contents }; }
function chunk(values, size) { const result = []; for (let i = 0; i < values.length; i += size) result.push(values.slice(i, i + size)); return result; }
function balancedChunks(values, maximum) {
  if (!values.length) return [[]];
  const pageCount = Math.ceil(values.length / maximum);
  const base = Math.floor(values.length / pageCount);
  const extra = values.length % pageCount;
  const result = [];
  let offset = 0;
  for (let page = 0; page < pageCount; page += 1) {
    const size = base + (page < extra ? 1 : 0);
    result.push(values.slice(offset, offset + size));
    offset += size;
  }
  return result;
}
function first(value) { return Array.isArray(value) ? value[0] || "" : ""; }
function clean(value) { return String(value ?? "").trim(); }
function numberOrBlank(value) { if (value === "" || value == null) return ""; const number = Number(value); return Number.isFinite(number) ? number : clean(value); }
function csvCell(value) { const text = String(value ?? ""); return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text; }
function kenyaTime(date) { return new Intl.DateTimeFormat("en-KE", { timeZone: "Africa/Nairobi", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(date); }
function pdfEscape(value) { return String(value ?? "").replace(/[^\x20-\x7e]/g, "-").replaceAll("\\", "\\\\").replaceAll("(", "\\(").replaceAll(")", "\\)"); }
function truncate(value, max) { const text = String(value ?? ""); return text.length > max ? `${text.slice(0, max - 1)}.` : text; }
