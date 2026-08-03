const STORAGE_KEY = "ms20-main-app:transactions";
const SETTINGS_KEY = "ms20-main-app:transaction-settings";

function safeStorage() {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function saleReversalFor(transactions = [], original = null) {
  if (!original) return null;
  const originalIds = new Set([original.id, original.permanentId].filter(Boolean).map(String));
  const undoIds = new Set([...originalIds].map((id) => `undo-${id}`));
  return transactions.find((item) => {
    if (item.kind !== "sale_reversal") return false;
    if (item.reversalOf && originalIds.has(String(item.reversalOf))) return true;
    return [item.id, item.permanentId].filter(Boolean).some((id) => undoIds.has(String(id)));
  }) || null;
}

export class TransactionCompletionEngine {
  constructor({ adapters = {}, storage = safeStorage(), now = () => new Date() } = {}) {
    this.adapters = new Map(Object.entries(adapters));
    this.storage = storage;
    this.memory = [];
    this.memorySettings = {};
    this.now = now;
  }

  settings() {
    const defaults = { completionMode: "always_fast_record", preferredPaymentMethod: "cash", businessDayStartHour: 0, environment: "simulator" };
    if (!this.storage) return { ...defaults, ...this.memorySettings };
    try {
      return { ...defaults, ...JSON.parse(this.storage.getItem(SETTINGS_KEY) || "{}") };
    } catch {
      return defaults;
    }
  }

  configure(patch = {}) {
    const next = { ...this.settings(), ...patch };
    if (this.storage) this.storage.setItem(SETTINGS_KEY, JSON.stringify(next));
    else this.memorySettings = next;
    return next;
  }

  list() {
    if (!this.storage) return [...this.memory];
    try {
      return JSON.parse(this.storage.getItem(STORAGE_KEY) || "[]");
    } catch {
      return [];
    }
  }

  start({
    id,
    kind,
    amount = 0,
    paymentMethod = "cash",
    mode = "fast_record",
    adapter = paymentMethod === "cash" ? "cash" : "manual",
    reference = "",
    metadata = {}
  }) {
    const transactions = this.list();
    const existing = transactions.find((item) => item.id === id);
    if (existing) return { created: false, duplicate: true, transaction: existing };

    const createdAt = this.now().toISOString();
    const businessDay = this.businessDay(createdAt);
    const saleNumber = kind === "sale"
      ? transactions.filter((item) => item.kind === "sale" && item.businessDay === businessDay && !item.reversalOf).length + 1
      : null;
    const selectedAdapter = this.adapters.get(adapter);
    if (!selectedAdapter) throw new Error(`Payment adapter is not registered: ${adapter}`);

    const payment = selectedAdapter.request({ transactionId: id, amount, paymentMethod, reference, metadata });
    const status = mode === "fast_record" && payment.status === "pending" ? "completed" : transactionStatus(payment.status);
    const transaction = {
      id,
      permanentId: id,
      kind,
      saleNumber,
      saleLabel: saleNumber ? `Sale ${saleNumber}` : "",
      businessDay,
      createdAt,
      updatedAt: createdAt,
      amount,
      paymentMethod,
      completionMode: mode,
      adapter,
      providerReference: payment.providerReference || "",
      paymentStatus: payment.status,
      status,
      reason: payment.reason || "",
      reference,
      metadata,
      callbackKeys: []
    };
    transactions.push(transaction);
    this.save(transactions);
    return { created: true, duplicate: false, transaction };
  }

  providerEvent(transactionId, event = {}) {
    const { key, status, reason = "", source = "provider" } = event;
    const transactions = this.list();
    const index = transactions.findIndex((item) => item.id === transactionId);
    if (index < 0) return { updated: false, missing: true };
    const transaction = transactions[index];
    if (source === "simulator" && this.settings().environment === "production") {
      return { updated: false, rejected: true, reason: "simulator_disabled_in_production", transaction };
    }
    const mismatch = paymentEventMismatch(transaction, event);
    if (mismatch) return { updated: false, rejected: true, reason: mismatch, transaction };
    if (key && transaction.callbackKeys.includes(key)) return { updated: false, duplicate: true, transaction };
    if (transaction.status !== "pending") return { updated: false, terminal: true, transaction };
    const updated = {
      ...transaction,
      paymentStatus: status,
      status: transactionStatus(status),
      reason: reason || transaction.reason,
      updatedAt: this.now().toISOString(),
      callbackKeys: key ? [...transaction.callbackKeys, key] : transaction.callbackKeys
    };
    transactions[index] = updated;
    this.save(transactions);
    return { updated: true, duplicate: false, transaction: updated };
  }

  undoSale(saleNumber, reason = "owner_undo") {
    const transactions = this.list();
    const original = [...transactions].reverse().find((item) =>
      item.kind === "sale" && item.saleNumber === Number(saleNumber) && item.status === "completed" && !item.reversalOf
    );
    if (!original) return { created: false, missing: true };
    const existing = saleReversalFor(transactions, original);
    if (existing) return { created: false, duplicate: true, transaction: existing };
    const createdAt = this.now().toISOString();
    const reversal = {
      ...original,
      id: `undo-${original.id}`,
      permanentId: `undo-${original.permanentId}`,
      kind: "sale_reversal",
      saleLabel: `Undo Sale ${original.saleNumber}`,
      createdAt,
      updatedAt: createdAt,
      amount: -Math.abs(Number(original.amount || 0)),
      status: "completed",
      paymentStatus: "reversed",
      reason,
      reversalOf: original.id,
      callbackKeys: []
    };
    transactions.push(reversal);
    this.save(transactions);
    return { created: true, duplicate: false, transaction: reversal, original };
  }

  pending() {
    return this.list().filter((item) => item.status === "pending");
  }

  businessDay(value = this.now().toISOString()) {
    const date = new Date(value);
    date.setHours(date.getHours() - Number(this.settings().businessDayStartHour || 0));
    return date.toISOString().slice(0, 10);
  }

  save(transactions) {
    if (!this.storage) this.memory = [...transactions];
    else this.storage.setItem(STORAGE_KEY, JSON.stringify(transactions));
  }
}

function paymentEventMismatch(transaction, event) {
  const checks = [["amount", Number], ["pharmacyId", String], ["branchId", String], ["merchantAccountId", String], ["paymentRequestId", String]];
  for (const [field, normalize] of checks) {
    if (event[field] === undefined || event[field] === null || event[field] === "") continue;
    const expected = field === "amount" ? transaction.amount : transaction.metadata?.[field];
    if (expected === undefined || expected === null || expected === "" || normalize(event[field]) !== normalize(expected)) return `${field}_mismatch`;
  }
  return "";
}

function transactionStatus(paymentStatus) {
  if (paymentStatus === "confirmed") return "completed";
  if (["refunded", "reversed", "cancelled", "failed"].includes(paymentStatus)) return paymentStatus;
  return "pending";
}
