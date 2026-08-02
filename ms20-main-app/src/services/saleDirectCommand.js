const DIRECT_SALE_ACTIONS = new Set(["open", "return", "refund", "credit", "undo"]);

export function parseSaleDirectCommand(text = "") {
  const normalized = String(text).trim().toLowerCase().replace(/\s+/g, " ");
  const match = normalized.match(/^(open|return|refund|credit|undo) sale (\d+)$/);
  if (!match) return null;
  const action = match[1];
  const saleNumber = Number(match[2]);
  if (!DIRECT_SALE_ACTIONS.has(action) || !Number.isSafeInteger(saleNumber) || saleNumber < 1) return null;
  return { action, target: "number", saleNumber };
}

export { DIRECT_SALE_ACTIONS };
