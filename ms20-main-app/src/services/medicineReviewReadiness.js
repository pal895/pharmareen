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
  if (!String(card.fields?.medicine || "").trim()) {
    if (card.type === "VisualScanCard" && card.fields?.scan_type === "barcode" && card.fields?.barcode) {
      return "Barcode read, but no medicine match was found. Add the medicine name before confirming, or cancel without saving.";
    }
    return "Add the medicine name before confirming. Nothing has been saved.";
  }
  if (card.type === "MedicineMatchCard") {
    const quantity = Number(card.fields?.quantity);
    const sellingPrice = Number(card.fields?.selling_price);
    const payment = String(card.fields?.payment || "").replace("-", "").toLowerCase();
    if (!Number.isFinite(quantity) || quantity <= 0) return "Add a positive sale quantity before confirming. Nothing has been saved.";
    if (!["cash", "mpesa", "credit", "mixed"].includes(payment)) return "Choose how the customer paid before confirming. Nothing has been saved.";
    if (!Number.isFinite(sellingPrice) || sellingPrice <= 0) return "Add the selling price before confirming this new medicine. Nothing has been saved.";
  }
  if (card.type === "RestockCard") {
    const quantity = Number(card.fields?.quantity);
    const bonus = Number(card.fields?.bonus_quantity || 0);
    if (!Number.isFinite(quantity) || quantity <= 0) return "Add the stock quantity before confirming. Nothing has been saved.";
    if (!Number.isFinite(bonus) || bonus < 0) return "Bonus stock cannot be below zero. Check it before confirming.";
    if (!String(card.fields?.unit || "").trim()) return "Add the unit, such as tablet, bottle, pack, or box, before confirming.";
  }
  return "";
}
