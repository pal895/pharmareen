export function cardFieldsFor(type) {
  const base = {
    SaleCard: ["medicine", "quantity", "payment", "stockLeft"],
    InvoiceCard: ["supplier", "medicine", "quantity", "unit", "total", "payment", "batch", "expiry"],
    RestockCard: ["medicine", "quantity", "unit", "supplier"],
    OnboardingCard: ["pharmacy", "owner", "branch", "location", "payments"],
    StockCorrectionCard: ["medicine", "current_stock", "correct_stock", "reason"],
    ReportCard: ["period", "focus", "backend_route"],
    VoiceReviewCard: ["transcript", "medicine", "quantity", "payment"],
    PhotoReviewCard: ["file", "medicine", "form", "unit", "pack_size", "barcode", "batch", "expiry", "shelf"],
    MedicineMatchCard: ["message", "medicine", "form", "unit", "selling_price", "quantity", "payment", "stock", "cost_price", "supplier", "batch", "expiry", "alias"],
    VisualScanCard: ["scan_type", "medicine", "form", "unit", "pack_size", "quantity", "selling_price", "cost_price", "supplier", "barcode", "batch", "expiry", "shelf", "category"],
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
