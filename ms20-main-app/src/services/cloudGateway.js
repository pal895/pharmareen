export class CloudMemoryGateway {
  constructor(seed = {}) {
    this.connected = false;
    this.memory = {
      profiles: {},
      catalogs: {},
      visualMemory: {},
      actions: [],
      cardHistory: [],
      ...seed
    };
  }

  status() {
    return {
      connected: this.connected,
      mode: "placeholder",
      sourceOfTruth: "cloud",
      deviceRole: "cache_and_queue_only"
    };
  }

  async recoverWorkspace(sessionId = "demo-session") {
    return {
      sessionId,
      recovered: true,
      profileCount: Object.keys(this.memory.profiles).length,
      catalogCount: Object.keys(this.memory.catalogs).length,
      visualMemoryCount: Object.keys(this.memory.visualMemory).length,
      actionCount: this.memory.actions.length
    };
  }

  async loadPharmacyProfile(pharmacyId) {
    return this.memory.profiles[pharmacyId] || null;
  }

  async saveOnboardingProfile(profile) {
    const id = profile.id || `pharmacy-${Date.now()}`;
    this.memory.profiles[id] = { ...profile, id };
    return this.memory.profiles[id];
  }

  async loadCatalog(pharmacyId) {
    return this.memory.catalogs[pharmacyId] || [];
  }

  async saveCatalog(pharmacyId, catalogItems) {
    this.memory.catalogs[pharmacyId] = catalogItems.map((item) => ({ ...item }));
    return this.memory.catalogs[pharmacyId];
  }

  async saveVisualMemory(pharmacyId, visualSignature) {
    const list = this.memory.visualMemory[pharmacyId] || [];
    list.push({ ...visualSignature, savedAt: new Date().toISOString() });
    this.memory.visualMemory[pharmacyId] = list;
    return visualSignature;
  }

  async saveAction(action) {
    this.memory.actions.push({ ...action, savedAt: new Date().toISOString() });
    return { saved: true, actionId: action.id };
  }

  async saveCardHistory(card) {
    this.memory.cardHistory.push({ ...card, savedAt: new Date().toISOString() });
    return { saved: true, cardId: card.id };
  }
}
