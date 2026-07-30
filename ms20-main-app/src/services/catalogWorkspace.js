export function createCatalogWorkspaceCard(itemCount = 0) {
  return {
    id: "card-pharmacy-catalog",
    type: "CatalogWorkspaceCard",
    title: "Pharmacy catalog",
    source: "Pharmacy Catalog",
    confidence: 1,
    status: "ready",
    aiRequired: false,
    fields: { item_count: String(itemCount), query: "", search_voice_feedback: "", selected_id: "", edit_draft: "", voice_field: "", voice_feedback: "" },
    validation: "Loaded directly from the saved Pharmacy Catalog. No medicines are recreated by this view."
  };
}

export function applyCatalogSearchVoice(transcript = "") {
  const query = String(transcript || "").trim();
  if (!query) {
    return { applied: false, query: "", feedback: "No medicine was heard. Tap Mic and try again." };
  }
  return {
    applied: true,
    query,
    feedback: `Heard “${query}”. Catalog filtered locally.`
  };
}

export function applyCatalogEditVoice(draft = {}, transcript = "", preferredField = "") {
  const spoken = String(transcript || "").trim();
  if (!spoken) return { applied: false, draft, field: "", value: "", feedback: "No words were heard. Tap Mic and try again." };
  const detected = detectSpokenField(spoken);
  const field = CATALOG_EDIT_FIELDS.includes(preferredField) ? preferredField : detected.field;
  if (!field) {
    return {
      applied: false,
      draft,
      field: "",
      value: "",
      feedback: "Tap the field you want to change, then tap Mic and speak its value."
    };
  }
  const rawValue = detected.field === field ? detected.value : spoken;
  const value = normalizeSpokenCatalogValue(field, rawValue);
  if (value === null) {
    return { applied: false, draft, field, value: "", feedback: `${fieldLabelForVoice(field)} needs a number. Nothing changed.` };
  }
  return {
    applied: true,
    draft: { ...draft, [field]: value },
    field,
    value,
    feedback: `Heard “${spoken}”. ${fieldLabelForVoice(field)} is now ${value === "" ? "blank" : value}. Review before saving.`
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
    base_stock_unit: item.baseStockUnit || item.base_stock_unit || item.units?.[0] || item.unit || "",
    unit_conversions: packMapText(item.unitConversions || item.stockUnitsPerSaleUnit),
    unit_prices: packMapText(item.unitPrices || item.pricesByUnit),
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

export function catalogEditPresentation(review = {}) {
  if (review.error) return { status: "Needs attention", description: "Resolve the issue below before this medicine can be saved.", state: "error" };
  if (review.changes?.length) return { status: "Unsaved changes", description: "Check the changes below. The saved medicine stays unchanged until you approve.", state: "changed" };
  return { status: "Saved medicine", description: "This card shows the medicine currently saved in the Pharmacy Catalog.", state: "saved" };
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
    baseStockUnit: draft.base_stock_unit.trim(),
    unitConversions: parsePackMap(draft.unit_conversions),
    unitPrices: parsePackMap(draft.unit_prices),
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
  const index = buildMedicineFinderIndex(catalog);
  return searchMedicineFinder(index, query, { limit: index.length }).map((entry) => entry.item);
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

const VOICE_FIELD_ALIASES = [
  ["reorder_level", ["reorder level", "minimum stock"]],
  ["selling_price", ["selling price", "sale price"]],
  ["cost_price", ["buying price", "cost price"]],
  ["pack_size", ["pack size"]],
  ["base_stock_unit", ["base stock unit"]],
  ["unit_conversions", ["pack conversions", "unit conversions"]],
  ["unit_prices", ["selling unit prices", "unit prices"]],
  ["stock", ["current stock", "stock"]],
  ["expiry", ["expiry month", "expiry"]],
  ["supplier", ["supplier"]],
  ["barcode", ["barcode"]],
  ["batch", ["batch"]],
  ["shelf", ["shelf"]],
  ["strength", ["strength"]],
  ["form", ["form"]],
  ["unit", ["unit"]],
  ["aliases", ["aliases", "alias"]],
  ["name", ["medicine name", "medicine", "name"]]
];

function detectSpokenField(spoken) {
  const normalized = String(spoken).trim().toLowerCase();
  for (const [field, aliases] of VOICE_FIELD_ALIASES) {
    for (const alias of aliases) {
      const match = normalized.match(new RegExp(`^${alias.replace(/\s+/g, "\\s+")}(?:\\s+(?:is|to))?\\s*(.*)$`, "i"));
      if (match) return { field, value: String(match[1] || "").trim() };
    }
  }
  return { field: "", value: spoken };
}

function normalizeSpokenCatalogValue(field, rawValue) {
  let value = String(rawValue || "").trim();
  if (/^(?:blank|empty|clear|remove|not set)$/i.test(value)) value = "";
  if (["stock", "selling_price", "cost_price", "reorder_level"].includes(field)) {
    if (value === "") return "";
    const number = value.match(/-?\d+(?:\.\d+)?/)?.[0] ?? spokenNumber(value);
    return number === undefined ? null : number;
  }
  if (field === "expiry") {
    const month = value.match(/\b(20\d{2})[\s/-](0?[1-9]|1[0-2])\b/);
    if (month) return `${month[1]}-${String(month[2]).padStart(2, "0")}`;
  }
  return value;
}

function spokenNumber(value) {
  const tokens = String(value).toLowerCase().replaceAll("-", " ").match(/[a-z]+/g) || [];
  const small = {
    zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9,
    ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16,
    seventeen: 17, eighteen: 18, nineteen: 19
  };
  const tens = { twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 };
  let total = 0;
  let recognized = false;
  for (const token of tokens) {
    if (token === "and") continue;
    if (Object.hasOwn(small, token)) {
      total += small[token];
      recognized = true;
    } else if (Object.hasOwn(tens, token)) {
      total += tens[token];
      recognized = true;
    } else if (token === "hundred") {
      total = (total || 1) * 100;
      recognized = true;
    }
  }
  return recognized ? String(total) : undefined;
}

function fieldLabelForVoice(field) {
  return {
    name: "Medicine", stock: "Current stock", selling_price: "Selling price",
    cost_price: "Buying price", reorder_level: "Reorder level", pack_size: "Pack size",
    expiry: "Expiry month"
  }[field] || field.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

function packMapText(value = {}) {
  return Object.entries(value || {}).map(([unit, amount]) => `${unit}=${amount}`).join(", ");
}

function parsePackMap(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) return value;
  const entries = String(value || "").split(",").map((entry) => entry.trim()).filter(Boolean).map((entry) => {
    const [unit, amount] = entry.split(/[:=]/).map((part) => part.trim());
    const number = Number(amount);
    return unit && Number.isFinite(number) && number > 0 ? [unit.toLowerCase(), number] : null;
  }).filter(Boolean);
  return Object.fromEntries(entries);
}
import { normalizeMedicineText } from "./medicineMatcher.js";
import { CATALOG_MEDICINE_FIELD_KEYS, normalizeExpiryValue } from "./medicineFieldSchema.js";
import { buildMedicineFinderIndex, searchMedicineFinder } from "./medicineFinder.js";
