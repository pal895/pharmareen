function clean(value) {
  return String(value ?? "").trim();
}

function numberOrBlank(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : "";
}

export function actionToOfflineEntry(action, pharmacy = {}) {
  const fields = action?.fields || {};
  const common = {
    id: clean(action?.id),
    action_id: clean(action?.id),
    pharmacy_id: clean(pharmacy.id || fields.pharmacy_id),
    source: "ms20_main_app",
    created_at: clean(action?.queuedAt),
    retry_count: Number(action?.retryCount || 0)
  };

  if (!common.id) throw new Error("This saved item has no safety ID.");
  if (action?.type === "SaleCard") {
    return {
      ...common,
      action: "sale",
      type: "sale",
      drug_name: clean(fields.medicine),
      quantity: numberOrBlank(fields.quantity),
      base_quantity: numberOrBlank(fields.stock_deduction),
      unit: clean(fields.unit),
      payment_method: clean(fields.payment || action?.transaction?.paymentMethod || "Cash")
    };
  }
  if (action?.type === "RestockCard") {
    return {
      ...common,
      action: "restock",
      type: "restock",
      drug_name: clean(fields.medicine),
      quantity: numberOrBlank(fields.quantity),
      unit: clean(fields.unit),
      actual_paid_amount: numberOrBlank(fields.cost_price),
      supplier: clean(fields.supplier),
      invoice_number: clean(fields.delivery_reference),
      batch_number: clean(fields.batch),
      expiry_date: clean(fields.expiry_month),
      barcode: clean(fields.barcode)
    };
  }
  throw new Error("This kind of saved item is not ready for safe sync yet.");
}

export class OfflineSyncGateway {
  constructor({ backendGateway, pharmacy = {} } = {}) {
    this.backendGateway = backendGateway;
    this.pharmacy = pharmacy;
  }

  async saveAction(action) {
    if (!this.backendGateway) throw new Error("The backend connection is missing.");
    const entry = actionToOfflineEntry(action, this.pharmacy);
    const response = await this.backendGateway.requestJson("/offline/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: { entries: [entry], sender: "ms20_main_app" },
      timeoutMs: 15000
    });
    if (!response.ok) throw new Error("The item was not sent. It is still waiting safely.");
    const data = response.data || {};
    const synced = Array.isArray(data.synced) ? data.synced.find((item) => item.id === action.id) : null;
    const failed = Array.isArray(data.failed) ? data.failed.find((item) => item.id === action.id) : null;
    const pending = Array.isArray(data.pending) ? data.pending.find((item) => item.id === action.id) : null;
    if (failed) throw new Error(clean(failed.error) || "The backend could not save this item.");
    if (pending) throw new Error(clean(pending.reason) || "The item is still waiting safely.");
    if (!synced) throw new Error("The backend did not confirm this item. It is still waiting safely.");
    return {
      saved: true,
      actionId: action.id,
      status: clean(synced.status) || "synced",
      message: clean(synced.result_summary || synced.reply) || "Saved to the pharmacy records."
    };
  }

  async testConnection(actionId) {
    const response = await this.backendGateway.requestJson("/api/ms20/sync/connection-test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: { action_id: actionId },
      timeoutMs: 15000
    });
    if (!response.ok) throw new Error("The safe test could not reach the backend.");
    const data = response.data || {};
    if (!["saved", "already_saved"].includes(data.status)) {
      throw new Error(clean(data.message) || "The safe test was not confirmed.");
    }
    return data;
  }
}
