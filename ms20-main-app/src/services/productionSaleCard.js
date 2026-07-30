export const PRODUCTION_SALE_CARD_FIELDS = Object.freeze([
  "medicine", "strength", "form", "unit", "quantity", "selling_price",
  "expected_total", "payment", "stock_before", "stock_after", "sale_status"
]);

export function prepareProductionSaleCard(card = {}, catalogMatch = {}) {
  if (card.type !== "SaleCard") return card;
  const match = catalogMatch.status === "matched" ? catalogMatch.matches?.[0] : null;
  const quantity = positiveNumber(card.fields?.quantity);
  const stockBefore = finiteNumber(match?.stockLeft ?? match?.stock ?? match?.current_stock);
  const forms = values(match?.forms ?? match?.form);
  const unitPrices = match?.unitPrices || match?.pricesByUnit || {};
  const unitConversions = match?.unitConversions || match?.stockUnitsPerSaleUnit || {};
  const units = uniqueValues([...(values(match?.units ?? match?.unit)), ...Object.keys(unitPrices), ...Object.keys(unitConversions)]);
  const batches = Array.isArray(match?.batches) ? match.batches : [];
  const selectedUnit = card.fields?.unit || (units.length === 1 ? units[0] : "");
  const baseStockUnit = match?.baseStockUnit || match?.base_stock_unit || values(match?.units ?? match?.unit)[0] || "";
  const packConversion = selectedUnit === baseStockUnit
    ? 1
    : positiveNumber(card.fields?.pack_conversion) ?? positiveNumber(unitConversions[selectedUnit]);
  const sellingPrice = positiveNumber(unitPrices[selectedUnit])
    ?? positiveNumber(card.fields?.selling_price)
    ?? (selectedUnit === baseStockUnit ? positiveNumber(match?.sellingPrice ?? match?.selling_price) : null);
  const stockDeduction = quantity === null || packConversion === null ? null : quantity * packConversion;
  card.fields = {
    ...card.fields,
    medicine: match?.name || card.fields?.medicine || "",
    strength: card.fields?.strength || match?.strength || "",
    form: card.fields?.form || (forms.length === 1 ? forms[0] : ""),
    unit: selectedUnit,
    base_stock_unit: baseStockUnit,
    pack_conversion: packConversion ?? card.fields?.pack_conversion ?? "",
    stock_deduction: stockDeduction ?? "",
    selling_price: sellingPrice ?? "",
    expected_total: quantity !== null && sellingPrice !== null ? quantity * sellingPrice : "",
    stock_before: stockBefore ?? "",
    stock_after: stockDeduction !== null && stockBefore !== null ? Math.max(0, stockBefore - stockDeduction) : "",
    sale_status: card.fields?.sale_status || "Review before recording",
    current_stock: stockBefore ?? "",
    cost_price: card.fields?.cost_price ?? match?.costPrice ?? match?.cost_price ?? "",
    supplier: card.fields?.supplier || match?.supplier || "",
    barcode: card.fields?.barcode || match?.barcode || "",
    batch: card.fields?.batch || batches[0]?.batch || match?.batch || "",
    expiry: card.fields?.expiry || batches[0]?.expiry || match?.expiry || "",
    aliases: card.fields?.aliases || values(match?.aliases).join(", "),
    note: card.fields?.note || ""
  };
  card.productionSaleCardVersion = "1.0";
  card.saleOptions = { forms, units };
  card.saleIssues = productionSaleIssues(card, catalogMatch);
  card.status = card.saleIssues.length ? "needs_correction" : "ready";
  card.validation = card.saleIssues.length
    ? issueMessage(card.saleIssues)
    : "Check the exact medicine, form, selling unit, quantity, unit price, total, payment and stock consequence. Nothing changes until Confirm.";
  return card;
}

export function productionSaleIssues(card = {}, catalogMatch = {}) {
  const fields = card.fields || {};
  const issues = [];
  if (catalogMatch.status !== "matched") issues.push("medicine_not_uniquely_matched");
  if (!String(fields.form || "").trim()) issues.push("form_unknown");
  if (!String(fields.unit || "").trim()) issues.push("selling_unit_unknown");
  const match = catalogMatch.status === "matched" ? catalogMatch.matches?.[0] : null;
  const forms = values(match?.forms ?? match?.form);
  const unitPrices = match?.unitPrices || match?.pricesByUnit || {};
  const unitConversions = match?.unitConversions || match?.stockUnitsPerSaleUnit || {};
  const units = uniqueValues([...(values(match?.units ?? match?.unit)), ...Object.keys(unitPrices), ...Object.keys(unitConversions)]);
  if (fields.form && forms.length && !forms.includes(fields.form)) issues.push("form_mismatch");
  if (fields.unit && units.length && !units.includes(fields.unit) && !COMMON_PACK_UNITS.has(fields.unit)) issues.push("selling_unit_mismatch");
  if (fields.strength && match?.strength && String(fields.strength).trim() !== String(match.strength).trim()) issues.push("strength_mismatch");
  if (positiveNumber(fields.quantity) === null) issues.push("quantity_invalid");
  if (positiveNumber(fields.selling_price) === null) issues.push("unit_price_unknown");
  if (fields.unit && fields.base_stock_unit && fields.unit !== fields.base_stock_unit && positiveNumber(fields.pack_conversion) === null) issues.push("pack_conversion_unknown");
  if (!["cash", "mpesa", "credit", "mixed"].includes(normalizePayment(fields.payment))) issues.push("payment_unknown");
  const before = finiteNumber(fields.stock_before);
  const deduction = positiveNumber(fields.stock_deduction);
  if (before !== null && deduction !== null && deduction > before) issues.push("insufficient_stock");
  return issues;
}

export function productionSaleSummary(fields = {}) {
  const identity = [fields.medicine || "Unknown medicine", fields.form, fields.unit].filter(Boolean).join(" · ");
  const payment = normalizePayment(fields.payment);
  return `${identity} · ${fields.quantity || "?"} × ${money(fields.selling_price)} = ${money(fields.expected_total)} · ${payment === "mpesa" ? "M-Pesa" : payment || "Unknown payment"}`;
}

export function saleFieldsFromTransaction(transaction = {}) {
  const metadata = transaction.metadata || {};
  return {
    medicine: metadata.medicine || "", strength: metadata.strength || "", form: metadata.form || "",
    unit: metadata.unit || "", quantity: metadata.quantity || "", selling_price: metadata.sellingPrice || "",
    expected_total: transaction.amount ?? metadata.expectedTotal ?? "", payment: transaction.paymentMethod || "",
    stock_before: metadata.stockBefore ?? "", stock_after: metadata.stockAfter ?? metadata.stockLeft ?? "",
    sale_status: transaction.status || "unknown"
  };
}

function issueMessage(issues) {
  const labels = {
    medicine_not_uniquely_matched: "choose one exact catalog medicine", form_unknown: "form is Unknown",
    selling_unit_unknown: "selling unit is Unknown", quantity_invalid: "enter a positive quantity",
    unit_price_unknown: "exact selling-unit price is Unknown", payment_unknown: "choose payment",
    pack_conversion_unknown: `enter how many base stock units are in one ${fieldsSafeUnit(issues)}`,
    insufficient_stock: "quantity exceeds available stock", form_mismatch: "form does not match the catalog medicine",
    selling_unit_mismatch: "selling unit does not match the catalog medicine",
    strength_mismatch: "strength does not match the catalog medicine"
  };
  return `${issues.map((issue) => labels[issue] || issue).join("; ")}. Confirm remains blocked until the sale is safe.`;
}

function fieldsSafeUnit() { return "requested pack"; }
const COMMON_PACK_UNITS = new Set(["tablet", "capsule", "sachet", "ampoule", "vial", "bottle", "tube", "strip", "blister", "packet", "pack", "box", "carton", "dose", "piece"]);

function normalizePayment(value) { return String(value || "").trim().toLowerCase().replace("-", ""); }
function values(value) {
  if (Array.isArray(value)) return value.map(String).map((entry) => entry.trim()).filter(Boolean);
  return String(value || "").split(",").map((entry) => entry.trim()).filter(Boolean);
}
function uniqueValues(valuesList) { return [...new Set(valuesList.map(String).map((entry) => entry.trim()).filter(Boolean))]; }
function finiteNumber(value) {
  if (value === "" || value === null || value === undefined) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}
function positiveNumber(value) { const number = finiteNumber(value); return number !== null && number > 0 ? number : null; }
function money(value) {
  const number = finiteNumber(value);
  return number === null ? "Unknown" : `KES ${number.toLocaleString("en-KE", { maximumFractionDigits: 2 })}`;
}
