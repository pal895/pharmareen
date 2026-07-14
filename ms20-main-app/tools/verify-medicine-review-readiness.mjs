import { medicineReviewBlocker } from "../src/services/medicineReviewReadiness.js";

const assert = (condition, message) => { if (!condition) throw new Error(message); };
const unknownBarcode = {
  type: "VisualScanCard",
  fields: { scan_type: "barcode", barcode: "6161109876560", medicine: "" }
};

assert(medicineReviewBlocker(unknownBarcode).includes("no medicine match"), "Unknown decoded barcode must explain the missing match");
assert(medicineReviewBlocker({ type: "PhotoReviewCard", fields: { medicine: "" } }).includes("Add the medicine name"), "Incomplete photo review must share the medicine identity gate");
assert(medicineReviewBlocker({ type: "MedicineMatchCard", fields: { medicine: "Loperamide" } }) === "", "Complete medicine review must remain confirmable");
assert(medicineReviewBlocker({ type: "ReportCard", fields: {} }) === "", "Unrelated cards must not inherit the medicine gate");

console.log("Medicine review readiness verification passed: unknown barcode messaging, shared missing-identity gate, complete review allowance, and unrelated-card isolation.");
