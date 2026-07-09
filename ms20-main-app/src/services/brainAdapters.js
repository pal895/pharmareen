export class PharmacyBrain {
  constructor({ pharmacyId, catalog = [], aliases = [], visualMemory = [] }) {
    this.pharmacyId = pharmacyId;
    this.catalog = catalog;
    this.aliases = aliases;
    this.visualMemory = visualMemory;
  }

  loadCatalog(items) {
    this.catalog = items.map((item) => ({
      name: item.name,
      aliases: item.aliases || [],
      forms: item.forms || [],
      units: item.units || [],
      packSizes: item.packSizes || [],
      category: item.category || "",
      stockLeft: item.stockLeft ?? null
    }));
    return this.catalog;
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

export class SourceBrain {
  lookupMedicine(name) {
    return {
      name,
      confidence: 0,
      status: "placeholder",
      note: "Connect to approved MS2.0 source brain later."
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
