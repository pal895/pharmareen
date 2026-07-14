import { SourceMedicineList } from "../data/sourceMedicines.js";
import { matchMedicine, normalizeMedicineText } from "./medicineMatcher.js";
import { normalizeExpiryValue } from "./medicineFieldSchema.js";

export class PharmacyBrain {
  constructor({ pharmacyId, catalog = [], aliases = [], visualMemory = [] }) {
    this.pharmacyId = pharmacyId;
    this.catalog = catalog;
    this.aliases = aliases;
    this.visualMemory = visualMemory;
  }

  loadCatalog(items) {
    this.catalog = [];
    items.forEach((item) => this.upsertCatalogItem(item));
    return this.catalog;
  }

  upsertCatalogItem(item) {
    const name = item.name || item.medicine || "";
    const existingIndex = this.catalog.findIndex((record) => sameMedicine(record.name, name));
    const normalized = normalizeCatalogItem(item);
    if (existingIndex >= 0) {
      this.catalog[existingIndex] = mergeCatalogItems(this.catalog[existingIndex], normalized);
      return this.catalog[existingIndex];
    }
    this.catalog.push(normalized);
    return normalized;
  }

  findMedicine(name) {
    return matchCatalogMedicine(name, this.catalog);
  }

  saveOwnerAlias(medicineName, alias) {
    const record = { medicineName, alias, pharmacyId: this.pharmacyId };
    this.aliases.push(record);
    return record;
  }

  saveVisualMemory(signature) {
    this.visualMemory.push({ ...signature, pharmacyId: this.pharmacyId });
    return signature;
  }
}

export function matchCatalogMedicine(name, catalog = []) {
  return matchMedicine(name, catalog);
}

export class SourceBrain {
  constructor({ medicines = SourceMedicineList } = {}) {
    this.medicines = medicines;
  }

  lookupMedicine(name) {
    const result = matchMedicine(name, this.medicines);
    if (result.status === "matched") return { ...result.matches[0], ...result };
    if (result.status === "ambiguous" || result.status === "missing_name") return { name, ...result };
    return {
      name,
      confidence: 0.18,
      status: "global_candidate",
      matches: [],
      note: "Needs owner evidence before promotion."
    };
  }
}

export class AIFallbackAdapter {
  constructor() {
    this.enabled = false;
    this.calls = 0;
  }

  shouldAskAI(context) {
    return Boolean(context?.explicitlyAllowed && context?.localConfidence < 0.55);
  }

  async request() {
    throw new Error("AI fallback is intentionally disabled in this foundation.");
  }
}

function normalize(value) {
  return normalizeMedicineText(value);
}

function sameMedicine(left, right) {
  return normalize(left) === normalize(right);
}

function normalizeCatalogItem(item) {
  const batches = Array.isArray(item.batches) && item.batches.length
    ? item.batches
    : item.batch || item.expiry
      ? [{ batch: item.batch || "", expiry: item.expiry || "" }]
      : [];
  return {
    id: item.id || `catalog-${normalize(item.name || item.medicine)}-${Date.now()}`,
    name: item.name || item.medicine || "",
    strength: item.strength || "",
    aliases: item.aliases || [],
    forms: item.forms || (item.form ? [item.form] : []),
    units: item.units || (item.unit ? [item.unit] : []),
    packSizes: item.packSizes || (item.pack_size ? [item.pack_size] : []),
    category: item.category || "",
    sellingPrice: item.sellingPrice ?? item.selling_price ?? "",
    costPrice: item.costPrice ?? item.cost_price ?? "",
    supplier: item.supplier || "",
    barcode: item.barcode || "",
    batches: batches.map((batch) => ({ ...batch, expiry: normalizeExpiryValue(batch.expiry || "") })),
    expiry: normalizeExpiryValue(item.expiry || ""),
    shelf: item.shelf || item.location || "",
    reorderLevel: item.reorderLevel ?? item.reorder_level ?? "",
    stockLeft: item.stockLeft ?? item.current_stock ?? item.stock ?? null,
    source: item.source || "pharmacy_catalog"
  };
}

function mergeCatalogItems(existing, incoming) {
  return {
    ...existing,
    ...incoming,
    aliases: unique([...(existing.aliases || []), ...(incoming.aliases || [])]),
    forms: unique([...(existing.forms || []), ...(incoming.forms || [])]),
    units: unique([...(existing.units || []), ...(incoming.units || [])]),
    packSizes: unique([...(existing.packSizes || []), ...(incoming.packSizes || [])]),
    batches: [...(existing.batches || []), ...(incoming.batches || [])].filter(Boolean),
    strength: incoming.strength || existing.strength || "",
    barcode: incoming.barcode || existing.barcode || "",
    stockLeft: incoming.stockLeft ?? existing.stockLeft
  };
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}
