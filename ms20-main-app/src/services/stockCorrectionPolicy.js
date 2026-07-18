import { matchMedicine } from "./medicineMatcher.js";

export function reviewStockCorrection(fields = {}, catalog = []) {
  const medicineText = String(fields.medicine || "").trim();
  const match = matchMedicine(medicineText, catalog);
  if (match.status !== "matched") {
    return {
      ok: false,
      message: match.status === "ambiguous"
        ? "Choose one exact saved medicine before confirming this stock fix."
        : "Choose a medicine from the saved Pharmacy Catalog before confirming this stock fix."
    };
  }

  const medicine = match.matches[0];
  const savedStock = trustedCatalogStock(medicine);
  const enteredCurrent = finiteStock(fields.current_stock);
  const correctStock = finiteStock(fields.correct_stock);
  const reason = String(fields.reason || "").trim();

  if (savedStock === null) return { ok: false, message: "This medicine has no trusted saved stock value. Set it through an approved catalog edit first." };
  if (enteredCurrent === null) return { ok: false, message: "Enter the current saved stock before confirming this stock fix." };
  if (enteredCurrent !== savedStock) return { ok: false, message: `Current saved stock is ${savedStock}. Review the card before confirming.` };
  if (correctStock === null) return { ok: false, message: "Enter a whole-number corrected stock value of zero or more." };
  if (!reason) return { ok: false, message: "Add a short reason for the stock correction audit trail." };
  if (correctStock === savedStock) return { ok: false, message: "Corrected stock matches saved stock. No correction is needed." };

  return {
    ok: true,
    fields: {
      ...fields,
      medicine: medicine.name || medicine.medicine,
      current_stock: savedStock,
      correct_stock: correctStock,
      reason,
      adjustment: correctStock - savedStock,
      mutation_status: "queued_not_applied"
    }
  };
}

export function stockCorrectionGuidance(fields = {}, catalog = []) {
  const review = reviewStockCorrection(fields, catalog);
  if (review.ok) return { ready: true, message: "Ready. Check the details, then tap Confirm. Saved stock will not change yet." };
  return { ready: false, message: review.message };
}

export function stockCorrectionSummary(fields = {}) {
  return [
    `Medicine: ${fields.medicine || "not set"}.`,
    `Current stock: ${fields.current_stock === "" ? "not set" : fields.current_stock}.`,
    `Correct stock: ${fields.correct_stock === "" ? "not set" : fields.correct_stock}.`,
    `Reason: ${fields.reason || "not set"}.`,
    "Say confirm or tap Confirm to continue."
  ].join(" ");
}

export function applyStockCorrectionVoice(fields = {}, transcript = "", catalog = []) {
  const text = String(transcript || "").trim();
  const normalized = text.toLowerCase().replace(/[^a-z0-9\s-]/g, " ").replace(/\s+/g, " ").trim();
  if (/^(confirm|okay confirm|ok confirm)$/.test(normalized)) return { intent: "confirm", fields };
  if (/^(cancel|stop)$/.test(normalized)) return { intent: "cancel", fields };
  if (/^(read|repeat)$/.test(normalized)) return { intent: "read", fields };
  if (/^(go back|back)$/.test(normalized)) return { intent: "slide", slide: Math.max(0, Number(fields.active_slide || 0) - 1), fields };
  const changeTargets = { "change medicine": 0, "change current stock": 1, "change correct stock": 2, "change reason": 2 };
  if (Object.hasOwn(changeTargets, normalized)) return { intent: "slide", slide: changeTargets[normalized], fields };

  const next = { ...fields };
  const currentAndCorrect = normalized.match(/current(?: stock)?\s+(\d+)\D+correct(?: stock)?\s+(\d+)/);
  const correctOnly = normalized.match(/(?:correct(?: stock)?|set(?: stock)? to)\s+(\d+)/);
  if (currentAndCorrect) {
    next.current_stock = currentAndCorrect[1];
    next.correct_stock = currentAndCorrect[2];
    return { intent: "update", slide: 2, fields: next };
  }
  if (correctOnly) {
    next.correct_stock = correctOnly[1];
    return { intent: "update", slide: 2, fields: next };
  }
  if (Number(fields.active_slide) === 1 && /^\d+$/.test(normalized)) {
    next.correct_stock = normalized;
    return { intent: "update", slide: 2, fields: next };
  }
  const reason = normalized.match(/^(?:reason\s+)?(.+)$/);
  if (String(next.medicine || "").trim() && next.current_stock !== "" && next.correct_stock !== "" && !String(next.reason || "").trim() && reason) {
    next.reason = text.replace(/^reason\s+/i, "").trim();
    return { intent: "update", slide: 2, review: true, fields: next };
  }
  const match = matchMedicine(text, catalog);
  if (match.status === "matched") {
    const medicine = match.matches[0];
    next.medicine = medicine.name || medicine.medicine;
    const savedStock = trustedCatalogStock(medicine);
    if (savedStock !== null) next.current_stock = savedStock;
    return { intent: "update", slide: 1, fields: next };
  }
  return {
    intent: match.status === "ambiguous" ? "disambiguate" : "retry",
    choices: (match.matches || []).map((item) => item.name || item.medicine).filter(Boolean),
    fields
  };
}

export class PharmacyPronunciationMemory {
  constructor(pharmacyId, storage = null) {
    this.pharmacyId = String(pharmacyId || "unknown");
    this.storage = storage;
    this.memory = {};
  }

  remember(spoken, canonical) {
    const key = String(spoken || "").trim().toLowerCase();
    if (!key || !canonical) return;
    const entries = this.read();
    entries[key] = String(canonical);
    this.write(entries);
  }

  resolve(spoken) {
    return this.read()[String(spoken || "").trim().toLowerCase()] || "";
  }

  forget(spoken) {
    const entries = this.read();
    delete entries[String(spoken || "").trim().toLowerCase()];
    this.write(entries);
  }

  read() {
    if (!this.storage) return { ...this.memory };
    try { return JSON.parse(this.storage.getItem(this.key()) || "{}"); } catch { return {}; }
  }

  write(entries) {
    this.memory = { ...entries };
    this.storage?.setItem(this.key(), JSON.stringify(entries));
  }

  key() { return `ms20-main-app:pronunciations:${this.pharmacyId}`; }
}

function finiteStock(value) {
  if (value === "" || value === null || value === undefined) return null;
  const number = Number(value);
  return Number.isInteger(number) && number >= 0 ? number : null;
}

export function trustedCatalogStock(medicine = {}) {
  return finiteStock(medicine.stock ?? medicine.stockLeft ?? medicine.current_stock ?? medicine.quantity);
}
