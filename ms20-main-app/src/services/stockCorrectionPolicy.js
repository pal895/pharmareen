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
  const savedStock = finiteStock(medicine.stock ?? medicine.current_stock ?? medicine.quantity);
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

function finiteStock(value) {
  if (value === "" || value === null || value === undefined) return null;
  const number = Number(value);
  return Number.isInteger(number) && number >= 0 ? number : null;
}
