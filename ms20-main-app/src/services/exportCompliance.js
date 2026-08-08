import { buildCanonicalInventoryExport, validateInventoryExportSnapshot } from "./documentGenerator.js";

export const EXPORT_HISTORY_RETENTION_DAYS = 30;
export const EXPORT_SCOPES = Object.freeze({ PRIVATE: "private", SAFER_SHARING: "safer_sharing" });
export const EXPORT_ASSET_LICENSE_REGISTER = Object.freeze([
  Object.freeze({ asset: "MS2.0 export layouts and generators", licence: "Pharmareen proprietary", use: "Owner-authorized pharmacy exports" }),
  Object.freeze({ asset: "Office Open XML and PDF file formats", licence: "Open interoperability standards", use: "Deterministic document packaging" }),
  Object.freeze({ asset: "Microsoft Excel, Word and PowerPoint names", licence: "Third-party trademarks used descriptively", use: "Compatibility guidance only; no affiliation or endorsement claimed" })
]);

export function normalizeExportScope(value) {
  return value === EXPORT_SCOPES.SAFER_SHARING ? EXPORT_SCOPES.SAFER_SHARING : EXPORT_SCOPES.PRIVATE;
}

export function prepareCompliantExport({ model, format, scope, activePharmacyId }) {
  validateInventoryExportSnapshot(model);
  if (!activePharmacyId || model.pharmacyId !== activePharmacyId) throw new Error("Export pharmacy identity does not match the active pharmacy.");
  if (!/^(csv|xlsx|pdf|docx|pptx|print)$/.test(String(format || ""))) throw new Error("This export format is not registered.");
  const normalizedScope = normalizeExportScope(scope);
  if (normalizedScope === EXPORT_SCOPES.PRIVATE) return Object.freeze({ model, scope: normalizedScope, redactedFields: Object.freeze([]) });
  const items = model.rows.map((row) => ({
    name: row.medicine, strength: row.strength, forms: [row.form], units: [row.unit],
    sellingPrice: row.sellingPrice, costPrice: "", stockLeft: row.stock, reorderLevel: row.reorderLevel,
    supplier: "", barcode: "", batches: [{ batch: "", expiry: row.expiry }], shelf: ""
  }));
  const redacted = buildCanonicalInventoryExport({
    pharmacy: { id: model.pharmacyId, name: model.pharmacyName, branch: model.branch, location: "Kenya" },
    items, generatedAt: new Date(model.generatedIso)
  });
  return Object.freeze({ model: redacted, scope: normalizedScope, redactedFields: Object.freeze(["cost price", "supplier", "barcode", "batch", "shelf", "precise location"]) });
}

export function retainedExportHistory(records, { now = new Date(), retentionDays = EXPORT_HISTORY_RETENTION_DAYS } = {}) {
  const cutoff = now.getTime() - retentionDays * 24 * 60 * 60 * 1000;
  return (Array.isArray(records) ? records : []).filter((record) => {
    const instant = Date.parse(record?.generatedIso || "");
    return Number.isFinite(instant) && instant >= cutoff && instant <= now.getTime() + 60_000;
  });
}

export function exportScopeLabel(scope) {
  return normalizeExportScope(scope) === EXPORT_SCOPES.SAFER_SHARING ? "Safer sharing copy" : "Private pharmacy copy";
}
