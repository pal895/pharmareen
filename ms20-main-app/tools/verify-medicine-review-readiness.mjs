import { medicineReviewBlocker } from "../src/services/medicineReviewReadiness.js";

const assert = (condition, message) => { if (!condition) throw new Error(message); };
const unknownBarcode = {
  type: "VisualScanCard",
  fields: { scan_type: "barcode", barcode: "6161109876560", medicine: "" }
};

assert(medicineReviewBlocker(unknownBarcode).includes("no medicine match"), "Unknown decoded barcode must explain the missing match");
assert(medicineReviewBlocker({ type: "PhotoReviewCard", fields: { medicine: "" } }).includes("Add the medicine name"), "Incomplete photo review must share the medicine identity gate");
assert(medicineReviewBlocker({ type: "MedicineMatchCard", fields: { medicine: "Loperamide" } }).includes("quantity"), "Incomplete medicine sale review must not expose a safe confirmation path");
assert(medicineReviewBlocker({ type: "MedicineMatchCard", fields: { medicine: "Loperamide", quantity: 1, payment: "cash" } }).includes("selling price"), "A new medicine sale must require its selling price");
assert(medicineReviewBlocker({ type: "MedicineMatchCard", fields: { medicine: "Loperamide", quantity: 1, payment: "cash", selling_price: 50 } }) === "", "Complete medicine review must remain confirmable");
assert(medicineReviewBlocker({ type: "ReportCard", fields: {} }) === "", "Unrelated cards must not inherit the medicine gate");

console.log("Medicine review readiness verification passed: unknown barcode messaging, shared missing-identity gate, complete review allowance, and unrelated-card isolation.");
