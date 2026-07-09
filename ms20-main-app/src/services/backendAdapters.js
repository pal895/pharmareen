import { parseLocalCommand, buildCardFromParse } from "./localIntelligence.js";
import { LiveBackendGateway } from "./liveBackendGateway.js";

export class BackendAdapterRegistry {
  constructor({ liveBackendGateway = new LiveBackendGateway() } = {}) {
    this.liveBackendGateway = liveBackendGateway;
    this.adapters = {
      commandParserAdapter: new CommandParserAdapter(),
      medicineBrainAdapter: liveSlot("medicineBrainAdapter", "Pharmacy catalog, aliases, forms, units, and source brain"),
      saleEngineAdapter: liveSlot("saleEngineAdapter", "Sales, payment modes, stock safety, undo/correction ledger"),
      stockEngineAdapter: liveSlot("stockEngineAdapter", "Stock checks, restock, low-stock/no-stock behavior"),
      reportEngineAdapter: liveSlot("reportEngineAdapter", "Corrected reports with cash, M-Pesa, credit, and mixed totals"),
      invoiceEngineAdapter: liveSlot("invoiceEngineAdapter", "Invoice/photo review foundation without AI by default"),
      onboardingEngineAdapter: liveSlot("onboardingEngineAdapter", "Registry, owner approval, pharmacy and branch setup"),
      syncEngineAdapter: liveSlot("syncEngineAdapter", "Offline queue, idempotency, retry and recovery safety"),
      authSessionAdapter: null,
      cloudStorageAdapter: liveSlot("cloudStorageAdapter", "Google Sheets cloud memory and registry adapter"),
      externalChannelAdapter: liveSlot("externalChannelAdapter", "Baileys WhatsApp bridge status adapter")
    };
  }

  connect(name, adapter) {
    this.adapters[name] = adapter;
    return this.adapters[name];
  }

  status() {
    return Object.fromEntries(
      Object.entries(this.adapters).map(([key, value]) => [key, Boolean(value)])
    );
  }

  details() {
    return Object.fromEntries(Object.entries(this.adapters).map(([key, value]) => [key, value]));
  }

  endpointLinks() {
    return this.liveBackendGateway.endpointLinks();
  }

  async getLiveStatus() {
    return this.liveBackendGateway.statusSnapshot();
  }

  prepareBackendAction(card, liveStatus) {
    return this.liveBackendGateway.prepareAction(card, liveStatus);
  }
}

export class CommandParserAdapter {
  parse(text, catalog = []) {
    return parseLocalCommand(text, catalog);
  }

  toCard(text, catalog = []) {
    const card = buildCardFromParse(this.parse(text, catalog), text);
    return {
      ...card,
      parser: "local_first_frontend_adapter"
    };
  }
}

function liveSlot(name, description) {
  return {
    name,
    description,
    status: "adapter_ready",
    writeMode: "safe_queue_only",
    tokenImpact: "zero_openai_api_tokens"
  };
}
