export const EditableCardTypes = [
  "SaleCard",
  "InvoiceCard",
  "RestockCard",
  "OnboardingCard",
  "StockCorrectionCard",
  "ReportCard",
  "VoiceReviewCard",
  "PhotoReviewCard",
  "MedicineMatchCard",
  "VisualScanCard",
  "SyncReviewCard"
];

export const RouteSlots = {
  root: "/",
  appOffline: "/app/offline",
  offline: "/offline",
  apiRoot: "/api/ms20",
  parseCommand: "/api/ms20/command/parse",
  approveCard: "/api/ms20/cards/approve",
  syncQueue: "/api/ms20/sync",
  recoverMemory: "/api/ms20/recover",
  pharmacyCatalog: "/api/ms20/pharmacies/:pharmacyId/catalog",
  visualMemory: "/api/ms20/pharmacies/:pharmacyId/visual-memory",
  onboarding: "/api/ms20/onboarding",
  externalChannel: "/api/ms20/channels/external"
};

export const LiveBackendRoutes = {
  health: "/health",
  debugVersion: "/debug/version",
  readiness: "/live/readiness",
  offlineApp: "/offline_app/index.html",
  baileysWebhook: "/webhooks/baileys/whatsapp",
  dailyReport: "/reports/daily?send_whatsapp=false",
  statusPage: "/status",
  adminOnboarding: "/admin/onboarding/{session_id}/{action}"
};

export const BackendAdapterSlots = [
  "commandParserAdapter",
  "medicineBrainAdapter",
  "saleEngineAdapter",
  "stockEngineAdapter",
  "reportEngineAdapter",
  "invoiceEngineAdapter",
  "onboardingEngineAdapter",
  "syncEngineAdapter",
  "authSessionAdapter",
  "cloudStorageAdapter",
  "externalChannelAdapter"
];

export const TokenPolicy = {
  localFirst: true,
  zeroTokenFlows: [
    "known_sales",
    "owner_aliases",
    "confirmed_packaging",
    "cached_invoice_layout",
    "repeated_documents",
    "stock_checks",
    "reports",
    "simple_analytics",
    "barcode_scans"
  ],
  aiAllowedOnlyFor: [
    "uncertain_photo",
    "difficult_invoice",
    "messy_language",
    "unknown_medicine",
    "ambiguous_context"
  ],
  aiRule: "Ask once, save the correction, then route locally next time."
};

export const CloudMemoryContract = {
  sourceOfTruth: "cloud",
  deviceRole: "cache_and_queue_only",
  recoveryRule: "After login, recover pharmacy profile, catalog, aliases, visual memory, pending queue, and card history from cloud memory.",
  multiDeviceRule: "Every device syncs through cloud memory with idempotent action ids and conflict review cards."
};

export const ExternalChannelContract = {
  currentLiveBridge: "Baileys WhatsApp bridge",
  appRole: "optional external channel adapter only",
  rule: "Do not modify the existing bridge from this main app foundation."
};
