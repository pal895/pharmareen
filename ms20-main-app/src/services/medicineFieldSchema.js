export const MEDICINE_FIELD_DEFINITIONS = Object.freeze({
  name: field("name", "Medicine", 180),
  medicine: field("medicine", "Medicine", 180),
  strength: field("strength", "Strength", 110),
  form: field("form", "Form", 110),
  unit: field("unit", "Unit", 110),
  pack_size: field("pack_size", "Pack size", 120),
  base_stock_unit: field("base_stock_unit", "Base stock unit", 130),
  unit_conversions: field("unit_conversions", "Pack conversions", 170),
  unit_prices: field("unit_prices", "Selling-unit prices", 170),
  quantity: field("quantity", "Quantity", 100, "numeric"),
  bonus_quantity: field("bonus_quantity", "Bonus stock", 100, "numeric"),
  stock: field("stock", "Current stock", 100, "numeric"),
  cost_price: field("cost_price", "Buying price", 120, "decimal"),
  selling_price: field("selling_price", "Selling price", 120, "decimal"),
  supplier: field("supplier", "Supplier", 130),
  barcode: field("barcode", "Barcode", 130),
  batch: field("batch", "Batch", 110),
  expiry: field("expiry", "Expiry month (YYYY-MM)", 150),
  shelf: field("shelf", "Shelf", 110),
  reorder_level: field("reorder_level", "Reorder level", 110, "decimal"),
  aliases: field("aliases", "Aliases", 140),
  delivery_reference: field("delivery_reference", "Invoice or delivery reference", 170),
  supplier_terms: field("supplier_terms", "Supplier payment", 150),
  settlement_date: field("settlement_date", "Settlement date", 150),
  note: field("note", "Note", 180),
  voice_transcript: field("voice_transcript", "Heard", 180)
});

export const CATALOG_MEDICINE_FIELD_KEYS = Object.freeze([
  "name", "strength", "form", "unit", "pack_size", "base_stock_unit", "unit_conversions", "unit_prices", "stock", "selling_price",
  "cost_price", "supplier", "shelf", "barcode", "batch", "expiry", "reorder_level", "aliases"
]);

export const CATALOG_IMPORT_FIELD_KEYS = Object.freeze([
  "name", "strength", "form", "unit", "pack_size", "stock", "cost_price", "selling_price",
  "supplier", "barcode", "batch", "expiry", "shelf"
]);

export const MEDICINE_DETAIL_FIELD_ORDER = Object.freeze([
  "medicine", "strength", "form", "unit", "pack_size", "quantity", "bonus_quantity", "stock",
  "current_stock", "correct_stock", "cost_price", "selling_price", "supplier",
  "barcode", "batch", "expiry", "shelf", "category", "reason", "alias", "file",
  "scan_type", "total", "payment", "delivery_reference", "note", "voice_transcript"
]);

export const MEDICINE_CARD_FIELD_KEYS = Object.freeze({
  InvoiceCard: ["supplier", "medicine", "strength", "form", "quantity", "unit", "cost_price", "selling_price", "barcode", "batch", "expiry", "total", "payment"],
  RestockCard: ["medicine", "quantity", "bonus_quantity", "unit", "pack_size", "strength", "form", "cost_price", "selling_price", "supplier", "supplier_terms", "settlement_date", "batch", "expiry", "barcode", "shelf", "delivery_reference", "note"],
  PhotoReviewCard: ["file", "medicine", "strength", "form", "unit", "pack_size", "barcode", "batch", "expiry", "shelf"],
  MedicineMatchCard: ["message", "medicine", "strength", "form", "unit", "selling_price", "quantity", "payment", "stock", "cost_price", "supplier", "barcode", "batch", "expiry", "alias"],
  VisualScanCard: ["scan_type", "medicine", "strength", "form", "unit", "pack_size", "quantity", "selling_price", "cost_price", "supplier", "barcode", "batch", "expiry", "shelf", "category"]
});

export function medicineFieldColumns(keys = CATALOG_IMPORT_FIELD_KEYS) {
  return keys.map((key) => MEDICINE_FIELD_DEFINITIONS[key]).filter(Boolean);
}

export function medicineFieldLabel(key) {
  return MEDICINE_FIELD_DEFINITIONS[key]?.label || "";
}

export function normalizeMedicineReviewRow(row = {}) {
  return {
    name: row.name || row.medicine || "",
    strength: row.strength || "",
    form: row.form || first(row.forms),
    unit: row.unit || first(row.units) || row.form || "",
    pack_size: row.pack_size || first(row.packSizes),
    base_stock_unit: row.base_stock_unit || row.baseStockUnit || "",
    unit_conversions: row.unit_conversions || row.unitConversions || {},
    unit_prices: row.unit_prices || row.unitPrices || {},
    stock: row.stock ?? row.current_stock ?? row.quantity ?? row.stockLeft ?? "",
    cost_price: row.cost_price ?? row.costPrice ?? "",
    line_total: row.line_total ?? row.lineTotal ?? "",
    selling_price: row.selling_price ?? row.sellingPrice ?? "",
    supplier: row.supplier || "",
    batch: row.batch || first(row.batches)?.batch || "",
    expiry: normalizeExpiryValue(row.expiry || first(row.batches)?.expiry || ""),
    barcode: row.barcode || "",
    shelf: row.shelf || row.location || "",
    source: row.source || "owner_review"
  };
}

export function medicineRecordFromFields(fields = {}, { source = "owner_review", quantityIsStock = true } = {}) {
  return {
    name: fields.name || fields.medicine || "",
    strength: fields.strength || "",
    form: fields.form || "",
    unit: fields.unit || "",
    pack_size: fields.pack_size || "",
    baseStockUnit: fields.base_stock_unit || "",
    unitConversions: fields.unit_conversions || {},
    unitPrices: fields.unit_prices || {},
    stock: fields.stock ?? (quantityIsStock ? fields.quantity : undefined),
    selling_price: fields.selling_price ?? "",
    cost_price: fields.cost_price ?? "",
    supplier: fields.supplier || "",
    barcode: fields.barcode || "",
    batch: fields.batch || "",
    expiry: normalizeExpiryValue(fields.expiry || ""),
    shelf: fields.shelf || "",
    aliases: fields.alias ? [fields.alias] : fields.aliases || [],
    source
  };
}

export function normalizeExpiryValue(value) {
  const clean = String(value || "").trim();
  if (!clean) return "";
  const iso = /^(20\d{2})-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?$/.exec(clean);
  if (iso) return iso[3] ? `${iso[1]}-${iso[2]}-${iso[3]}` : `${iso[1]}-${iso[2]}`;
  const named = /^([a-z]{3,9})[\s\-/]+(\d{2}|20\d{2})$/i.exec(clean);
  if (named) {
    const month = monthNumber(named[1]);
    const year = fourDigitYear(named[2]);
    if (month && year) return `${year}-${month}`;
  }
  const numeric = /^(0?[1-9]|1[0-2])[\s\-/]+(\d{2}|20\d{2})$/.exec(clean);
  if (numeric) return `${fourDigitYear(numeric[2])}-${String(Number(numeric[1])).padStart(2, "0")}`;
  return clean;
}

export function expiryEndDate(value) {
  const normalized = normalizeExpiryValue(value);
  const monthOnly = /^(20\d{2})-(0[1-9]|1[0-2])$/.exec(normalized);
  if (monthOnly) return new Date(Date.UTC(Number(monthOnly[1]), Number(monthOnly[2]), 0, 23, 59, 59, 999));
  const fullDate = /^(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/.exec(normalized);
  if (!fullDate) return null;
  const parsed = new Date(Date.UTC(Number(fullDate[1]), Number(fullDate[2]) - 1, Number(fullDate[3]), 23, 59, 59, 999));
  return parsed.getUTCFullYear() === Number(fullDate[1]) && parsed.getUTCMonth() === Number(fullDate[2]) - 1 && parsed.getUTCDate() === Number(fullDate[3]) ? parsed : null;
}

export function expiryDisplayLabel(value) {
  const normalized = normalizeExpiryValue(value);
  const date = expiryEndDate(normalized);
  if (!date) return normalized;
  if (/^20\d{2}-\d{2}$/.test(normalized)) {
    return `end of ${date.toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" })}`;
  }
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

function field(key, label, min, inputMode) {
  return Object.freeze({ key, label, min, ...(inputMode ? { inputMode } : {}) });
}

function first(values = []) {
  return Array.isArray(values) ? values[0] || "" : "";
}

function fourDigitYear(value) {
  const number = Number(value);
  if (!Number.isInteger(number)) return "";
  return String(value).length === 2 ? String(2000 + number) : String(number);
}

function monthNumber(value) {
  const wanted = String(value || "").slice(0, 3).toLowerCase();
  const index = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].indexOf(wanted);
  return index < 0 ? "" : String(index + 1).padStart(2, "0");
}
