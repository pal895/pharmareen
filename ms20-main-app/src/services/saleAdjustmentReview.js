const ADJUSTMENT_TYPES = new Set(["refund", "return", "credit"]);

export function completedSaleByReference(transactions = [], reference = {}) {
  const saleNumber = Number(reference.saleNumber);
  const transactionId = String(reference.transactionId || "");
  return [...transactions].reverse().find((item) =>
    item.kind === "sale"
    && item.status === "completed"
    && !item.reversalOf
    && (
      (transactionId && [item.id, item.permanentId].includes(transactionId))
      || (Number.isFinite(saleNumber) && item.saleNumber === saleNumber)
    )
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

export function createSaleAdjustmentReview(transaction, type, quantity = 1) {
  const normalizedType = String(type || "").toLowerCase();
  if (!transaction || !ADJUSTMENT_TYPES.has(normalizedType)) return null;
  const soldQuantity = Number(transaction.metadata?.quantity || 0);
  const reviewQuantity = Math.min(Math.max(1, Number(quantity) || 1), soldQuantity);
  const unitPrice = Number(transaction.metadata?.sellingPrice || 0);
  return {
    adjustment_type: normalizedType,
    original_transaction_id: transaction.permanentId || transaction.id,
    original_sale_number: transaction.saleNumber,
    medicine: transaction.metadata?.medicine || "",
    unit: transaction.metadata?.unit || "",
    sold_quantity: soldQuantity,
    adjustment_quantity: reviewQuantity,
    unit_price: unitPrice,
    financial_adjustment: unitPrice * reviewQuantity,
    stock_to_restore: normalizedType === "credit" ? 0 : reviewQuantity,
    original_sale_status: transaction.status,
    review_status: "Review only — nothing has changed"
  };
}

export { ADJUSTMENT_TYPES };
