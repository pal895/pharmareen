import { CashPaymentAdapter, ManualPaymentAdapter, SimulatorPaymentAdapter } from "../src/services/paymentAdapters.js";
import { TransactionCompletionEngine } from "../src/services/transactionCompletionEngine.js";

const assert = (condition, message) => { if (!condition) throw new Error(message); };
let current = new Date("2026-07-16T08:00:00.000Z");
const simulator = new SimulatorPaymentAdapter();
const engine = new TransactionCompletionEngine({
  storage: null,
  now: () => current,
  adapters: {
    cash: new CashPaymentAdapter(),
    manual: new ManualPaymentAdapter(),
    simulator
  }
});

const first = engine.start({ id: "sale-a", kind: "sale", amount: 120, paymentMethod: "cash" });
assert(first.transaction.status === "completed" && first.transaction.saleLabel === "Sale 1", "Fast cash sale must complete with daily numbering");
const duplicate = engine.start({ id: "sale-a", kind: "sale", amount: 120, paymentMethod: "cash" });
assert(duplicate.duplicate && engine.list().length === 1, "Transaction IDs must be idempotent");

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

console.log("Transaction Completion Engine verification passed: adapter isolation, Fast Record, Request & Verify queue, simulator outcomes, daily sale numbering, idempotency, duplicate callbacks, and undo/reversal linkage.");
