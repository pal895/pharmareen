export function createCatalogWorkspaceCard(itemCount = 0) {
  return {
    id: "card-pharmacy-catalog",
    type: "CatalogWorkspaceCard",
    title: "Pharmacy catalog",
    source: "Pharmacy Catalog",
    confidence: 1,
    status: "ready",
    aiRequired: false,
    fields: { item_count: String(itemCount), query: "", selected_id: "", edit_draft: "" },
    validation: "Loaded directly from the saved Pharmacy Catalog. No medicines are recreated by this view."
  };
}

export const CATALOG_EDIT_FIELDS = CATALOG_MEDICINE_FIELD_KEYS;

export function catalogItemId(item = {}) {
  return String(item.id || normalize(item.name || item.medicine));
}

export function createCatalogEditDraft(item = {}) {
  return {
    id: catalogItemId(item),
    name: item.name || item.medicine || "",
    strength: item.strength || "",
    form: item.form || item.forms?.[0] || "",
    unit: item.unit || item.units?.[0] || "",
    pack_size: item.pack_size || item.packSizes?.[0] || "",
    stock: item.stockLeft ?? item.stock ?? item.current_stock ?? "",
    selling_price: item.sellingPrice ?? item.selling_price ?? "",
    cost_price: item.costPrice ?? item.cost_price ?? "",
    supplier: item.supplier || "",
    shelf: item.shelf || item.location || "",
    barcode: item.barcode || "",
    batch: item.batches?.[0]?.batch || item.batch || "",
    expiry: normalizeExpiryValue(item.batches?.[0]?.expiry || item.expiry || ""),
    reorder_level: item.reorderLevel ?? item.reorder_level ?? "",
    aliases: (item.aliases || []).join(", ")
  };
}

export function reviewCatalogEdit(catalog = [], originalId, draft = {}) {
  const original = catalog.find((item) => catalogItemId(item) === String(originalId));
  if (!original) return { valid: false, error: "This medicine is no longer in the Pharmacy Catalog." };
  if (!normalize(draft.name)) return { valid: false, error: "Medicine name is required." };
  const collision = catalog.find((item) => catalogItemId(item) !== String(originalId) && normalize(item.name || item.medicine) === normalize(draft.name));
  if (collision) return { valid: false, identityCollision: true, error: `${draft.name} already exists in this Pharmacy Catalog. Cancel this edit and open that medicine instead.` };
  const originalDraft = createCatalogEditDraft(original);
  const changes = CATALOG_EDIT_FIELDS.filter((field) => String(originalDraft[field] ?? "") !== String(draft[field] ?? ""));
  return { valid: true, original, changes };
}

export function applyApprovedCatalogEdit(catalog = [], originalId, draft = {}) {
  const review = reviewCatalogEdit(catalog, originalId, draft);
  if (!review.valid) return { ...review, catalog };
  if (!review.changes.length) return { ...review, catalog, updated: review.original };
  const aliases = String(draft.aliases || "").split(",").map((value) => value.trim()).filter(Boolean);
  const updated = {
    ...review.original,
    name: draft.name.trim(),
    strength: draft.strength.trim(),
    forms: draft.form ? [draft.form.trim()] : [],
    units: draft.unit ? [draft.unit.trim()] : [],
    packSizes: draft.pack_size ? [draft.pack_size.trim()] : [],
    stockLeft: draft.stock === "" ? null : draft.stock,
    sellingPrice: draft.selling_price,
    costPrice: draft.cost_price,
    supplier: draft.supplier.trim(),
    shelf: draft.shelf.trim(),
    barcode: draft.barcode.trim(),
    batches: draft.batch || draft.expiry ? [{ batch: draft.batch.trim(), expiry: normalizeExpiryValue(draft.expiry) }] : [],
    expiry: normalizeExpiryValue(draft.expiry),
    reorderLevel: draft.reorder_level,
    aliases,
    updatedAt: new Date().toISOString()
  };
  return { ...review, catalog: catalog.map((item) => catalogItemId(item) === String(originalId) ? updated : item), updated };
}

export function catalogWorkspaceItems(catalog = [], query = "") {
  const unique = new Map();
  for (const item of catalog) {
    const key = normalize(item.name || item.medicine);
    if (key && !unique.has(key)) unique.set(key, item);
  }
  const items = [...unique.values()];
  if (!normalize(query)) return items.sort((left, right) => String(left.name || left.medicine).localeCompare(String(right.name || right.medicine)));
  return rankMedicineMatches(query, items, { limit: items.length, requireAllTerms: true }).map((entry) => entry.medicine);
}

function searchableText(item) {
  return [
    item.name,
    item.medicine,
    item.strength,
    ...(item.aliases || []),
    item.form,
    ...(item.forms || []),
    item.unit,
    ...(item.units || []),
    item.supplier,
    item.barcode,
    item.shelf
  ].map(normalize).join(" ");
}

function normalize(value) {
  return normalizeMedicineText(value);
}
import { rankMedicineMatches, normalizeMedicineText } from "./medicineMatcher.js";
import { CATALOG_MEDICINE_FIELD_KEYS, normalizeExpiryValue } from "./medicineFieldSchema.js";
