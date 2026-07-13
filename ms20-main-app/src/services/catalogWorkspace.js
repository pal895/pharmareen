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

export const CATALOG_EDIT_FIELDS = [
  "name", "strength", "form", "unit", "pack_size", "stock", "selling_price",
  "cost_price", "supplier", "shelf", "barcode", "batch", "expiry", "reorder_level", "aliases"
];

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
    expiry: item.batches?.[0]?.expiry || item.expiry || "",
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
    batches: draft.batch || draft.expiry ? [{ batch: draft.batch.trim(), expiry: draft.expiry.trim() }] : [],
    expiry: draft.expiry.trim(),
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
  const wanted = normalize(query);
  return [...unique.values()]
    .filter((item) => !wanted || matchesSearch(searchableText(item), wanted))
    .sort((left, right) => String(left.name || left.medicine).localeCompare(String(right.name || right.medicine)));
}

function matchesSearch(text, wanted) {
  if (text.includes(wanted) || text.replace(/\s/g, "").includes(wanted.replace(/\s/g, ""))) return true;
  if (wanted.length < 5 || wanted.includes(" ")) return false;
  return text.split(" ").some((word) => word.length >= 5 && editDistanceWithin(word, wanted, Math.max(word.length, wanted.length) >= 8 ? 2 : 1));
}

function editDistanceWithin(left, right, limit) {
  if (Math.abs(left.length - right.length) > limit) return false;
  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let row = 1; row <= left.length; row += 1) {
    const current = [row];
    for (let column = 1; column <= right.length; column += 1) {
      const cost = left[row - 1] === right[column - 1] ? 0 : 1;
      current[column] = Math.min(current[column - 1] + 1, previous[column] + 1, previous[column - 1] + cost);
    }
    previous = current;
  }
  return previous[right.length] <= limit;
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
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}
