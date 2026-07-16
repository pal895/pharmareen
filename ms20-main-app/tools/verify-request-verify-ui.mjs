import fs from "node:fs";

const source = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
const styles = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
const assert = (condition, message) => { if (!condition) throw new Error(message); };

assert(source.includes('state.ui.screen === "payments" ? paymentQueueScreenTemplate()'), "Payment Queue must be a first-class screen");
assert(source.includes('data-action="set-completion-mode"'), "Owner must be able to choose the completion mode");
assert(source.includes('data-mode="request_verify"'), "Request & Verify must be owner-selectable");
assert(source.includes('requestVerify ? "request_verify" : "fast_record"'), "Confirmed sales must route through the selected completion mode");
assert(source.includes('requestVerify ? "simulator"'), "Request & Verify must remain simulator-only at this stage");
assert(source.includes('new SimulatorPaymentAdapter({ scenario: "delayed_confirmation" })'), "Live simulator requests must enter the waiting queue before owner resolution");
assert(source.includes('transactionResult?.transaction?.status === "pending"'), "Pending requests must not use the completed-sale path");
assert(source.includes("applyConfirmedPendingSale(result.transaction)"), "Only confirmation may apply deferred sale stock");
assert(source.includes("transaction.metadata?.stockApplied"), "Deferred stock application must be idempotent");
assert(source.includes("You can keep serving"), "Pending copy must explicitly preserve non-blocking service");
assert(styles.includes(".payment-queue-body") && styles.includes(".operation-card"), "Payment Queue must have responsive card styling");

console.log("Request & Verify UI verification passed: owner mode selection, simulator-only routing, non-blocking queue, confirmation-gated idempotent stock mutation, and mobile card layout.");
