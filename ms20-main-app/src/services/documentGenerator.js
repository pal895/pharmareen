import { buildStoredZip, xml } from "./ooxmlPackage.js";
import { buildMedicineFinderIndex, medicineFinderClientScript } from "./medicineFinder.js";

export const EXPORT_FORMATS = Object.freeze([
  { id: "csv", label: "CSV", help: "Machine-readable; best opened in Excel or Google Sheets" },
  { id: "xlsx", label: "Excel", help: "Formatted workbook for sorting, filtering and review" },
  { id: "pdf", label: "PDF", help: "Fixed, paginated owner copy" },
  { id: "docx", label: "Word", help: "Editable professional document" },
  { id: "pptx", label: "Presentation", help: "Landscape inventory briefing slides" },
  { id: "print", label: "Print", help: "Print-ready browser layout" }
]);

const COLUMNS = Object.freeze([
  ["medicine", "Medicine"], ["strength", "Strength"], ["form", "Form"], ["unit", "Unit"],
  ["sellingPrice", "Selling price (KES)"], ["costPrice", "Cost price (KES)"], ["stock", "Stock"],
  ["supplier", "Supplier"], ["barcode", "Barcode"], ["batch", "Batch"], ["expiry", "Expiry"], ["shelf", "Shelf"]
]);

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
      supplier: clean(item?.supplier || batch.supplier), barcode: clean(item?.barcode),
      batch: clean(batch.batch || item?.batch), expiry: clean(batch.expiry || item?.expiry),
      shelf: clean(item?.shelf || item?.location)
    });
  });
  return Object.freeze({
    schema: "ms20.inventory-export.v1", pharmacyId,
    pharmacyName: clean(pharmacy?.name) || "Pharmacy",
    branch: clean(pharmacy?.branch) || "Main", location: clean(pharmacy?.location) || "Kenya",
    generatedIso: instant.toISOString(), generatedKenya: kenyaTime(instant),
    title: "Pharmacy Inventory", columns: COLUMNS, rows: Object.freeze(rows), finderIndex
  });
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
  const rows = [
    [model.title], ["Pharmacy", model.pharmacyName], ["Branch", model.branch],
    ["Location", model.location], ["Generated (Africa/Nairobi)", model.generatedKenya], [],
    COLUMNS.map(([, label]) => label), ...model.rows.map((row) => COLUMNS.map(([key]) => row[key]))
  ];
  const sheetRows = rows.map((row, r) => `<row r="${r + 1}"${r === 0 ? ' ht="28" customHeight="1"' : ""}>${row.map((value, c) => xlsxCell(value, r + 1, c + 1, r === 0 ? 1 : r === 6 ? 2 : 0)).join("")}</row>`).join("");
  const widths = [24, 13, 12, 11, 18, 16, 11, 22, 18, 15, 14, 11];
  return buildStoredZip([
    ["[Content_Types].xml", `<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>`],
    ["_rels/.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "xl/workbook.xml"], ["rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"], ["rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties", "docProps/app.xml"]])],
    ["xl/workbook.xml", `<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Inventory" sheetId="1" r:id="rId1"/></sheets></workbook>`],
    ["xl/_rels/workbook.xml.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", "worksheets/sheet1.xml"], ["rId2", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "styles.xml"]])],
    ["xl/worksheets/sheet1.xml", `<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="7" topLeftCell="A8" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>${widths.map((width, i) => `<col min="${i + 1}" max="${i + 1}" width="${width}" customWidth="1"/>`).join("")}</cols><sheetData>${sheetRows}</sheetData><autoFilter ref="A7:L${Math.max(7, rows.length)}"/><pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/><pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0"/></worksheet>`],
    ["xl/styles.xml", xlsxStyles()], ["docProps/core.xml", coreProps(model)], ["docProps/app.xml", appProps("Microsoft Excel")]
  ].map(([name, contents]) => ({ name, contents })));
}

export function buildInventoryDocx(model) {
  const headers = COLUMNS.map(([, label]) => wordCell(label, true)).join("");
  const body = model.rows.map((row) => `<w:tr>${COLUMNS.map(([key]) => wordCell(row[key], false)).join("")}</w:tr>`).join("");
  const document = `<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${wordP(model.title, "Title")}${wordP(`${model.pharmacyName} | ${model.branch} | ${model.location}`, "Subtitle")}${wordP(`Generated ${model.generatedKenya} Africa/Nairobi`, "Meta")}<w:tbl><w:tblPr><w:tblStyle w:val="InventoryTable"/><w:tblW w:w="0" w:type="auto"/><w:tblLayout w:type="autofit"/></w:tblPr><w:tblGrid/> <w:tr>${headers}</w:tr>${body}</w:tbl><w:p/><w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/><w:pgMar w:top="720" w:right="576" w:bottom="720" w:left="576" w:header="360" w:footer="360"/></w:sectPr></w:body></w:document>`;
  return buildStoredZip([
    entry("[Content_Types].xml", `<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>`),
    entry("_rels/.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "word/document.xml"], ["rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"], ["rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties", "docProps/app.xml"]])),
    entry("word/document.xml", document), entry("word/_rels/document.xml.rels", rels([["rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "styles.xml"]])),
    entry("word/styles.xml", wordStyles()), entry("docProps/core.xml", coreProps(model)), entry("docProps/app.xml", appProps("Microsoft Word"))
  ]);
}

export function buildInventoryPptx(model) {
  const chunks = chunk(model.rows, 12);
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
  const rowsPerPage = 24;
  const pages = chunk(model.rows, rowsPerPage);
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

export function buildPrintHtml(model, { bridgeId = "" } = {}) {
  const cells = (row) => COLUMNS.map(([key, label]) => `<td data-label="${xml(label)}">${xml(row[key] === "" ? "—" : row[key])}</td>`).join("");
  const detailRows = (row) => COLUMNS.map(([key, label]) => `<div class="field"><strong>${xml(label)}</strong><span>${xml(row[key] === "" ? "—" : row[key])}</span></div>`).join("");
  const mobileCards = model.rows.map((row, index) => `<details class="medicine-card" data-finder-id="${xml(row.finderId)}"${index === 0 ? " open" : ""}><summary><span><strong>${xml(row.medicine || "Unnamed medicine")}</strong><small>${xml([row.strength, row.form, row.unit].filter(Boolean).join(" · ") || "Details not recorded")}</small></span><span class="quick-facts"><b>Stock ${xml(row.stock === "" ? "—" : row.stock)}</b><small>KES ${xml(row.sellingPrice === "" ? "—" : row.sellingPrice)}</small></span></summary><div class="details-grid">${detailRows(row)}</div></details>`).join("");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>MS2.0 | ${xml(model.title)} | Print preview</title><style>
  :root{font-family:Arial,sans-serif;color:#19332f;background:#eef5f3;color-scheme:light}*{box-sizing:border-box}body{margin:0}.page{max-width:1200px;margin:0 auto;padding:20px}.toolbar{position:sticky;top:0;z-index:2;display:flex;gap:10px;align-items:center;padding:12px 0;background:#eef5f3}.action{min-height:46px;padding:10px 18px;border:1px solid #086c5c;border-radius:24px;background:#086c5c;color:#fff;font:700 16px Arial;cursor:pointer}.action.secondary{background:#fff;color:#086c5c}.eyebrow{margin:8px 0 4px;color:#536b66;font-size:14px;font-weight:700}h1{margin:0 0 8px;color:#086c5c;font-size:30px}.meta{margin:0 0 10px;font-size:16px;line-height:1.5}.summary{margin:0 0 18px;padding:12px 14px;border-left:5px solid #086c5c;background:#dff1ec;font-size:16px}.mobile-review{display:none}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;background:#fff;font-size:12px}th{background:#086c5c;color:#fff;text-align:left}th,td{padding:7px;border:1px solid #c9d8d4;vertical-align:top;overflow-wrap:anywhere}tbody tr:nth-child(even){background:#f1f7f5}footer{margin:16px 0;color:#536b66;line-height:1.5}
  @media(max-width:720px){.page{padding:14px}.toolbar{justify-content:stretch}.action{flex:1;padding:10px 12px}h1{font-size:26px}.meta,.summary{font-size:15px}.table-wrap{display:none}.mobile-review{display:block}.finder-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}.finder-action{min-height:46px;border:1px solid #086c5c;border-radius:23px;background:#fff;color:#086c5c;font:700 15px Arial}.search-label{display:block;margin:0 0 8px;font-weight:700}.search{width:100%;min-height:48px;margin-bottom:10px;padding:10px 14px;border:1px solid #7e9b95;border-radius:12px;background:#fff;color:#19332f;font:16px Arial}.filter{width:100%;min-height:46px;margin-bottom:10px;padding:8px 12px;border:1px solid #7e9b95;border-radius:12px;background:#fff;color:#19332f;font:15px Arial}.review-help{margin:0 0 12px;color:#536b66;font-size:14px}.medicine-list{display:grid;gap:10px}.medicine-card{border:1px solid #b7cdc8;border-radius:14px;background:#fff;box-shadow:0 2px 8px rgba(25,51,47,.06);overflow:hidden}.medicine-card[hidden]{display:none}.medicine-card summary{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;min-height:68px;padding:12px 14px;cursor:pointer}.medicine-card summary>span:first-child{display:grid;gap:4px}.medicine-card summary strong{font-size:17px}.medicine-card small{color:#536b66;font-size:13px}.quick-facts{display:grid;gap:4px;text-align:right}.quick-facts b{color:#086c5c;font-size:14px}.details-grid{border-top:1px solid #d6e3df}.field{display:grid;grid-template-columns:minmax(112px,42%) 1fr;gap:10px;min-height:42px;padding:10px 12px;border-bottom:1px solid #e1ebe8;font-size:15px;line-height:1.35}.field:last-child{border-bottom:0}.field strong{color:#536b66}footer{font-size:14px}}
  @page{size:A4 landscape;margin:10mm}@media print{:root{background:#fff}.page{max-width:none;margin:0;padding:0}.toolbar,.eyebrow,.summary,.mobile-review{display:none}.table-wrap{display:block;overflow:visible}h1{font-size:20px}.meta{font-size:10px;margin-bottom:12px}table{display:table;font-size:8px}thead{display:table-header-group;position:static;width:auto;height:auto;overflow:visible;clip:auto}tbody{display:table-row-group}tbody tr{display:table-row;box-shadow:none}th,td{display:table-cell;min-height:0;padding:4px;border:1px solid #c9d8d4;line-height:1.2}td::before{display:none}footer{font-size:8px;margin-top:8px}}
  </style></head><body><main class="page"><div class="toolbar"><button class="action" type="button" onclick="window.print()">Print inventory</button><button class="action secondary" type="button" onclick="window.close()">Close view</button></div><p class="eyebrow">Review before printing</p><h1>${xml(model.title)}</h1><p class="meta"><strong>${xml(model.pharmacyName)}</strong><br>${xml(model.branch)} · ${xml(model.location)}<br>Generated ${xml(model.generatedKenya)} Africa/Nairobi</p><p class="summary">${model.rows.length} canonical medicine records · Pharmacy-isolated · Generated locally with zero AI formatting</p><section class="mobile-review" aria-label="Mobile inventory review"><label class="search-label" for="medicine-search">Fast medicine finder</label><div class="finder-actions"><button class="finder-action" id="finder-scan" type="button">Scan barcode</button><button class="finder-action" id="finder-voice" type="button">Speak medicine</button></div><p class="review-help" id="finder-status" aria-live="polite"></p><select class="filter" id="medicine-filter" aria-label="Quick medicine filter"><option value="all">All medicines</option><option value="lowStock">Low stock</option><option value="outOfStock">Out of stock</option><option value="expiringSoon">Expiring soon</option><option value="az">A–Z</option></select><label class="search-label" for="medicine-search">Type only if needed</label><input class="search" id="medicine-search" type="search" placeholder="Name, alias, strength, form, unit, barcode, supplier, shelf or batch" autocomplete="off"><p class="review-help" id="review-count">${model.rows.length} of ${model.rows.length} medicines shown · Tap a medicine to view every field.</p><div class="medicine-list">${mobileCards}</div></section><div class="table-wrap"><table><thead><tr>${COLUMNS.map(([, label]) => `<th>${xml(label)}</th>`).join("")}</tr></thead><tbody>${model.rows.map((row) => `<tr>${cells(row)}</tr>`).join("")}</tbody></table></div><footer>${model.rows.length} canonical medicine records. Generated locally by MS2.0 with no AI formatting.</footer></main><script>${medicineFinderClientScript(model.finderIndex, { bridgeId })}</script></body></html>`;
}

export function exportFilename(model, extension) {
  const pharmacy = model.pharmacyName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "pharmacy";
  return `${pharmacy}-inventory-${model.generatedIso.slice(0, 10)}.${extension}`;
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

function xlsxCell(value, row, column, style) { const ref = `${columnName(column)}${row}`; return typeof value === "number" ? `<c r="${ref}" s="${style}"><v>${value}</v></c>` : `<c r="${ref}" s="${style}" t="inlineStr"><is><t>${xml(value)}</t></is></c>`; }
function columnName(value) { let result = ""; for (let n = value; n; n = Math.floor((n - 1) / 26)) result = String.fromCharCode(65 + ((n - 1) % 26)) + result; return result; }
function xlsxStyles() { return `<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="3"><font><sz val="10"/><name val="Aptos"/></font><font><b/><sz val="18"/><color rgb="FF086C5C"/><name val="Aptos Display"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Aptos"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF086C5C"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="3"><xf fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf fontId="1" fillId="0" borderId="0" xfId="0"/><xf fontId="2" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`; }
function wordP(text, style) { return `<w:p><w:pPr><w:pStyle w:val="${style}"/></w:pPr><w:r><w:t>${xml(text)}</w:t></w:r></w:p>`; }
function wordCell(value, header) { return `<w:tc><w:tcPr><w:shd w:fill="${header ? "086C5C" : "FFFFFF"}"/></w:tcPr><w:p><w:r><w:rPr>${header ? '<w:b/><w:color w:val="FFFFFF"/>' : ""}<w:sz w:val="16"/></w:rPr><w:t>${xml(value)}</w:t></w:r></w:p></w:tc>`; }
function wordStyles() { return `<?xml version="1.0"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Aptos"/><w:sz w:val="20"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:color w:val="086C5C"/><w:sz w:val="40"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Meta"><w:name w:val="Meta"/><w:rPr><w:color w:val="536B66"/><w:sz w:val="18"/></w:rPr></w:style><w:style w:type="table" w:styleId="InventoryTable"><w:name w:val="Inventory Table"/><w:tblPr><w:tblBorders><w:top w:val="single" w:color="C9D8D4"/><w:left w:val="single" w:color="C9D8D4"/><w:bottom w:val="single" w:color="C9D8D4"/><w:right w:val="single" w:color="C9D8D4"/><w:insideH w:val="single" w:color="C9D8D4"/><w:insideV w:val="single" w:color="C9D8D4"/></w:tblBorders></w:tblPr></w:style></w:styles>`; }
function titleSlide(model) { return slideXml([shapeText(1, model.title, 700000, 1150000, 10800000, 900000, 3000, true, "086C5C"), shapeText(2, `${model.pharmacyName}\n${model.branch} | ${model.location}`, 700000, 2350000, 10800000, 1100000, 1800, false, "19332F"), shapeText(3, `${model.rows.length} medicines\nGenerated ${model.generatedKenya} Africa/Nairobi`, 700000, 4100000, 10800000, 900000, 1400, false, "536B66")]); }
function tableSlide(model, rows, index, total) { const headers = ["Medicine", "Strength", "Form", "Stock", "Sell KES", "Cost KES", "Supplier", "Expiry", "Shelf"]; const keys = ["medicine", "strength", "form", "stock", "sellingPrice", "costPrice", "supplier", "expiry", "shelf"]; const widths = [2500000, 1100000, 900000, 700000, 900000, 900000, 1900000, 1100000, 750000]; let y = 1450000; const shapes = [shapeText(1, `${model.title} - ${index} of ${total}`, 500000, 300000, 11200000, 600000, 2200, true, "086C5C")]; let id = 2; let x = 350000; headers.forEach((header, i) => { shapes.push(shapeText(id++, header, x, y, widths[i], 360000, 850, true, "FFFFFF", "086C5C")); x += widths[i]; }); y += 360000; rows.forEach((row, r) => { x = 350000; keys.forEach((key, i) => { shapes.push(shapeText(id++, row[key], x, y, widths[i], 360000, 760, false, "19332F", r % 2 ? "F1F7F5" : "FFFFFF")); x += widths[i]; }); y += 360000; }); shapes.push(shapeText(id, `${model.pharmacyName} | Generated ${model.generatedKenya}`, 500000, 6400000, 11200000, 250000, 700, false, "536B66")); return slideXml(shapes); }
function slideXml(shapes) { return `<?xml version="1.0"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="0" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>${shapes.join("")}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`; }
function shapeText(id, text, x, y, cx, cy, size, bold, color, fill = "FFFFFF") { return `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="Text ${id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="${fill}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="70000" rIns="70000" tIns="35000" bIns="35000"/><a:lstStyle/><a:p><a:r><a:rPr lang="en-KE" sz="${size}" b="${bold ? 1 : 0}"><a:solidFill><a:srgbClr val="${color}"/></a:solidFill></a:rPr><a:t>${xml(text)}</a:t></a:r><a:endParaRPr lang="en-KE"/></a:p></p:txBody></p:sp>`; }
function slideMaster() { return `<?xml version="1.0"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>`; }
function slideLayout() { return `<?xml version="1.0"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld></p:sldLayout>`; }
function pptTheme() { return `<?xml version="1.0"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="MS2.0"><a:themeElements><a:clrScheme name="MS2.0"><a:dk1><a:srgbClr val="19332F"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="536B66"/></a:dk2><a:lt2><a:srgbClr val="F1F7F5"/></a:lt2><a:accent1><a:srgbClr val="086C5C"/></a:accent1><a:accent2><a:srgbClr val="C9D8D4"/></a:accent2><a:accent3><a:srgbClr val="58A696"/></a:accent3><a:accent4><a:srgbClr val="D3A229"/></a:accent4><a:accent5><a:srgbClr val="7E9B95"/></a:accent5><a:accent6><a:srgbClr val="B7CDC8"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="MS2.0"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme><a:fmtScheme name="MS2.0"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme></a:themeElements></a:theme>`; }
function pdfPage(model, rows, page, total) { const lines = []; const t = (x, y, size, text, bold = false) => lines.push(`BT /F${bold ? 2 : 1} ${size} Tf ${x} ${y} Td (${pdfEscape(text)}) Tj ET`); t(36, 555, 20, model.title, true); t(36, 533, 10, `${model.pharmacyName} | ${model.branch} | ${model.location}`); t(36, 517, 9, `Generated ${model.generatedKenya} Africa/Nairobi | Page ${page} of ${total}`); const headers = ["Medicine", "Strength", "Form", "Stock", "Sell", "Cost", "Supplier", "Expiry", "Shelf"]; const keys = ["medicine", "strength", "form", "stock", "sellingPrice", "costPrice", "supplier", "expiry", "shelf"]; const xs = [36, 190, 255, 310, 350, 395, 440, 615, 725]; headers.forEach((h, i) => t(xs[i], 490, 7, h, true)); rows.forEach((row, r) => keys.forEach((key, i) => t(xs[i], 474 - r * 17, 7, truncate(row[key], i === 0 ? 24 : i === 6 ? 26 : 14)))); t(36, 28, 8, `${model.rows.length} canonical medicine records | Generated locally with zero AI formatting.`); return lines.join("\n"); }
function rels(values) { return `<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${values.map(([id, type, target]) => `<Relationship Id="${id}" Type="${type}" Target="${target}"/>`).join("")}</Relationships>`; }
function coreProps(model) { return `<?xml version="1.0"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>${xml(model.title)}</dc:title><dc:creator>MS2.0</dc:creator><cp:lastModifiedBy>MS2.0</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">${model.generatedIso}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">${model.generatedIso}</dcterms:modified></cp:coreProperties>`; }
function appProps(application) { return `<?xml version="1.0"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>${application}</Application><AppVersion>1.0</AppVersion></Properties>`; }
function entry(name, contents) { return { name, contents }; }
function chunk(values, size) { const result = []; for (let i = 0; i < values.length; i += size) result.push(values.slice(i, i + size)); return result; }
function first(value) { return Array.isArray(value) ? value[0] || "" : ""; }
function clean(value) { return String(value ?? "").trim(); }
function numberOrBlank(value) { if (value === "" || value == null) return ""; const number = Number(value); return Number.isFinite(number) ? number : clean(value); }
function csvCell(value) { const text = String(value ?? ""); return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text; }
function kenyaTime(date) { return new Intl.DateTimeFormat("en-KE", { timeZone: "Africa/Nairobi", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(date); }
function pdfEscape(value) { return String(value ?? "").replace(/[^\x20-\x7e]/g, "-").replaceAll("\\", "\\\\").replaceAll("(", "\\(").replaceAll(")", "\\)"); }
function truncate(value, max) { const text = String(value ?? ""); return text.length > max ? `${text.slice(0, max - 1)}.` : text; }
