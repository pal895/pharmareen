import { matchMedicine } from "./medicineMatcher.js";
import { trustedCatalogStock } from "./stockCorrectionPolicy.js";

export function normalizeStockFixEvidence(ocr = {}, catalog = [], evidenceSource = "photo") {
  const visibleText = String(ocr.visible_text || "").replace(/[^\p{L}\p{N}.\-/\s]/gu, " ").replace(/\s+/g, " ").trim();
  const normalizedEvidence = visibleText.toLowerCase().replace(/[^a-z0-9]/g, "");
  const contained = catalog.filter((item) => {
    const name = String(item.name || item.medicine || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    return name.length >= 4 && normalizedEvidence.includes(name);
  });
  const match = contained.length === 1
    ? { status: "matched", matches: contained }
    : contained.length > 1
      ? { status: "ambiguous", matches: contained }
      : matchMedicine(visibleText, catalog);
  const medicine = match.status === "matched" ? match.matches[0] : null;
  return {
    canonicalMedicineId: medicine?.id || medicine?.medicine_id || "",
    canonicalName: medicine?.name || medicine?.medicine || "",
    displayName: medicine?.name || medicine?.medicine || "",
    strength: String(ocr.strength || "").trim(),
    form: String(ocr.form || "").trim(),
    unit: String(ocr.unit || "").trim(),
    batch: String(ocr.batch || "").trim(),
    expiry: String(ocr.expiry || "").trim(),
    barcode: String(ocr.barcode || "").trim(),
    confidence: medicine ? Math.min(1, Number(ocr.confidence || 0.8)) : Number(ocr.confidence || 0),
    ambiguityChoices: match.status === "ambiguous" ? match.matches.map((item) => item.name || item.medicine) : [],
    evidenceSource,
    currentStock: medicine ? trustedCatalogStock(medicine) : null,
    fieldsStillRequired: medicine ? ["correct_stock"] : ["medicine", "correct_stock"],
    visibleText
  };
}

export function hydrateStockFixDraft(fields = {}, result = {}) {
  return {
    ...fields,
    medicine: result.canonicalName || fields.medicine || "",
    current_stock: result.currentStock ?? fields.current_stock ?? "",
    strength: result.strength || fields.strength || "",
    form: result.form || fields.form || "",
    unit: result.unit || fields.unit || "",
    batch: result.batch || fields.batch || "",
    expiry: result.expiry || fields.expiry || "",
    correct_stock: fields.correct_stock ?? "",
    reason: fields.reason || ""
  };
}
