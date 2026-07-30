function normalize(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

export function matchMedicineName(name, catalog = []) {
  const result = matchCatalogMedicine(name, catalog);
  return result.status === "not_in_catalog"
    ? { ...result, status: "needs_pharmacy_catalog", confidence: 0.72 }
    : result;
}

export function resolveStockCheck(input, catalog = []) {
  const raw = String(input || "").trim();
  const medicineText = raw
    .replace(/^\s*(?:check|show|what(?:'s| is))?\s*(?:the\s+)?stock\s+(?:for\s+)?/i, "")
    .replace(/\s+(?:stock|stock left)\s*$/i, "")
    .trim();
  if (!/\bstock\b/i.test(raw) || !medicineText || medicineText === raw) return { status: "not_stock_check" };
  const medicineMatch = matchMedicineName(medicineText, catalog);
  if (medicineMatch.status !== "matched") return { status: medicineMatch.status, medicineText, medicineMatch };
  const medicine = medicineMatch.matches[0];
  return {
    status: "matched",
    medicine,
    medicineText,
    medicineMatch
  };
}

export function parseLocalCommand(input, catalog = []) {
  const raw = String(input || "").trim();
  const commandText = normalizeSpokenNumbers(raw);
  const text = normalize(commandText);
  if (!text) {
    return { kind: "empty", cardType: null, aiRequired: false, confidence: 0 };
  }

  if (text.startsWith("pharmacy:")) {
    return {
      kind: "onboarding",
      cardType: "OnboardingCard",
      aiRequired: false,
      confidence: 0.9,
      fields: parseOnboarding(raw)
    };
  }

  if (text.includes("invoice")) {
    return {
      kind: "invoice",
      cardType: "InvoiceCard",
      aiRequired: false,
      confidence: 0.78,
      fields: { supplier: "Supplier pending", total: "", payment: "credit" }
    };
  }

  if (text.includes("report")) {
    return {
      kind: "report",
      cardType: "ReportCard",
      aiRequired: false,
      confidence: 0.92,
      fields: { period: text.includes("week") ? "This week" : "Today" }
    };
  }

  if (text.includes("stock") && !text.includes("restock")) {
    return {
      kind: "stock_check",
      cardType: "ReportCard",
      aiRequired: false,
      confidence: 0.88,
      fields: { period: "Current stock", focus: raw.replace(/stock/gi, "").trim() || "All medicines" }
    };
  }

  if (text.includes("restock")) {
    const restockText = commandText.replace(/restock/gi, "").trim();
    const quantityMatch = /^(.*?)(?:\s+(\d+(?:\.\d+)?))?$/.exec(restockText);
    const enteredMedicine = String(quantityMatch?.[1] || restockText).trim();
    const enteredQuantity = quantityMatch?.[2] || "";
    const medicineMatch = matchMedicineName(enteredMedicine, catalog);
    const known = normalizeMedicineReviewRow(medicineMatch.matches?.[0] || {});
    return {
      kind: "restock",
      cardType: "RestockCard",
      aiRequired: false,
      confidence: medicineMatch.status === "matched" ? 0.94 : 0.72,
      fields: {
        medicine: medicineMatch.status === "insufficient_identity" ? "" : medicineMatch.matches?.[0]?.name || enteredMedicine,
        quantity: enteredQuantity,
        bonus_quantity: "",
        unit: known.unit || "",
        pack_size: known.pack_size || "",
        strength: known.strength || "",
        form: known.form || "",
        cost_price: known.cost_price ?? "",
        selling_price: known.selling_price ?? "",
        supplier: known.supplier || "",
        batch: known.batch || "",
        expiry: known.expiry || "",
        barcode: known.barcode || "",
        shelf: known.shelf || "",
        delivery_reference: "",
        note: ""
      },
      medicineMatch
    };
  }

  const sale = parseSaleFacts(commandText, catalog);
  if (sale) {
    const medicineMatch = sale.medicineMatch;
    return {
      kind: "sale",
      cardType: ["ambiguous", "insufficient_identity"].includes(medicineMatch.status) ? "MedicineMatchCard" : "SaleCard",
      aiRequired: false,
      confidence: medicineMatch.status === "matched" ? 0.96 : medicineMatch.confidence,
      fields: {
        medicine: medicineMatch.status === "insufficient_identity" ? "" : medicineMatch.matches[0]?.name || sale.medicine,
        quantity: sale.quantity,
        unit: sale.unit || "",
        payment: sale.payment,
        stockLeft: medicineMatch.matches[0]?.stockLeft ?? "Catalog sync needed"
      },
      medicineMatch
    };
  }

  return {
    kind: "needs_clarification",
    cardType: "MedicineMatchCard",
    aiRequired: false,
    confidence: 0.35,
    fields: {
      message: "Add medicine, quantity, and payment.",
      medicine: raw,
      quantity: "",
      payment: ""
    }
  };
}

export function parseSaleFacts(input, catalog = []) {
  const command = normalizeSpokenNumbers(String(input || "").trim()).trim();
  if (!command) return null;
  const paymentMatch = command.match(/(m[\s-]?pesa|cash|credit|mixed)\s*$/i);
  const payment = paymentMatch ? paymentMatch[1].replace(/[\s-]/g, "").toLowerCase() : "";
  let saleText = paymentMatch ? command.slice(0, paymentMatch.index).trim() : command;
  if (!saleText) return null;

  const unitMatch = saleText.match(new RegExp(`^(.*?)\\s+(\\d+(?:\\.\\d+)?)\\s+(${saleUnitPattern(catalog)})$`, "i"));
  if (unitMatch) {
    const medicine = unitMatch[1].trim();
    const medicineMatch = matchMedicineName(medicine, catalog);
    return {
      medicine,
      quantity: Number(unitMatch[2]),
      unit: normalizeSaleUnit(unitMatch[3]),
      payment: payment || "cash",
      medicineMatch,
      defaultedQuantity: false
    };
  }

  // Catalog-first prevents a numeric medicine identity from being mistaken for quantity.
  const wholeMatch = matchMedicineName(saleText, catalog);
  if (payment && wholeMatch.status === "matched" && hasExactCatalogIdentity(saleText, catalog)) {
    return { medicine: saleText, quantity: 1, payment, medicineMatch: wholeMatch, defaultedQuantity: true };
  }

  const quantityMatch = saleText.match(/^(.*?)(\d+(?:\.\d+)?)\s*$/);
  if (quantityMatch) {
    const medicine = quantityMatch[1].trim();
    const medicineMatch = matchMedicineName(medicine, catalog);
    if (medicine && (payment || /\s+\d/.test(saleText))) {
      return {
        medicine,
        quantity: Number(quantityMatch[2]),
        payment: payment || "cash",
        medicineMatch,
        defaultedQuantity: false
      };
    }
  }

  if (payment) {
    return {
      medicine: saleText,
      quantity: 1,
      payment,
      medicineMatch: wholeMatch,
      defaultedQuantity: true
    };
  }
  return null;
}

const SALE_UNIT_PATTERN = "tablets?|tabs?|capsules?|caps?|strips?|blisters?|packets?|packs?|box(?:es)?|bottles?|sachets?|tubes?|vials?|ampoules?|cartons?|pieces?|doses?";

function saleUnitPattern(catalog = []) {
  const configured = catalog.flatMap((medicine) => [
    ...(Array.isArray(medicine?.units) ? medicine.units : [medicine?.unit]),
    ...Object.keys(medicine?.unitConversions || medicine?.stockUnitsPerSaleUnit || {}),
    ...Object.keys(medicine?.unitPrices || medicine?.pricesByUnit || {})
  ]).map((unit) => String(unit || "").trim()).filter(Boolean);
  return [SALE_UNIT_PATTERN, ...new Set(configured.map(configuredUnitPattern))].join("|");
}

function escapeRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function configuredUnitPattern(value) {
  const unit = String(value || "").trim().toLowerCase();
  const singular = unit.endsWith("s") ? unit.slice(0, -1) : unit;
  if (/[^aeiou]y$/.test(singular)) return `${escapeRegex(singular)}|${escapeRegex(`${singular.slice(0, -1)}ies`)}`;
  if (/(s|x|z|ch|sh)$/.test(singular)) return `${escapeRegex(singular)}(?:es)?`;
  return `${escapeRegex(singular)}s?`;
}

function normalizeSaleUnit(value) {
  const unit = String(value || "").trim().toLowerCase();
  const aliases = { tab: "tablet", tabs: "tablet", cap: "capsule", caps: "capsule", boxes: "box" };
  if (aliases[unit]) return aliases[unit];
  return unit.endsWith("s") ? unit.slice(0, -1) : unit;
}

function hasExactCatalogIdentity(value, catalog) {
  const target = normalize(value).replace(/[^a-z0-9]+/g, " ").trim();
  return catalog.some((medicine) => [
    medicine?.name,
    ...(medicine?.aliases || []),
    ...(medicine?.brandNames || [])
  ].some((identity) => normalize(identity).replace(/[^a-z0-9]+/g, " ").trim() === target));
}

function normalizeSpokenNumbers(value) {
  const numbers = new Map([
    ["one", "1"], ["moja", "1"],
    ["two", "2"], ["mbili", "2"],
    ["three", "3"], ["tatu", "3"],
    ["four", "4"], ["nne", "4"],
    ["five", "5"], ["tano", "5"],
    ["six", "6"], ["sita", "6"],
    ["seven", "7"], ["saba", "7"],
    ["eight", "8"], ["nane", "8"],
    ["nine", "9"], ["tisa", "9"],
    ["ten", "10"], ["kumi", "10"],
    ["eleven", "11"], ["twelve", "12"]
  ]);
  return String(value || "").replace(/\b[a-z]+\b/gi, (word) => numbers.get(word.toLowerCase()) || word);
}

function parseOnboarding(raw) {
  const fields = {};
  raw.split(";").forEach((part) => {
    const [key, ...rest] = part.split(":");
    if (!key || rest.length === 0) return;
    const cleanKey = normalize(key).replace(/\s+/g, "_");
    fields[cleanKey] = rest.join(":").trim();
  });
  return fields;
}

export function buildCardFromParse(parse, sourceText) {
  return {
    id: `card-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    type: parse.cardType,
    title: titleForCard(parse.cardType),
    source: sourceText,
    confidence: parse.confidence,
    aiRequired: parse.aiRequired,
    status: parse.kind === "needs_clarification" ? "needs_correction" : "ready",
    fields: parse.fields || {},
    validation: validationFor(parse)
  };
}

function titleForCard(type) {
  const titles = {
    SaleCard: "Review sale",
    InvoiceCard: "Review invoice",
    RestockCard: "Review restock",
    OnboardingCard: "Review setup",
    StockCorrectionCard: "Review stock correction",
    ReportCard: "Review report",
    PhotoReviewCard: "Review photo",
    MedicineMatchCard: "Confirm medicine",
    VisualScanCard: "Review scan",
    SyncReviewCard: "Review sync"
  };
  return titles[type] || "Review card";
}

function validationFor(parse) {
  if (parse.kind === "needs_clarification") {
    return "Add quantity and payment, for example Panadol 2 cash.";
  }
  if (parse.medicineMatch?.status === "ambiguous") {
    return "More than one medicine could match. Ask the owner to choose.";
  }
  if (parse.medicineMatch?.status === "needs_pharmacy_catalog") {
    return "Medicine catalog sync needed before live stock writes.";
  }
  if (parse.medicineMatch?.status === "insufficient_identity") {
    return "Add the medicine name. A form such as syrup or tablet is not enough.";
  }
  return "Local-first route. No AI token needed.";
}
import { matchCatalogMedicine } from "./brainAdapters.js";
import { normalizeMedicineReviewRow } from "./medicineFieldSchema.js";
