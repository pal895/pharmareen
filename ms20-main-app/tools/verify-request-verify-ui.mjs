import fs from "node:fs";

const source = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
const styles = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
const assert = (condition, message) => { if (!condition) throw new Error(message); };

assert(source.includes('state.ui.screen === "payments" ? paymentQueueScreenTemplate()'), "Payment Queue must be a first-class screen");
assert(source.includes('root.querySelector("#paymentQueueBody")?.scrollTo({ top: 0 })'), "Payment Queue must open at its heading instead of inheriting a scrolled position");
assert(source.includes('data-action="set-completion-mode"'), "Owner must be able to choose the completion mode");
assert(source.includes('data-mode="request_verify"'), "Request & Verify must be owner-selectable");
assert(source.includes('requestVerify ? "request_verify" : "fast_record"'), "Confirmed sales must route through the selected completion mode");
assert(source.includes('requestVerify ? "simulator"'), "Request & Verify must remain simulator-only at this stage");
assert(source.includes('new SimulatorPaymentAdapter({ scenario: "delayed_confirmation" })'), "Live simulator requests must enter the waiting queue before owner resolution");
assert(source.includes('transactionResult?.transaction?.status === "pending"'), "Pending requests must not use the completed-sale path");
assert(source.includes("processTransactionProviderEvent(transactionId"), "Simulator and future provider callbacks must share one completion root");
assert(source.includes("applyConfirmedPendingSale(result.transaction)"), "Only confirmation may apply deferred sale stock");
assert(source.includes("transaction.metadata?.stockApplied"), "Deferred stock application must be idempotent");
assert(source.includes("You can keep serving"), "Pending copy must explicitly preserve non-blocking service");
assert(source.includes("transactionDayLabel(item)"), "Queue history must distinguish daily sale-number resets");
assert(source.includes("productionSaleCardBody(saleFieldsFromTransaction(item)"), "Waiting payments must use the shared Production Sales Card, including the amount the owner is verifying");
assert(source.includes("paymentHistoryLineTemplate"), "Completed history must use the financially complete transaction summary");
assert(source.includes("${escapeHtml(medicine)} x${quantity}"), "History must identify the medicine and quantity");
assert(source.includes('return `KES ${value.toLocaleString("en-KE"'), "Payment amounts must use an explicit Kenyan currency label");
assert(styles.includes(".payment-queue-body") && styles.includes(".operation-card"), "Payment Queue must have responsive card styling");
assert(styles.includes(".payment-setup-card .card-actions button.selected"), "Only the selected completion mode may use the filled active style");
assert(!source.includes('<button class="show-me-action"'), "Home must not duplicate the SHOW ME catalog card");
assert(source.includes('data-action="open-catalog" aria-label="Open Pharmacy Catalog"'), "Header catalog access must remain protected");
assert(source.includes('data-action="open-catalog-card"'), "Catalog result cards must keep their Open catalog route");
assert(source.includes('simulatorMode ? `<div class="card-actions">'), "Simulator controls must be environment-gated");
assert(source.includes("buildTransactionNotification"), "Failed payments must use the shared durable notification builder");

console.log("Request & Verify UI verification passed: owner mode selection, explicit verification amounts, complete history, simulator-only routing, non-blocking queue, confirmation-gated idempotent stock mutation, and mobile card layout.");
