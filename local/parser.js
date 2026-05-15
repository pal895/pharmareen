(function (root, factory) {
  const parser = factory();
  if (typeof module === "object" && module.exports) module.exports = parser;
  root.PharMareenOfflineParser = parser;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const NUMBER_WORDS = {
    zero: 0,
    one: 1,
    two: 2,
    three: 3,
    four: 4,
    five: 5,
    six: 6,
    seven: 7,
    eight: 8,
    nine: 9,
    ten: 10,
    eleven: 11,
    twelve: 12,
    thirteen: 13,
    fourteen: 14,
    fifteen: 15,
    sixteen: 16,
    seventeen: 17,
    eighteen: 18,
    nineteen: 19,
    twenty: 20,
    thirty: 30,
    forty: 40,
    fifty: 50,
    hundred: 100
  };

  const SHORTCUT_DRUGS = {
    p: "Panadol",
    pan: "Panadol",
    para: "Paracetamol",
    ors: "ORS",
    a: "Antacid",
    ant: "Antacid",
    i: "Insulin",
    ins: "Insulin"
  };

  function normalizeSpaces(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function normalizeNumberWords(value) {
    let text = ` ${String(value || "").toLowerCase()} `;
    const compounds = [
      ["one thousand eight hundred", "1800"],
      ["two thousand five hundred", "2500"],
      ["two thousand", "2000"],
      ["one thousand", "1000"]
    ];
    compounds.forEach(([phrase, number]) => {
      text = text.replace(new RegExp(`\\b${phrase}\\b`, "g"), number);
    });
    Object.entries(NUMBER_WORDS).forEach(([word, number]) => {
      text = text.replace(new RegExp(`\\b${word}\\b`, "g"), String(number));
    });
    return normalizeSpaces(text);
  }

  function numberFrom(value) {
    if (value === null || value === undefined) return null;
    const normalized = normalizeNumberWords(String(value));
    const match = normalized.match(/\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : null;
  }

  function titleCaseDrugName(value) {
    return normalizeSpaces(value)
      .replace(/^\+/, "")
      .replace(/\b(sold|sale|sell|restock|received|bought|add|stock|cost|paid|discount|bonus|supplier|expiry|cash|mpesa|m-pesa|card|credit)\b.*$/i, "")
      .replace(/\s+\d+(?:\.\d+)?\s*$/i, "")
      .replace(/\b(tablets?|tabs?|strips?|boxes?|box|bottles?|pieces?|units?)\b/gi, "")
      .trim()
      .split(" ")
      .filter(Boolean)
      .map(part => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
      .join(" ");
  }

  function splitCommands(rawText) {
    const pieces = String(rawText || "")
      .split(/[\n;]+/)
      .flatMap(line => line.split(/,(?!\s*(?:bonus|discount|paid|cost|supplier|expiry|budget)\b)/i))
      .map(normalizeSpaces)
      .filter(Boolean);
    return pieces.flatMap(splitFastSaleLine);
  }

  function splitFastSaleLine(line) {
    const text = normalizeSpaces(line);
    if (!text) return [];
    if (/\b(restock|received|bought|bonus|discount|cost|supplier|expiry|invoice|batch|barcode|no stock|report|summary|stock)\b/i.test(text)) {
      return [text];
    }
    const pattern = /([A-Za-z][A-Za-z' -]*?)\s+(?:x\s*)?(\d+(?:\.\d+)?)(?:\s+(tablets?|tabs?|strips?|boxes?|box|bottles?|pieces?|units?))?(?:\s+(cash|mpesa|m-pesa|card|credit))?(?=\s+[A-Za-z][A-Za-z' -]*?\s+(?:x\s*)?\d|$)/gi;
    const matches = Array.from(text.matchAll(pattern));
    if (matches.length <= 1) return [text];
    const commands = matches
      .map(match => normalizeSpaces(match[0]))
      .filter(Boolean);
    return commands.length ? commands : [text];
  }

  function matchFirst(text, patterns) {
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) return match;
    }
    return null;
  }

  function extractMoney(text, labels) {
    for (const label of labels) {
      const pattern = new RegExp(`\\b${label}\\s+(\\d+(?:\\.\\d+)?)`, "i");
      const match = text.match(pattern);
      if (match) return Number(match[1]);
    }
    return null;
  }

  function canonicalUnit(value) {
    const unit = String(value || "").toLowerCase();
    if (/^tabs?$|^tablets?$/.test(unit)) return "tablet";
    if (/^strips?$/.test(unit)) return "strip";
    if (unit === "box" || unit === "boxes") return "box";
    if (/^bottles?$/.test(unit)) return "bottle";
    if (/^pieces?$/.test(unit)) return "piece";
    if (/^units?$/.test(unit)) return "unit";
    return "";
  }

  function unitFactor(unit) {
    const canonical = canonicalUnit(unit);
    if (canonical === "box") return 100;
    if (canonical === "strip") return 10;
    return 1;
  }

  function extractUnit(text) {
    const match = String(text || "").match(/\b(tablets?|tabs?|strips?|boxes?|box|bottles?|pieces?|units?)\b/i);
    return match ? canonicalUnit(match[1]) : "";
  }

  function extractPayment(text) {
    const match = String(text || "").match(/\b(cash|mpesa|m-pesa|card|credit)\b/i);
    if (!match) return "";
    const value = match[1].toLowerCase();
    if (value === "mpesa" || value === "m-pesa") return "M-Pesa";
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function parseCommand(rawText) {
    const original = normalizeSpaces(rawText);
    const text = normalizeNumberWords(original);
    const lower = text.toLowerCase();
    const now = new Date().toISOString();
    const base = {
      id: `offline-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      timestamp: now,
      raw_text: original,
      command_text: original,
      action: "unknown",
      type: "unknown",
      drug_name: "",
      quantity: 0,
      bonus_quantity: 0,
      total_received_quantity: 0,
      buying_price: null,
      expected_total_cost: null,
      discount_amount: 0,
      actual_paid_amount: null,
      supplier: "",
      expiry_date: "",
      unit: extractUnit(original),
      base_quantity: 0,
      payment_method: extractPayment(original),
      invoice_number: "",
      batch_number: "",
      barcode: "",
      sync_status: "pending",
      retry_count: 0,
      last_error: ""
    };

    const bonusMatch = lower.match(/\bbonus\s+(\d+(?:\.\d+)?)\b|\bplus\s+(\d+(?:\.\d+)?)\s+bonus\b/i);
    const bonusQuantity = bonusMatch ? Number(bonusMatch[1] || bonusMatch[2]) : 0;
    const discountAmount = extractMoney(lower, ["discount", "saved"]);
    const expectedTotalCost = extractMoney(lower, ["budget", "ordered"]);
    let actualPaidAmount = extractMoney(lower, ["paid", "cost"]);
    if (actualPaidAmount === null) {
      const forMatch = lower.match(/\bfor\s+(\d+(?:\.\d+)?)\b/);
      if (forMatch) actualPaidAmount = Number(forMatch[1]);
    }
    if (actualPaidAmount === null && expectedTotalCost !== null && discountAmount !== null) {
      actualPaidAmount = expectedTotalCost - discountAmount;
    }
    const supplierMatch = original.match(/\bsupplier\s+(.+?)(?:\s+expiry\b|$)/i);
    const expiryMatch = original.match(/\bexpiry\s+(.+)$/i);

    const shortcutStock = lower.match(/^stock\s+([a-z]+)$/i);
    if (shortcutStock && SHORTCUT_DRUGS[shortcutStock[1]]) {
      return {
        ...base,
        action: "stock_check",
        type: "stock_check",
        drug_name: SHORTCUT_DRUGS[shortcutStock[1]]
      };
    }

    const shortcutRestock = lower.match(/^([a-z]+)\s*\+\s*(\d+(?:\.\d+)?)$/i);
    if (shortcutRestock && SHORTCUT_DRUGS[shortcutRestock[1]]) {
      const quantity = Number(shortcutRestock[2]);
      return {
        ...base,
        action: "restock",
        type: "restock",
        drug_name: SHORTCUT_DRUGS[shortcutRestock[1]],
        quantity,
        total_received_quantity: quantity,
        base_quantity: quantity * unitFactor(base.unit)
      };
    }

    const shortcutSale = lower.match(/^([a-z]+)\s*(?:x|\s)?\s*(\d+(?:\.\d+)?)$/i);
    if (shortcutSale && SHORTCUT_DRUGS[shortcutSale[1]]) {
      const quantity = Number(shortcutSale[2]);
      return {
        ...base,
        action: "sale",
        type: "sale",
        drug_name: SHORTCUT_DRUGS[shortcutSale[1]],
        quantity,
        base_quantity: quantity * unitFactor(base.unit)
      };
    }

    const plusRestock = matchFirst(text, [
      /^\+(.+?)\s+(\d+(?:\.\d+)?)(?:\s|$)/i,
      /^(.+?)\s+\+(\d+(?:\.\d+)?)(?:\s|$)/i
    ]);
    const wordRestock = matchFirst(text, [
      /^(?:add|received|restock|bought)\s+(.+?)\s+(\d+(?:\.\d+)?)(?:\s|$)/i,
      /^(.+?)\s+(?:restock|received|bought)\s+(\d+(?:\.\d+)?)(?:\s|$)/i
    ]);
    const isRestock = Boolean(plusRestock || wordRestock || lower.includes(" restock ") || lower.includes(" received ") || lower.includes(" bought "));
    if (isRestock) {
      const match = plusRestock || wordRestock;
      const drugName = match ? titleCaseDrugName(match[1]) : titleCaseDrugName(original);
      const quantity = match ? Number(match[2]) : numberFrom(original) || 0;
      const totalReceived = quantity + bonusQuantity;
      const baseQuantity = totalReceived * unitFactor(base.unit);
      return {
        ...base,
        action: "restock",
        type: bonusQuantity ? "bonus_restock" : discountAmount ? "discount_restock" : "restock",
        drug_name: drugName,
        quantity,
        bonus_quantity: bonusQuantity,
        total_received_quantity: totalReceived,
        base_quantity: baseQuantity,
        buying_price: actualPaidAmount !== null && totalReceived > 0 ? Number((actualPaidAmount / totalReceived).toFixed(2)) : null,
        expected_total_cost: expectedTotalCost,
        discount_amount: discountAmount || 0,
        actual_paid_amount: actualPaidAmount,
        supplier: supplierMatch ? normalizeSpaces(supplierMatch[1]) : "",
        expiry_date: expiryMatch ? normalizeSpaces(expiryMatch[1]) : ""
      };
    }

    const saleMatch = matchFirst(text, [
      /^(.+?)\s+(?:sold|sale)\s+(\d+(?:\.\d+)?)(?:\s|$)/i,
      /^(?:sold|sell)\s+(\d+(?:\.\d+)?)\s+(.+?)$/i,
      /^(?:sold|sell)\s+(.+?)\s+(\d+(?:\.\d+)?)(?:\s|$)/i,
      /^(.+?)\s+(\d+(?:\.\d+)?)(?:\s|$)/i
    ]);
    if (saleMatch) {
      let drugName = "";
      let quantity = 0;
      if (/^(?:sold|sell)/i.test(text) && /^\d/.test(saleMatch[1])) {
        quantity = Number(saleMatch[1]);
        drugName = titleCaseDrugName(saleMatch[2]);
      } else {
        drugName = titleCaseDrugName(saleMatch[1]);
        quantity = Number(saleMatch[2]);
      }
      if (drugName && quantity > 0) {
        return {
          ...base,
          action: "sale",
          type: "sale",
          drug_name: drugName,
          quantity,
          base_quantity: quantity * unitFactor(base.unit)
        };
      }
    }

    return base;
  }

  return { splitCommands, parseCommand, numberFrom, normalizeNumberWords };
});
