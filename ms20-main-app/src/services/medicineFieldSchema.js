export const MEDICINE_FIELD_DEFINITIONS = Object.freeze({
  name: field("name", "Medicine", 180),
  medicine: field("medicine", "Medicine", 180),
  strength: field("strength", "Strength", 110),
  form: field("form", "Form", 110),
  unit: field("unit", "Unit", 110),
  pack_size: field("pack_size", "Pack size", 120),
  quantity: field("quantity", "Quantity", 100, "numeric"),
  stock: field("stock", "Quantity", 100, "numeric"),
  cost_price: field("cost_price", "Buying price", 120, "decimal"),
  selling_price: field("selling_price", "Selling price", 120, "decimal"),
  supplier: field("supplier", "Supplier", 130),
  barcode: field("barcode", "Barcode", 130),
  batch: field("batch", "Batch", 110),
  expiry: field("expiry", "Expiry", 120),
  shelf: field("shelf", "Shelf", 110),
  reorder_level: field("reorder_level", "Reorder level", 110, "decimal"),
  aliases: field("aliases", "Aliases", 140)
});

export const CATALOG_MEDICINE_FIELD_KEYS = Object.freeze([
  "name", "strength", "form", "unit", "pack_size", "stock", "selling_price",
  "cost_price", "supplier", "shelf", "barcode", "batch", "expiry", "reorder_level", "aliases"
]);

export const CATALOG_IMPORT_FIELD_KEYS = Object.freeze([
  "name", "strength", "form", "unit", "pack_size", "stock", "cost_price", "selling_price",
  "supplier", "barcode", "batch", "expiry", "shelf"
]);

export const MEDICINE_DETAIL_FIELD_ORDER = Object.freeze([
  "medicine", "strength", "form", "unit", "pack_size", "quantity", "stock",
  "current_stock", "correct_stock", "cost_price", "selling_price", "supplier",
  "barcode", "batch", "expiry", "shelf", "category", "reason", "alias", "file",
  "scan_type", "total", "payment"
]);

export const MEDICINE_CARD_FIELD_KEYS = Object.freeze({
  InvoiceCard: ["supplier", "medicine", "strength", "form", "quantity", "unit", "cost_price", "selling_price", "barcode", "batch", "expiry", "total", "payment"],
  RestockCard: ["medicine", "strength", "form", "quantity", "unit", "cost_price", "selling_price", "supplier", "barcode", "batch", "expiry"],
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
    stock: row.stock ?? row.current_stock ?? row.quantity ?? row.stockLeft ?? "",
    cost_price: row.cost_price ?? row.costPrice ?? "",
    line_total: row.line_total ?? row.lineTotal ?? "",
    selling_price: row.selling_price ?? row.sellingPrice ?? "",
    supplier: row.supplier || "",
    batch: row.batch || first(row.batches)?.batch || "",
    expiry: row.expiry || first(row.batches)?.expiry || "",
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
    stock: fields.stock ?? (quantityIsStock ? fields.quantity : undefined),
    selling_price: fields.selling_price ?? "",
    cost_price: fields.cost_price ?? "",
    supplier: fields.supplier || "",
    barcode: fields.barcode || "",
    batch: fields.batch || "",
    expiry: fields.expiry || "",
    shelf: fields.shelf || "",
    aliases: fields.alias ? [fields.alias] : fields.aliases || [],
    source
  };
}

function field(key, label, min, inputMode) {
  return Object.freeze({ key, label, min, ...(inputMode ? { inputMode } : {}) });
}

function first(values = []) {
  return Array.isArray(values) ? values[0] || "" : "";
}
