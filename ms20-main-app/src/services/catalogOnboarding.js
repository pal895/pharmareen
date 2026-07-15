import { SupportedForms } from "../data/sourceMedicines.js";
import { normalizeExpiryValue } from "./medicineFieldSchema.js";

const CATALOG_TEXT_HEADER = "medicine | form | unit | selling price | cost price | stock | supplier | barcode | batch | expiry | strength | pack size | shelf";

export const CatalogOnboardingMethods = [
  {
    id: "invoice",
    label: "Invoice or delivery note",
    ownerText: "Take or upload an invoice/photo."
  },
  {
    id: "scan",
    label: "Scan shelves or medicines",
    ownerText: "Scan shelves, drawers, boxes, or barcodes."
  },
  {
    id: "paste",
    label: "Paste medicine list",
    ownerText: "Paste a list from your old system, supplier, or notes."
  },
  {
    id: "file",
    label: "Upload CSV or old POS export",
    ownerText: "Upload CSV, XLSX, or text from your old system."
  },
  {
    id: "sell",
    label: "Add while selling",
    ownerText: "Use only for missing medicines during a sale."
  }
];

export function createCatalogChoiceCard() {
  return {
    id: `card-catalog-choice-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    type: "CatalogOnboardingCard",
    title: "Add your medicines",
    source: "MS2.0 setup",
    confidence: 0.95,
    status: "ready",
    aiRequired: false,
    fields: {
      question: "How would you like to show me your pharmacy?",
      choices: CatalogOnboardingMethods.map((method) => method.ownerText).join("\n")
    },
    validation: "Choose one method. MS2.0 will prepare a review card before saving."
  };
}

export function createPasteImportCard(seedText = "") {
  const preparedText = seedText.trim();
  return {
    id: `card-catalog-paste-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    type: "CatalogImportCard",
    title: "Review medicine list",
    source: "Bulk paste",
    confidence: preparedText ? 0.82 : 0.65,
    status: "needs_correction",
    aiRequired: false,
    fields: {
      method: "bulk paste",
      entry_mode: preparedText ? "review" : "paste_input",
      items_text: preparedText,
      notes: "One medicine per line. Price can be the last number."
    },
    validation: "MS2.0 parses this locally, then saves approved medicines to this pharmacy."
  };
}

export function parseBulkMedicineList(text, sourceBrain) {
  const lines = String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const items = [];
  const unclear = [];
  const seen = new Set();

  for (const line of lines) {
    const item = parseMedicineLine(line, sourceBrain);
    if (!item.name) {
      unclear.push({ line, reason: "missing medicine name" });
      continue;
    }
    const key = normalize(item.name);
    if (seen.has(key)) {
      item.duplicate = true;
    }
    seen.add(key);
    items.push(item);
  }

  return {
    source: "bulk_paste",
    items,
    unclear,
    duplicates: items.filter((item) => item.duplicate),
    aiRequired: false
  };
}

export function partitionCatalogItems(items = [], catalog = []) {
  const existingNames = new Set(catalog.map((item) => normalize(item.name || item.medicine)));
  return items.reduce((result, item) => {
    result[existingNames.has(normalize(item.name || item.medicine)) ? "existing" : "newItems"].push(item);
    return result;
  }, { newItems: [], existing: [] });
}

export function parseCatalogText(text) {
  const rows = String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !line.toLowerCase().startsWith("medicine |"));

  return rows.map((row) => {
    const parts = row.split("|").map((part) => part.trim());
    return cleanCatalogItem({
      name: parts[0],
      strength: parts[10],
      pack_size: parts[11],
      form: parts[1],
      unit: parts[2],
      selling_price: parts[3],
      cost_price: parts[4],
      stock: parts[5],
      supplier: parts[6],
      barcode: parts[7],
      batch: parts[8],
      expiry: parts[9],
      shelf: parts[12]
    });
  }).filter((item) => item.name);
}

export function catalogItemsToText(items) {
  const rows = items.map((item) => [
    item.name,
    item.form || first(item.forms),
    item.unit || first(item.units),
    item.selling_price || item.sellingPrice || "",
    item.cost_price || item.costPrice || "",
    item.stock ?? item.stockLeft ?? "",
    item.supplier || "",
    item.barcode || "",
    item.batch || "",
    item.expiry || "",
    item.strength || "",
    item.pack_size || first(item.packSizes),
    item.shelf || item.location || ""
  ].map((value) => String(value ?? "")).join(" | "));
  return [CATALOG_TEXT_HEADER, ...rows].join("\n");
}

export function parseDelimitedInventory(text, sourceBrain) {
  const lines = String(text || "").split(/\r?\n/).filter((line) => line.trim());
  if (lines.length === 0) return { items: [], mapping: {}, unclear: ["empty file"], aiRequired: false };
  const delimiter = detectDelimiter(lines[0]);
  const headers = lines[0].split(delimiter).map((header) => normalize(header));
  const mapping = mapHeaders(headers);
  const items = [];
  const unclear = [];

  for (const line of lines.slice(1)) {
    const cells = line.split(delimiter).map((cell) => cell.trim());
    const rawName = cells[mapping.name] || "";
    if (!rawName) {
      unclear.push(`Missing medicine name: ${line}`);
      continue;
    }
    const sourceMatch = sourceBrain?.lookupMedicine(rawName);
    items.push(cleanCatalogItem({
      name: sourceMatch?.status === "matched" ? sourceMatch.name : rawName,
      strength: cells[mapping.strength] || "",
      pack_size: cells[mapping.pack_size] || "",
      form: cells[mapping.form] || first(sourceMatch?.forms),
      unit: cells[mapping.unit] || first(sourceMatch?.units),
      selling_price: cells[mapping.selling_price] || "",
      cost_price: cells[mapping.cost_price] || "",
      stock: cells[mapping.stock] || "",
      supplier: cells[mapping.supplier] || "",
      barcode: cells[mapping.barcode] || "",
      batch: cells[mapping.batch] || "",
      expiry: cells[mapping.expiry] || "",
      shelf: cells[mapping.shelf] || "",
      source: sourceMatch?.status === "matched" ? "source_brain_match" : "pharmacy_import"
    }));
  }

  return { items, mapping, unclear, aiRequired: false };
}

export function buildImportSummary(items, unclear = []) {
  return [
    `${items.length} medicine(s) ready for review.`,
    unclear.length ? `${unclear.length} line(s) need attention.` : "No unclear lines found.",
    "Approve only after checking names, prices, stock, batch, and expiry."
  ].join(" ");
}

export function buildCatalogSavedSummary(items, unclear = []) {
  return [
    `${items.length} medicine(s) saved.`,
    unclear.length ? `${unclear.length} line(s) still need attention.` : "No unclear lines found.",
    "Catalog is ready for daily sales."
  ].join(" ");
}

function parseMedicineLine(line, sourceBrain) {
  const price = line.match(/(?:^|\s)(\d+(?:\.\d{1,2})?)\s*$/)?.[1] || "";
  const withoutPrice = price ? line.replace(new RegExp(`\\s${escapeRegex(price)}\\s*$`), "").trim() : line;
  const strength = withoutPrice.match(/\b\d+(?:\.\d+)?\s?(?:mg|ml|mcg|g|iu|%)\b/i)?.[0] || "";
  const form = inferForm(withoutPrice);
  const sourceMatch = sourceBrain?.lookupMedicine(withoutPrice.replace(strength, "").replace(form, "").trim());
  const name = sourceMatch?.status === "matched"
    ? sourceMatch.name
    : withoutPrice.replace(strength, "").replace(new RegExp(`\\b${escapeRegex(form)}s?\\b`, "i"), "").trim();

  return cleanCatalogItem({
    name,
    strength,
    form: form || first(sourceMatch?.forms),
    unit: inferUnit(form, sourceMatch),
    selling_price: price,
    source: sourceMatch?.status === "matched" ? "source_brain_match" : "owner_list"
  });
}

function cleanCatalogItem(item) {
  const batch = item.batch || "";
  const expiry = normalizeExpiryValue(item.expiry || "");
  return {
    name: titleCase(item.name || ""),
    strength: item.strength || "",
    form: normalizeForm(item.form || ""),
    unit: normalizeForm(item.unit || item.form || ""),
    pack_size: item.pack_size || "",
    selling_price: item.selling_price || item.sellingPrice || "",
    cost_price: item.cost_price || item.costPrice || "",
    stock: item.stock || item.current_stock || "",
    supplier: item.supplier || "",
    barcode: item.barcode || "",
    batch,
    expiry,
    shelf: item.shelf || "",
    batches: batch || expiry ? [{ batch, expiry, quantity: item.stock || "", supplier: item.supplier || "" }] : [],
    source: item.source || "owner_review"
  };
}

function detectDelimiter(line) {
  if (line.includes("\t")) return "\t";
  if (line.includes(";")) return ";";
  return ",";
}

function mapHeaders(headers) {
  const find = (...needles) => headers.findIndex((header) => needles.some((needle) => header.includes(needle)));
  return {
    name: find("medicine", "drug", "item", "product", "name"),
    strength: find("strength", "dose", "dosage"),
    pack_size: find("pack size", "pack", "package"),
    form: find("form"),
    unit: find("unit"),
    selling_price: find("sell", "selling", "price", "retail"),
    cost_price: find("cost", "buy", "purchase"),
    stock: find("stock", "qty", "quantity", "balance"),
    supplier: find("supplier", "vendor"),
    barcode: find("barcode", "code"),
    batch: find("batch", "lot"),
    expiry: find("expiry", "exp"),
    shelf: find("shelf", "location")
  };
}

function inferForm(text) {
  const wanted = normalize(text);
  return SupportedForms.find((form) => wanted.includes(form) || wanted.includes(`${form}s`)) || "";
}

function inferUnit(form, sourceMatch) {
  return normalizeForm(form || first(sourceMatch?.units) || "");
}

function normalizeForm(value) {
  const clean = normalize(value);
  if (SupportedForms.includes(clean)) return clean;
  const singular = clean.replace(/s$/, "");
  if (singular === "table") return "tablet";
  if (singular === "cap") return "capsule";
  return SupportedForms.includes(singular) ? singular : clean;
}

function normalize(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function titleCase(value) {
  return normalize(value).replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function first(values = []) {
  return Array.isArray(values) ? values[0] || "" : "";
}

function escapeRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
