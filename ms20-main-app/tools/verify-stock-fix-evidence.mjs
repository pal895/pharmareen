import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
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

const cameraFixture = JSON.parse(readFileSync(new URL("../fixtures/stock-fix-metronidazole-400mg-camera.json", import.meta.url), "utf8"));
const cameraImage = readFileSync(new URL(`../fixtures/${cameraFixture.fileName}`, import.meta.url));
assert.equal(createHash("sha256").update(cameraImage).digest("hex"), cameraFixture.sha256, "camera fixture hash must remain exact");
const cameraCatalog = [{ id: "metro", name: "Metronidazole", stockLeft: 36 }];
const cameraOcr = {
  visible_text: "METRONIDAZOLE 400 mg TABLETS 20 tablets Batch MET-400C EXP 2029-03",
  strength: "400 mg", form: "tablet", unit: "tablet", batch: "MET-400C", expiry: "2029-03", confidence: 0.94
};
const cameraResult = normalizeStockFixEvidence(cameraOcr, cameraCatalog, "camera");
assert.equal(cameraResult.canonicalName, "Metronidazole");
assert.equal(cameraResult.currentStock, 36, "camera evidence must read stock only from the saved catalog");
assert.deepEqual(cameraResult.fieldsStillRequired, ["correct_stock", "reason"]);
const cameraDraft = hydrateStockFixDraft({ correct_stock: "", reason: "" }, cameraResult);
assert.equal(cameraDraft.batch, "MET-400C");
assert.equal(cameraDraft.expiry, "2029-03");
assert.equal(cameraDraft.correct_stock, "", "camera evidence must never invent corrected stock");
console.log("Stock Fix shared evidence checks passed.");
