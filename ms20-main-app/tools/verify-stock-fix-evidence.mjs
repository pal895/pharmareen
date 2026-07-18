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
  assert.deepEqual(result.fieldsStillRequired, ["correct_stock"]);
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
assert.deepEqual(cameraResult.fieldsStillRequired, ["correct_stock"]);
const cameraDraft = hydrateStockFixDraft({ correct_stock: "", reason: "" }, cameraResult);
assert.equal(cameraDraft.batch, "MET-400C");
assert.equal(cameraDraft.expiry, "2029-03");
assert.equal(cameraDraft.correct_stock, "", "camera evidence must never invent corrected stock");

const nameMissed = normalizeStockFixEvidence({
  visible_text: "400 mg TABLETS 20 tablets Batch MET-400C EXP 2029-03",
  strength: "400 mg", form: "tablet", unit: "tablet", batch: "MET-400C", expiry: "2029-03", confidence: 0.88
}, [{ id: "metro", name: "Metronidazole", stockLeft: 34, batch: "MET-400C", strength: "400 mg", expiry: "2029-03" }], "camera");
assert.equal(nameMissed.canonicalName, "Metronidazole", "a unique saved batch must recover a missed printed name safely");
assert.equal(nameMissed.currentStock, 34);
assert.equal(nameMissed.matchBasis, "unique_catalog_batch");
const duplicateBatch = normalizeStockFixEvidence({ visible_text: "Batch SHARED-1", batch: "SHARED-1" }, [
  { name: "Medicine A", stockLeft: 2, batch: "SHARED-1" },
  { name: "Medicine B", stockLeft: 3, batch: "SHARED-1" }
], "camera");
assert.equal(duplicateBatch.canonicalName, "", "a non-unique package identifier must never choose a medicine");

const fileFixture = JSON.parse(readFileSync(new URL("../fixtures/stock-fix-ibuprofen-200mg-file.json", import.meta.url), "utf8"));
const fileImage = readFileSync(new URL(`../fixtures/${fileFixture.fileName}`, import.meta.url));
assert.equal(createHash("sha256").update(fileImage).digest("hex"), fileFixture.sha256, "File fixture hash must remain exact");
const fileCatalog = [{
  id: "ibuprofen", name: "Ibuprofen", stockLeft: 28, strength: "200 mg", form: "tablet", unit: "tablet", batch: "IBU-200C", expiry: "2028-12"
}];
const fileResult = normalizeStockFixEvidence({
  visible_text: "IBUPROFEN 200 mg TABLETS 24 tablets Batch IBU-200C EXP 2028-12",
  strength: "200 mg", form: "tablet", unit: "tablet", batch: "IBU-200C", expiry: "2028-12", confidence: 0.94
}, fileCatalog, "file");
assert.equal(fileResult.canonicalName, "Ibuprofen");
assert.equal(fileResult.currentStock, 28, "File evidence must read stock only from the saved catalog");
assert.equal(fileResult.evidenceSource, "file");
assert.deepEqual(fileResult.fieldsStillRequired, ["correct_stock"]);
const fileDraft = hydrateStockFixDraft({ correct_stock: "", reason: "" }, fileResult);
assert.equal(fileDraft.batch, "IBU-200C");
assert.equal(fileDraft.expiry, "2028-12");
assert.equal(fileDraft.correct_stock, "");
assert.equal(fileDraft.reason, "");
console.log("Stock Fix shared evidence checks passed.");
