const MEDICINE_REVIEW_TYPES = new Set([
  "InvoiceCard",
  "RestockCard",
  "StockCorrectionCard",
  "PhotoReviewCard",
  "MedicineMatchCard",
  "VisualScanCard"
]);

export function medicineReviewBlocker(card = {}) {
  if (!MEDICINE_REVIEW_TYPES.has(card.type)) return "";
  if (String(card.fields?.medicine || "").trim()) return "";
  if (card.type === "VisualScanCard" && card.fields?.scan_type === "barcode" && card.fields?.barcode) {
    return "Barcode read, but no medicine match was found. Add the medicine name before confirming, or cancel without saving.";
  }
  return "Add the medicine name before confirming. Nothing has been saved.";
}
