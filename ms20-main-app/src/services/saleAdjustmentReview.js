const ADJUSTMENT_TYPES = new Set(["refund", "return", "credit"]);
const STORAGE_KEY = "ms20-main-app:sale-adjustments";

export function completedSaleByReference(transactions = [], reference = {}) {
  const saleNumber = Number(reference.saleNumber);
  const transactionId = String(reference.transactionId || "");
  return [...transactions].reverse().find((item) =>
    item.kind === "sale" && item.status === "completed" && !item.reversalOf
    && ((transactionId && [item.id, item.permanentId].includes(transactionId))
      || (Number.isFinite(saleNumber) && item.saleNumber === saleNumber))
  ) || null;
}

export function saleReferenceFromReceipt(text = "") {
  const match = String(text).match(/(?:^|\n)Sale\s+(\d+)\b/i);
  return match ? { saleNumber: Number(match[1]) } : null;
}

export function saleDetailFields(transaction) {
  if (!transaction) return null;
  return {
    transaction_id: transaction.permanentId || transaction.id,
    sale_number: transaction.saleNumber,
    medicine: transaction.metadata?.medicine || "",
    form: transaction.metadata?.form || "",
    unit: transaction.metadata?.unit || "",
    quantity: Number(transaction.metadata?.quantity || 0),
    unit_price: Number(transaction.metadata?.sellingPrice || 0),
    total: Number(transaction.amount || transaction.metadata?.expectedTotal || 0),
    payment: transaction.paymentMethod || "",
    stock_after_sale: transaction.metadata?.stockLeft ?? transaction.metadata?.stockAfter ?? "",
    status: transaction.status
  };
}

export function createSaleAdjustmentReview(transaction, type, quantity = 1, existing = [], options = {}) {
  const normalizedType = String(type || "").toLowerCase();
  if (!transaction || !ADJUSTMENT_TYPES.has(normalizedType)) return null;
  const originalId = transaction.permanentId || transaction.id;
  const soldQuantity = Number(transaction.metadata?.quantity || 0);
  const alreadyAdjusted = existing
    .filter((item) => item.original_transaction_id === originalId && item.status === "confirmed")
    .reduce((sum, item) => sum + Number(item.adjustment_quantity || 0), 0);
  const remainingQuantity = Math.max(0, soldQuantity - alreadyAdjusted);
  if (!remainingQuantity) return null;
  const reviewQuantity = Math.min(Math.max(1, Number(quantity) || 1), remainingQuantity);
  const unitPrice = Number(transaction.metadata?.sellingPrice || 0);
  const restoreStock = normalizedType === "return"
    || (normalizedType === "refund" && options.restoreStock === true);
  const basePerSoldUnit = Number(transaction.metadata?.baseStockDeduction || soldQuantity) / soldQuantity;
  const financialAdjustment = unitPrice * reviewQuantity;
  const payment = String(transaction.paymentMethod || "");
  return {
    review_id: options.reviewId || `adjust-${originalId}-${normalizedType}-${Date.now()}`,
    adjustment_type: normalizedType,
    original_transaction_id: originalId,
    original_sale_number: transaction.saleNumber,
    medicine: transaction.metadata?.medicine || "",
    unit: transaction.metadata?.unit || "",
    sold_quantity: soldQuantity,
    previously_adjusted_quantity: alreadyAdjusted,
    remaining_quantity: remainingQuantity,
    adjustment_quantity: reviewQuantity,
    unit_price: unitPrice,
    financial_adjustment: financialAdjustment,
    restore_stock: restoreStock,
    stock_to_restore: restoreStock ? reviewQuantity : 0,
    base_stock_to_restore: restoreStock ? basePerSoldUnit * reviewQuantity : 0,
    payment_method: payment,
    payment_impact: normalizedType === "credit"
      ? `Create KES ${financialAdjustment} account credit; no ${payment || "payment"} refund`
      : `Reverse KES ${financialAdjustment} against ${payment || "original payment"}`,
    original_sale_status: transaction.status,
    review_status: "Review only — nothing has changed"
  };
}

export class SaleAdjustmentEngine {
  constructor({ storage = null, now = () => new Date(), staffIdentity = () => "Owner" } = {}) {
    this.storage = storage;
    this.now = now;
    this.staffIdentity = staffIdentity;
    this.memory = [];
  }

  list() {
    if (!this.storage) return [...this.memory];
    try { return JSON.parse(this.storage.getItem(STORAGE_KEY) || "[]"); } catch { return []; }
  }

  save(records) {
    if (this.storage) this.storage.setItem(STORAGE_KEY, JSON.stringify(records));
    else this.memory = [...records];
  }

  review(transaction, type, quantity = 1, options = {}) {
    return createSaleAdjustmentReview(transaction, type, quantity, this.list(), options);
  }

  confirm(review) {
    const records = this.list();
    const existing = records.find((item) => item.id === review.review_id);
    if (existing) return { created: false, duplicate: true, record: existing };
    const used = records.filter((item) =>
      item.original_transaction_id === review.original_transaction_id && item.status === "confirmed"
    ).reduce((sum, item) => sum + Number(item.adjustment_quantity || 0), 0);
    if (Number(review.adjustment_quantity) < 1 || used + Number(review.adjustment_quantity) > Number(review.sold_quantity)) {
      return { created: false, rejected: true, reason: "quantity_exceeds_remaining_sale_quantity" };
    }
    const createdAt = this.now().toISOString();
    const record = {
      ...review,
      id: review.review_id,
      adjustment_number: records.length + 1,
      status: "confirmed",
      created_at: createdAt,
      confirmed_at: createdAt,
      staff_identity: this.staffIdentity(),
      audit: [{ at: createdAt, by: this.staffIdentity(), event: "confirmed" }],
      sync_status: "pending"
    };
    records.push(record);
    this.save(records);
    return { created: true, duplicate: false, record };
  }
}

export { ADJUSTMENT_TYPES, STORAGE_KEY };
