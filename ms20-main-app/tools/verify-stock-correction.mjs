import assert from "node:assert/strict";
import { reviewStockCorrection } from "../src/services/stockCorrectionPolicy.js";

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

console.log("Stock correction policy verification passed: canonical identity, trusted-current comparison, non-negative whole stock, audit reason, no-op rejection, and queued-not-applied metadata.");
