const COMPLETION_KEY = "ms20-main-app:stock-fix-completions";
const AUDIT_KEY = "ms20-main-app:stock-fix-audit";

export function executeStockCorrection({ action, catalog = [], online, queue, storage, persistCatalog, replaceCatalog }) {
  if (!action?.id) throw new Error("Stock fix action id is required.");
  if (completedIds(storage).has(action.id)) return { status: "completed", duplicate: true, action };

  if (!online || !storage) return savePending(action, queue);

  const nextCatalog = correctedCatalog(catalog, action.fields);
  if (!nextCatalog) return { status: "failed", message: "The saved medicine could not be found. Review the stock fix and try again." };

  try {
    if (persistCatalog(nextCatalog) === false) return savePending(action, queue);
    replaceCatalog(nextCatalog);
    recordCompletion(storage, action);
    if (queue.list().some((item) => item.id === action.id)) {
      queue.update(action.id, { status: "synced", syncedAt: new Date().toISOString() });
    }
    return {
      status: "completed",
      duplicate: false,
      action: { ...action, fields: { ...action.fields, mutation_status: "applied" } },
      catalog: nextCatalog
    };
  } catch {
    return savePending(action, queue);
  }
}

export function replayPendingStockCorrections(options) {
  const pending = options.queue.list().filter((item) => item.status === "pending" && item.type === "StockCorrectionCard");
  const results = [];
  for (const action of pending) {
    const result = executeStockCorrection({ ...options, action, catalog: options.getCatalog() });
    results.push(result);
  }
  return results;
}

function savePending(action, queue) {
  const pendingAction = {
    ...action,
    fields: { ...action.fields, mutation_status: "pending_automatic_sync" }
  };
  const result = queue.add(pendingAction);
  return { status: "pending", duplicate: result.duplicate, action: result.action || pendingAction };
}

function correctedCatalog(catalog, fields = {}) {
  const wanted = normalize(fields.medicine);
  const index = catalog.findIndex((item) => normalize(item.name || item.medicine) === wanted);
  if (index < 0) return null;
  const corrected = Number(fields.correct_stock);
  if (!Number.isInteger(corrected) || corrected < 0) return null;
  const next = catalog.map((item) => ({ ...item }));
  const medicine = { ...next[index], stockLeft: corrected };
  for (const legacyKey of ["stock", "current_stock", "quantity"]) {
    if (Object.hasOwn(medicine, legacyKey)) medicine[legacyKey] = corrected;
  }
  next[index] = medicine;
  return next;
}

function recordCompletion(storage, action) {
  const ids = completedIds(storage);
  ids.add(action.id);
  storage.setItem(COMPLETION_KEY, JSON.stringify([...ids]));
  const audit = readJson(storage, AUDIT_KEY, []);
  audit.push({
    id: action.id,
    medicine: action.fields.medicine,
    previousStock: action.fields.current_stock,
    correctedStock: action.fields.correct_stock,
    adjustment: action.fields.adjustment,
    reason: action.fields.reason,
    appliedAt: new Date().toISOString()
  });
  storage.setItem(AUDIT_KEY, JSON.stringify(audit));
}

function completedIds(storage) {
  return new Set(readJson(storage, COMPLETION_KEY, []));
}

function readJson(storage, key, fallback) {
  if (!storage) return fallback;
  try { return JSON.parse(storage.getItem(key) || JSON.stringify(fallback)); } catch { return fallback; }
}

function normalize(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}
