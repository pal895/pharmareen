const VALUE_KEYS = Object.freeze({
  name: ["name", "medicine", "canonical_name"],
  id: ["id", "medicineId", "stable_catalog_id"],
  stock: ["stockLeft", "stock", "current_stock"],
  unit: ["unit", "selling_unit"],
  form: ["form"],
  sellingPrice: ["sellingPrice", "selling_price"],
  buyingPrice: ["costPrice", "cost_price", "buying_price"],
  barcode: ["barcode"],
  reorderLevel: ["reorderLevel", "reorder_level"],
  expiry: ["expiry"],
  batch: ["batch"],
  aliases: ["aliases"],
});

export function assessSaleTestMedicine({
  medicine,
  catalog = [],
  quantity = 1,
  requireBuyingPrice = false,
  requireBarcode = false,
  requireReorderLevel = false,
  requireExpiryOrBatch = false,
} = {}) {
  const issues = [];
  const name = textValue(medicine, "name");
  const id = textValue(medicine, "id");
  const stock = numberValue(medicine, "stock");
  const sellingPrice = numberValue(medicine, "sellingPrice");
  const buyingPrice = numberValue(medicine, "buyingPrice");
  const requestedQuantity = Number(quantity);

  if (!name) issues.push("canonical_name_missing");
  if (!id) issues.push("stable_catalog_identity_missing");
  if (stock === null) issues.push("numeric_current_stock_missing");
  if (!Number.isFinite(requestedQuantity) || requestedQuantity <= 0) issues.push("test_quantity_invalid");
  if (stock !== null && Number.isFinite(requestedQuantity) && stock < requestedQuantity) issues.push("insufficient_stock");
  if (!textValue(medicine, "unit")) issues.push("selling_unit_missing");
  if (!textValue(medicine, "form")) issues.push("form_missing");
  if (sellingPrice === null || sellingPrice <= 0) issues.push("selling_price_missing");
  if (requireBuyingPrice && (buyingPrice === null || buyingPrice < 0)) issues.push("buying_price_missing");
  if (requireBarcode && !textValue(medicine, "barcode")) issues.push("barcode_missing");
  if (requireReorderLevel && numberValue(medicine, "reorderLevel") === null) issues.push("reorder_level_missing");
  if (requireExpiryOrBatch && !textValue(medicine, "expiry") && !textValue(medicine, "batch")) issues.push("expiry_or_batch_missing");

  const normalizedName = normalize(name);
  const candidates = (Array.isArray(catalog) ? catalog : []).filter((item) => {
    if (id && textValue(item, "id") === id) return true;
    const identities = [textValue(item, "name"), ...arrayValue(item, "aliases")].map(normalize).filter(Boolean);
    return normalizedName && identities.includes(normalizedName);
  });
  if (candidates.length === 0) issues.push("catalog_record_missing");
  if (candidates.length > 1) issues.push("duplicate_or_alias_conflict");

  return {
    ready: issues.length === 0,
    issues,
    beforeState: {
      canonicalName: name,
      catalogId: id,
      currentStock: stock,
      quantity: Number.isFinite(requestedQuantity) ? requestedQuantity : null,
      unit: textValue(medicine, "unit"),
      form: textValue(medicine, "form"),
      sellingPrice,
      buyingPrice,
      barcode: textValue(medicine, "barcode"),
      reorderLevel: numberValue(medicine, "reorderLevel"),
      expiry: textValue(medicine, "expiry"),
      batch: textValue(medicine, "batch"),
    },
  };
}

function rawValue(item, key) {
  for (const candidate of VALUE_KEYS[key] || []) {
    const value = item?.[candidate];
    if (value !== undefined && value !== null) return value;
  }
  return "";
}

function textValue(item, key) {
  const value = rawValue(item, key);
  return Array.isArray(value) ? String(value[0] || "").trim() : String(value || "").trim();
}

function arrayValue(item, key) {
  const value = rawValue(item, key);
  if (Array.isArray(value)) return value.map((entry) => String(entry || "").trim()).filter(Boolean);
  return String(value || "").split(",").map((entry) => entry.trim()).filter(Boolean);
}

function numberValue(item, key) {
  const value = rawValue(item, key);
  if (value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function normalize(value) {
  return String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ");
}
