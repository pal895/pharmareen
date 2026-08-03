import assert from "node:assert/strict";
import fs from "node:fs";
import { parseSaleDirectCommand } from "../src/services/saleDirectCommand.js";
import { completedSaleByReference } from "../src/services/saleAdjustmentReview.js";

assert.deepEqual(parseSaleDirectCommand("open sale 1"), { action: "open", target: "number", saleNumber: 1 });
assert.deepEqual(parseSaleDirectCommand("  OPEN   SALE 42 "), { action: "open", target: "number", saleNumber: 42 });
assert.deepEqual(parseSaleDirectCommand("sale 1"), { action: "open", target: "number", saleNumber: 1 });
assert.deepEqual(parseSaleDirectCommand("open cell one"), { action: "open", target: "number", saleNumber: 1 });
assert.deepEqual(parseSaleDirectCommand("return sale 2"), { action: "return", target: "number", saleNumber: 2 });
assert.deepEqual(parseSaleDirectCommand("refund sale 3"), { action: "refund", target: "number", saleNumber: 3 });
assert.deepEqual(parseSaleDirectCommand("refund sale four"), { action: "refund", target: "number", saleNumber: 4 });
assert.deepEqual(parseSaleDirectCommand("refund sale number 4"), { action: "refund", target: "number", saleNumber: 4 });
assert.deepEqual(parseSaleDirectCommand("refund sale number four"), { action: "refund", target: "number", saleNumber: 4 });
assert.deepEqual(parseSaleDirectCommand("credit sale 5"), { action: "credit", target: "number", saleNumber: 5 });
assert.deepEqual(parseSaleDirectCommand("credit sale number five"), { action: "credit", target: "number", saleNumber: 5 });
assert.deepEqual(parseSaleDirectCommand("undo sale 6"), { action: "undo", target: "number", saleNumber: 6 });
assert.deepEqual(parseSaleDirectCommand("undo sale number six"), { action: "undo", target: "number", saleNumber: 6 });
assert.deepEqual(parseSaleDirectCommand("open last sale"), { action: "open", target: "last" });
assert.deepEqual(parseSaleDirectCommand("return last sale"), { action: "return", target: "last" });
assert.deepEqual(parseSaleDirectCommand("refund last sale"), { action: "refund", target: "last" });
assert.deepEqual(parseSaleDirectCommand("undo last sale"), { action: "undo", target: "last" });
assert.equal(parseSaleDirectCommand("credit last sale"), null);
assert.equal(parseSaleDirectCommand("return cell to"), null);
assert.equal(parseSaleDirectCommand("return cell two"), null);
assert.equal(parseSaleDirectCommand("refund cell three"), null);
assert.equal(parseSaleDirectCommand("refund sale number"), null);
assert.equal(parseSaleDirectCommand("refund medicine 4"), null);
assert.equal(parseSaleDirectCommand("open sale 0"), null);
assert.equal(parseSaleDirectCommand("open 1"), null);
assert.equal(parseSaleDirectCommand("ibuprofen"), null);
assert.equal(parseSaleDirectCommand("open capsules"), null);

const immutableSales = [
  { id: "sale-1-old", permanentId: "sale-1-old", kind: "sale", status: "completed", saleNumber: 1, businessDay: "2026-08-01" },
  { id: "sale-4", permanentId: "sale-4", kind: "sale", status: "completed", saleNumber: 4, businessDay: "2026-08-01", metadata: { fullyAdjusted: true } },
  { id: "sale-1", permanentId: "sale-1", kind: "sale", status: "completed", saleNumber: 1, businessDay: "2026-08-02", syncStatus: "synced" }
];
for (const [text, expectedId] of [["open sale 1", "sale-1"], ["open sale 4", "sale-4"], ["sale 1", "sale-1"]]) {
  const command = parseSaleDirectCommand(text);
  const before = JSON.stringify(immutableSales);
  assert.equal(completedSaleByReference(immutableSales, { saleNumber: command.saleNumber })?.id, expectedId);
  assert.equal(JSON.stringify(immutableSales), before, `${text} must be read-only`);
}
assert.equal(completedSaleByReference(immutableSales, { saleNumber: 99 }), null);
assert.equal(completedSaleByReference(immutableSales, { transactionId: "sale-1-old" })?.id, "sale-1-old");
assert.equal(completedSaleByReference(immutableSales, { latest: true })?.id, "sale-1");

const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
assert.match(app, /function routePriorityCommand\(text\)/);
assert.match(app, /if \(routePriorityCommand\(trimmed\)\) return/);
assert.match(app, /function handleVoiceTranscript\(text\)[\s\S]*?if \(routePriorityCommand\(text\)\) return;[\s\S]*?buildCommandCard\(text\)/);
assert.match(app, /direct\.action === "open"/);
assert.match(app, /direct\.target === "last" \? \{ latest: true \} : \{ saleNumber: direct\.saleNumber \}/);
assert.match(app, /openCompletedSale\(reference\)/);
assert.match(app, /direct\.action === "return"[\s\S]*?openCompletedSale\(reference, \{ adjustmentType: "return" \}\)/);
assert.match(app, /direct\.action === "refund"[\s\S]*?openCompletedSale\(reference, \{ adjustmentType: "refund" \}\)/);
assert.match(app, /direct\.action === "credit"[\s\S]*?openCompletedSale\(reference, \{ adjustmentType: "credit" \}\)/);
assert.match(app, /direct\.action === "undo"[\s\S]*?openCompletedSale\(reference, \{ undoReview: true \}\)/);
assert.match(app, /This completed sale could not be found in local transaction history\. Nothing was changed\./);
assert.doesNotMatch(app, /completedSaleByReference\(state\.transactions/);
assert.match(app, /function openCompletedSale\(reference, options = \{\}\)[\s\S]*?completedSaleByReference\(transactionEngine\.list\(\), reference\)/);
assert.match(app, /\["return", "refund", "credit"\]\.includes\(options\.adjustmentType\)[\s\S]*?startSaleAdjustment\(card\.id, options\.adjustmentType\)/);
assert.match(app, /function confirmSaleUndo\(cardId\)[\s\S]*?transactionEngine\.undoSale\(original\.saleNumber, "owner_direct_command"\)/);
assert.match(app, /if \(result\.created\)[\s\S]*?stockToRestore[\s\S]*?type: "SaleUndo"/);
assert.match(app, /if \(reversal\)[\s\S]*?fields\.adjustment_available = false[\s\S]*?linked Undo/);

console.log("SALE_DIRECT_COMMAND_OK cases=open-sale-1,open-sale-4,sale-1,return-sale-2,refund-sale-3,credit-sale-5,undo-sale-6,open-return-refund-undo-last-sale voice=shared-priority medicine=fallback undo=review-confirm-linked-idempotent");
