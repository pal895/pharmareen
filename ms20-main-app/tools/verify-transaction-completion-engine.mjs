import { CashPaymentAdapter, DeferredPaymentAdapter, ManualPaymentAdapter, SimulatorPaymentAdapter } from "../src/services/paymentAdapters.js";
import { saleReversalFor, saleReversalReconciliation, TransactionCompletionEngine } from "../src/services/transactionCompletionEngine.js";

const assert = (condition, message) => { if (!condition) throw new Error(message); };
let current = new Date("2026-07-16T08:00:00.000Z");
const simulator = new SimulatorPaymentAdapter();
const engine = new TransactionCompletionEngine({
  storage: null,
  now: () => current,
  adapters: {
    cash: new CashPaymentAdapter(),
    manual: new ManualPaymentAdapter(),
    deferred: new DeferredPaymentAdapter(),
    simulator
  }
});

const first = engine.start({ id: "sale-a", kind: "sale", amount: 120, paymentMethod: "cash" });
assert(first.transaction.status === "completed" && first.transaction.saleLabel === "Sale 1", "Fast cash sale must complete with daily numbering");
const duplicate = engine.start({ id: "sale-a", kind: "sale", amount: 120, paymentMethod: "cash" });
assert(duplicate.duplicate && engine.list().length === 1, "Transaction IDs must be idempotent");

const supplierEngine = new TransactionCompletionEngine({ storage: null, now: () => current, adapters: { cash: new CashPaymentAdapter(), manual: new ManualPaymentAdapter(), deferred: new DeferredPaymentAdapter() } });
const paidSupplier = supplierEngine.start({ id: "supplier-paid-a", kind: "supplier_payment", amount: 180, paymentMethod: "cash", adapter: "cash", metadata: { financialDirection: "outflow", supplier: "AfyaLink" } });
assert(paidSupplier.transaction.status === "completed" && paidSupplier.transaction.metadata.financialDirection === "outflow", "Paid supplier restock must cross the TCE boundary as a completed outflow");
const supplierCredit = supplierEngine.start({ id: "supplier-credit-a", kind: "supplier_credit", amount: 180, paymentMethod: "supplier_credit", adapter: "manual", metadata: { financialDirection: "outflow", supplier: "AfyaLink" } });
assert(supplierCredit.transaction.status === "completed" && supplierCredit.transaction.paymentMethod === "supplier_credit", "Supplier credit must be recorded as an explicit completed liability event");
const futureSupplier = supplierEngine.start({ id: "supplier-due-a", kind: "supplier_settlement_due", amount: 180, paymentMethod: "pay_later", mode: "request_verify", adapter: "deferred", metadata: { financialDirection: "outflow", settlementDate: "2026-08-10" } });
assert(futureSupplier.transaction.status === "pending" && futureSupplier.transaction.metadata.settlementDate === "2026-08-10", "Future supplier settlement must remain pending with its explicit due date");
assert(supplierEngine.start({ id: "supplier-due-a", kind: "supplier_settlement_due", amount: 180, adapter: "deferred" }).duplicate, "Supplier payment records must remain idempotent");

const stableOriginal = { id: "runtime-sale-a", permanentId: "sale-a", kind: "sale" };
const stableReversal = { id: "undo-old-runtime-sale-a", permanentId: "undo-sale-a", kind: "sale_reversal", reversalOf: "old-runtime-sale-a" };
assert(saleReversalFor([stableReversal], stableOriginal) === stableReversal, "Linked Undo lookup must survive runtime ID rehydration through permanent identity");
const reconciliation = saleReversalReconciliation([
  { ...stableReversal, amount: -18, paymentStatus: "reversed", status: "completed", reason: "owner_direct_command", createdAt: "2026-08-03T08:00:00.000Z", saleLabel: "Undo Sale 2" }
], { ...stableOriginal, saleNumber: 2, saleLabel: "Sale 2", status: "completed", amount: 18, metadata: { quantity: 1, baseStockDeduction: 1 } });
assert(reconciliation.stock_restored === 1 && reconciliation.finance_reversed === 18 && reconciliation.report_net === 0, "Reversal reconciliation must balance stock, finance and report impact exactly once");
assert(reconciliation.original_receipt === "Sale 2" && reconciliation.reversal_receipt === "Undo Sale 2" && reconciliation.payment_status === "reversed", "Reversal reconciliation must retain receipt and audit truth");

simulator.setScenario("delayed_confirmation");
const second = engine.start({
  id: "sale-b",
  kind: "sale",
  amount: 240,
  paymentMethod: "mpesa",
  mode: "request_verify",
  adapter: "simulator"
});
assert(second.transaction.status === "pending" && second.transaction.saleLabel === "Sale 2", "Request & Verify must enter a non-blocking pending queue");
assert(engine.pending().length === 1, "Pending payment queue must be queryable");
assert(second.transaction.metadata && Object.keys(second.transaction.metadata).length === 0, "Pending transactions must preserve a metadata envelope for deferred completion");
const confirmed = engine.providerEvent("sale-b", { key: "callback-1", status: "confirmed" });
assert(confirmed.transaction.status === "completed", "Provider confirmation must complete the transaction");
assert(engine.providerEvent("sale-b", { key: "callback-1", status: "confirmed" }).duplicate, "Duplicate callbacks must be ignored");
assert(engine.pending().length === 0, "Confirmed transactions must leave the pending queue");

simulator.setScenario("delayed_confirmation");
const identity = { pharmacyId: "pharmacy-a", branchId: "main", merchantAccountId: "till-a", paymentRequestId: "request-d" };
engine.start({ id: "sale-d", kind: "sale", amount: 25, paymentMethod: "mpesa", mode: "request_verify", adapter: "simulator", metadata: identity });
engine.start({ id: "sale-e", kind: "sale", amount: 40, paymentMethod: "mpesa", mode: "request_verify", adapter: "simulator", metadata: { ...identity, paymentRequestId: "request-e" } });
assert(engine.pending().length === 2, "Concurrent electronic requests must wait independently");
const secondFirst = engine.providerEvent("sale-e", { key: "provider-e", status: "confirmed", amount: 40, ...identity, paymentRequestId: "request-e" });
assert(secondFirst.updated && engine.pending().length === 1 && engine.pending()[0].id === "sale-d", "A second payment may complete first without changing the first request");
const wrongAmount = engine.providerEvent("sale-d", { key: "wrong-amount", status: "confirmed", amount: 26, ...identity });
assert(wrongAmount.rejected && wrongAmount.reason === "amount_mismatch" && engine.pending().length === 1, "Mismatched amounts must be rejected without completion");
const wrongTenant = engine.providerEvent("sale-d", { key: "wrong-tenant", status: "confirmed", amount: 25, ...identity, pharmacyId: "pharmacy-b" });
assert(wrongTenant.rejected && wrongTenant.reason === "pharmacyId_mismatch", "Cross-tenant events must be rejected");
const failed = engine.providerEvent("sale-d", { key: "provider-d-failed", status: "failed", amount: 25, ...identity });
assert(failed.updated && failed.transaction.status === "failed", "Authenticated failure must close only its own request");
assert(engine.providerEvent("sale-d", { key: "late-success", status: "confirmed", amount: 25, ...identity }).terminal, "Late out-of-order events must not rewrite terminal truth");

const productionEngine = new TransactionCompletionEngine({ storage: null, adapters: { simulator: new SimulatorPaymentAdapter({ scenario: "delayed_confirmation" }) } });
productionEngine.configure({ environment: "production" });
productionEngine.start({ id: "production-sale", kind: "sale", amount: 10, paymentMethod: "mpesa", mode: "request_verify", adapter: "simulator" });
assert(productionEngine.providerEvent("production-sale", { key: "manual", status: "confirmed", source: "simulator" }).rejected, "Simulator controls must be rejected in production");

const undo = engine.undoSale(1);
assert(undo.transaction.reversalOf === "sale-a" && undo.transaction.amount === -120, "Undo must create a reconciliable reversal linked to the original sale");
assert(engine.undoSale(1).duplicate, "Undo must not create duplicate reversals");

current = new Date("2026-07-17T08:00:00.000Z");
const nextDay = engine.start({ id: "sale-c", kind: "sale", amount: 50, paymentMethod: "cash" });
assert(nextDay.transaction.saleLabel === "Sale 1", "Daily sale numbering must reset on the next pharmacy business day");

for (const scenario of ["success", "timeout", "cancellation", "wrong_pin", "insufficient_balance", "delayed_confirmation", "duplicate_callback", "failed_payment", "refund", "reversal"]) {
  simulator.setScenario(scenario);
  const result = simulator.request({ transactionId: `scenario-${scenario}` });
  assert(result.status && result.reason, `Simulator scenario ${scenario} must produce a production-shaped result`);
}

console.log("Transaction Completion Engine verification passed: automatic provider events, tenant/amount isolation, concurrent out-of-order completion, terminal truth, simulator separation, daily numbering, idempotency, and reversal linkage.");
