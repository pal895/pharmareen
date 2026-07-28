const ACTIVITY_LIMIT = 100;

export function createCatalogActivityEntry({
  pharmacyId,
  medicine,
  changes = [],
  source = "manual",
  timestamp = new Date().toISOString()
} = {}) {
  const changedFields = [...new Set(changes.map(String).filter(Boolean))];
  const eventType = catalogEventType(changedFields);
  const safeMedicine = String(medicine || "Medicine").trim();
  return {
    id: `${String(pharmacyId || "pharmacy")}:${eventType}:${safeMedicine.toLowerCase()}:${timestamp}`,
    pharmacyId: String(pharmacyId || ""),
    eventType,
    medicine: safeMedicine,
    timestamp,
    kenyaTime: kenyaTimestamp(timestamp),
    summary: catalogActivitySummary(safeMedicine, changedFields),
    changedFields,
    source: ["manual", "voice", "barcode", "invoice", "system"].includes(source) ? source : "manual",
    outcome: "saved"
  };
}

export function appendActivity(history = [], entry) {
  if (!entry?.id) return Array.isArray(history) ? history : [];
  const current = Array.isArray(history) ? history : [];
  if (current.some((item) => item.id === entry.id)) return current;
  return [entry, ...current].slice(0, ACTIVITY_LIMIT);
}

export function catalogEventType(changes = []) {
  const fields = new Set(changes);
  if (fields.size === 1 && fields.has("stock")) return "stock_corrected";
  if (fields.size === 1 && fields.has("expiry")) return "expiry_changed";
  if (["supplier", "shelf", "batch", "barcode", "pack_size"].some((field) => fields.has(field))) {
    return "supplier_details_changed";
  }
  return "catalog_medicine_updated";
}

export function catalogActivitySummary(medicine, changes = []) {
  const labels = changes.map(activityFieldLabel);
  return labels.length
    ? `${medicine}: ${labels.join(", ")} updated.`
    : `${medicine} updated.`;
}

export function activityFieldLabel(field) {
  return {
    name: "Medicine",
    strength: "Strength",
    form: "Form",
    unit: "Unit",
    pack_size: "Pack size",
    stock: "Current stock",
    selling_price: "Selling price",
    cost_price: "Buying price",
    supplier: "Supplier",
    shelf: "Shelf",
    barcode: "Barcode",
    batch: "Batch",
    expiry: "Expiry month",
    reorder_level: "Reorder level",
    aliases: "Aliases"
  }[field] || String(field).replaceAll("_", " ");
}

export function kenyaTimestamp(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Africa/Nairobi",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(date);
}
