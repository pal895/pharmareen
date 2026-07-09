export function cardFieldsFor(type) {
  const base = {
    SaleCard: ["medicine", "quantity", "payment", "stockLeft"],
    InvoiceCard: ["supplier", "medicine", "quantity", "unit", "total", "payment"],
    RestockCard: ["medicine", "quantity", "unit", "supplier"],
    OnboardingCard: ["pharmacy", "owner", "branch", "location", "payments"],
    StockCorrectionCard: ["medicine", "current_stock", "correct_stock", "reason"],
    ReportCard: ["period", "focus", "backend_route"],
    VoiceReviewCard: ["transcript", "medicine", "quantity", "payment"],
    PhotoReviewCard: ["file", "medicine", "form", "unit", "pack_size"],
    MedicineMatchCard: ["message", "medicine", "quantity", "payment", "choice", "alias"],
    VisualScanCard: ["scan_type", "medicine", "form", "unit", "pack_size", "category"],
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
