import { MEDICINE_CARD_FIELD_KEYS } from "../services/medicineFieldSchema.js";
import { PRODUCTION_SALE_CARD_FIELDS } from "../services/productionSaleCard.js";

export function cardFieldsFor(type) {
  const base = {
    SaleCard: [...PRODUCTION_SALE_CARD_FIELDS],
    ...MEDICINE_CARD_FIELD_KEYS,
    OnboardingCard: ["pharmacy", "owner", "branch", "location", "payments"],
    StockCorrectionCard: ["medicine", "current_stock", "correct_stock", "reason"],
    ReportCard: ["period", "focus", "report_date", "generated_at", "report_text"],
    CatalogOnboardingCard: ["question", "choices"],
    CatalogImportCard: ["method", "items_text", "notes"],
    ImportMappingCard: ["file", "mapping", "missing_columns", "notes"],
    NotificationCard: ["category", "message", "action", "status"],
    DocumentExportCard: ["document", "format", "items", "status"],
    SyncReviewCard: ["pending", "last_sync", "conflict", "backend", "sheets", "baileys"]
  };
  return base[type] || [];
}

export function createEditableCard({ type, title, source = "", fields = {}, confidence = 0.7, status = "ready", aiRequired = false, validation = "" }) {
  return {
    id: `card-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    type,
    title: title || type.replace(/([A-Z])/g, " $1").trim(),
    source,
    fields,
    confidence,
    status,
    aiRequired,
    validation: validation || "Review and confirm."
  };
}

export function paymentOptions() {
  return ["cash", "mpesa", "credit", "mixed"];
}

export function quantityBumps() {
  return [-1, 1, 5, 10];
}
