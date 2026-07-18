import assert from "node:assert/strict";
import { hydrateStockFixDraft, normalizeStockFixEvidence } from "../src/services/stockFixEvidencePipeline.js";

const catalog = [
  { id: "pred", name: "Prednisolone", stock: 24 },
  { id: "los", name: "Losartan", stock: 39 }
];
const ocr = {
  visible_text: "PREDNISOLONE 5 mg TABLETS 100 tablets Batch PRE-5T EXP 2028-11",
  strength: "5 mg", form: "tablet", unit: "tablet", batch: "PRE-5T", expiry: "2028-11", confidence: 0.94
};
for (const source of ["camera", "photo", "file"]) {
  const result = normalizeStockFixEvidence(ocr, catalog, source);
  assert.equal(result.canonicalName, "Prednisolone");
  assert.equal(result.currentStock, 24, "saved catalog stock must remain authoritative");
  assert.deepEqual(result.fieldsStillRequired, ["correct_stock", "reason"]);
  const draft = hydrateStockFixDraft({ correct_stock: "", reason: "" }, result);
  assert.equal(draft.current_stock, 24);
  assert.equal(draft.batch, "PRE-5T");
  assert.equal(draft.expiry, "2028-11");
  assert.equal(draft.correct_stock, "", "image evidence must never invent corrected stock");
}
const unknown = normalizeStockFixEvidence({ visible_text: "UNKNOWN PACKAGE 40" }, catalog, "file");
assert.equal(unknown.canonicalName, "");
assert.equal(unknown.currentStock, null);
console.log("Stock Fix shared evidence checks passed.");
