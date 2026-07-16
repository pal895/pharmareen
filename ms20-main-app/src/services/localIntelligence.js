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
  const text = normalize(raw);
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
    const restockText = raw.replace(/restock/gi, "").trim();
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
        medicine: medicineMatch.matches?.[0]?.name || enteredMedicine,
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

  const sale = raw.match(/^(.+?)[\s-]*(\d+(?:\.\d+)?)(?:\s*)?(cash|mpesa|m-pesa|credit|mixed)$/i)
    || raw.match(/^(.+?)\s+(\d+(?:\.\d+)?)\s*$/i);
  if (sale) {
    const medicine = sale[1].trim();
    const quantity = Number(sale[2]);
    const payment = (sale[3] || "cash").replace("-", "").toLowerCase();
    const medicineMatch = matchMedicineName(medicine, catalog);
    return {
      kind: "sale",
      cardType: medicineMatch.status === "ambiguous" ? "MedicineMatchCard" : "SaleCard",
      aiRequired: false,
      confidence: medicineMatch.status === "matched" ? 0.96 : medicineMatch.confidence,
      fields: {
        medicine: medicineMatch.matches[0]?.name || medicine,
        quantity,
        payment,
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
    VoiceReviewCard: "Review voice",
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
  return "Local-first route. No AI token needed.";
}
import { matchCatalogMedicine } from "./brainAdapters.js";
import { normalizeMedicineReviewRow } from "./medicineFieldSchema.js";
