import { SourceMedicineList } from "../data/sourceMedicines.js";

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
  const wanted = normalize(name);
  if (!wanted) return { status: "missing_name", confidence: 0, matches: [] };
  const matches = catalog.filter((item) => {
    const aliases = [item.name, ...(item.aliases || [])].map(normalize);
    return aliases.some((alias) => alias === wanted || alias.includes(wanted) || wanted.includes(alias));
  });
  if (matches.length === 1) return { status: "matched", confidence: 0.96, matches };
  if (matches.length > 1) return { status: "ambiguous", confidence: 0.55, matches };
  const spellingMatches = catalog.filter((item) => {
    const aliases = [item.name, ...(item.aliases || [])].map(normalize);
    return aliases.some((alias) => isCloseSpelling(alias, wanted));
  });
  if (spellingMatches.length === 1) {
    return { status: "matched", confidence: 0.88, matches: spellingMatches, matchType: "spelling_variation" };
  }
  if (spellingMatches.length > 1) {
    return { status: "ambiguous", confidence: 0.52, matches: spellingMatches, matchType: "spelling_variation" };
  }
  return { status: "not_in_catalog", confidence: 0.2, matches: [] };
}

export class SourceBrain {
  constructor({ medicines = SourceMedicineList } = {}) {
    this.medicines = medicines;
  }

  lookupMedicine(name) {
    const wanted = normalize(name);
    if (!wanted) return { name, confidence: 0, status: "missing_name", matches: [] };
    const matches = this.medicines.filter((item) => {
      const aliases = [item.name, ...(item.aliases || [])].map(normalize);
      return aliases.some((alias) => alias === wanted || alias.includes(wanted) || wanted.includes(alias));
    });
    if (matches.length === 1) {
      return { ...matches[0], confidence: 0.92, status: "matched", matches };
    }
    if (matches.length > 1) {
      return { name, confidence: 0.58, status: "ambiguous", matches };
    }
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
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function sameMedicine(left, right) {
  return normalize(left) === normalize(right);
}

function isCloseSpelling(left, right) {
  if (!left || !right || left.includes(" ") || right.includes(" ")) return false;
  const longest = Math.max(left.length, right.length);
  if (longest < 5 || Math.abs(left.length - right.length) > 2) return false;
  const allowedEdits = longest >= 8 ? 2 : 1;
  return editDistanceWithin(left, right, allowedEdits);
}

function editDistanceWithin(left, right, limit) {
  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let row = 1; row <= left.length; row += 1) {
    const current = [row];
    let rowMinimum = row;
    for (let column = 1; column <= right.length; column += 1) {
      const cost = left[row - 1] === right[column - 1] ? 0 : 1;
      const value = Math.min(
        current[column - 1] + 1,
        previous[column] + 1,
        previous[column - 1] + cost
      );
      current.push(value);
      rowMinimum = Math.min(rowMinimum, value);
    }
    if (rowMinimum > limit) return false;
    previous = current;
  }
  return previous[right.length] <= limit;
}

function normalizeCatalogItem(item) {
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
    batches: item.batches || [],
    expiry: item.expiry || "",
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
    stockLeft: incoming.stockLeft ?? existing.stockLeft
  };
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}
