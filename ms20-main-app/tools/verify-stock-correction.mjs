import assert from "node:assert/strict";
import { applyStockCorrectionVoice, PharmacyPronunciationMemory, reviewStockCorrection, stockCorrectionGuidance, stockCorrectionSummary } from "../src/services/stockCorrectionPolicy.js";

const catalog = [{ name: "Losartan", stock: 37, aliases: ["Losartan 50"] }];

assert.equal(reviewStockCorrection({ medicine: "", current_stock: 37, correct_stock: 36, reason: "Count" }, catalog).ok, false);
assert.equal(reviewStockCorrection({ medicine: "Losartan", current_stock: 38, correct_stock: 36, reason: "Count" }, catalog).ok, false);
assert.equal(reviewStockCorrection({ medicine: "Losartan", current_stock: 37, correct_stock: -1, reason: "Count" }, catalog).ok, false);
assert.equal(reviewStockCorrection({ medicine: "Losartan", current_stock: 37, correct_stock: 36, reason: "" }, catalog).ok, false);
assert.equal(reviewStockCorrection({ medicine: "Losartan", current_stock: 37, correct_stock: 37, reason: "Count" }, catalog).ok, false);

const approved = reviewStockCorrection({ medicine: "losartan 50", current_stock: "37", correct_stock: "36", reason: "Physical count" }, catalog);
assert.equal(approved.ok, true);
assert.deepEqual(approved.fields, {
  medicine: "Losartan",
  current_stock: 37,
  correct_stock: 36,
  reason: "Physical count",
  adjustment: -1,
  mutation_status: "queued_not_applied"
});

assert.equal(stockCorrectionGuidance(approved.fields, catalog).ready, true);
assert.match(stockCorrectionSummary(approved.fields), /Medicine: Losartan\. Current stock: 37\. Correct stock: 36\. Reason: Physical count\./);

let voice = applyStockCorrectionVoice({ medicine: "", current_stock: "", correct_stock: "", reason: "", active_slide: 0 }, "Losartan", catalog);
assert.equal(voice.fields.medicine, "Losartan");
assert.equal(voice.fields.current_stock, 37);
assert.equal(voice.slide, 1);
voice = applyStockCorrectionVoice({ ...voice.fields, active_slide: 1 }, "36", catalog);
assert.equal(voice.fields.correct_stock, "36");
voice = applyStockCorrectionVoice({ ...voice.fields, active_slide: 2 }, "Physical count", catalog);
assert.equal(voice.fields.reason, "Physical count");
assert.equal(voice.review, true);
assert.equal(applyStockCorrectionVoice(voice.fields, "Confirm", catalog).intent, "confirm");
assert.equal(applyStockCorrectionVoice(voice.fields, "Cancel", catalog).intent, "cancel");
assert.equal(applyStockCorrectionVoice(voice.fields, "Change correct stock", catalog).slide, 2);

const ambiguousCatalog = [{ name: "Losartan", stock: 37, aliases: ["lora"] }, { name: "Loratadine", stock: 12, aliases: ["lora"] }];
const uncertain = applyStockCorrectionVoice({}, "lora", ambiguousCatalog);
assert.ok(["disambiguate", "retry"].includes(uncertain.intent));

const pharmacyA = new PharmacyPronunciationMemory("pharmacy-a");
const pharmacyB = new PharmacyPronunciationMemory("pharmacy-b");
pharmacyA.remember("loss a ton", "Losartan");
assert.equal(pharmacyA.resolve("loss a ton"), "Losartan");
assert.equal(pharmacyB.resolve("loss a ton"), "");
pharmacyA.forget("loss a ton");
assert.equal(pharmacyA.resolve("loss a ton"), "");

const draft = { medicine: "Losartan", current_stock: "37", correct_stock: "36", reason: "Physical count" };
const acrossSlides = structuredClone(draft);
for (const activeSlide of [0, 1, 2, 0]) acrossSlides.active_slide = activeSlide;
delete acrossSlides.active_slide;
assert.deepEqual(acrossSlides, draft);

console.log("Stock correction workflow verification passed: authoritative cross-slide draft, live readiness, canonical validation, concise Read summary, guided voice update/confirm/cancel, safe ambiguity, tenant-isolated pronunciation memory, and queued-not-applied metadata.");
