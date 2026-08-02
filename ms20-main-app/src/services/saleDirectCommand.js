const DIRECT_SALE_ACTIONS = new Set(["open", "return", "refund", "credit", "undo"]);
const SPOKEN_NUMBERS = new Map([
  ["one", "1"], ["two", "2"], ["three", "3"], ["four", "4"], ["five", "5"],
  ["six", "6"], ["seven", "7"], ["eight", "8"], ["nine", "9"], ["ten", "10"]
]);

export function normalizeSaleDirectCommand(text = "") {
  const words = String(text).trim().toLowerCase().replace(/\s+/g, " ").split(" ");
  const normalized = words.map((word) => SPOKEN_NUMBERS.get(word) || word);
  if (normalized.length === 3 && normalized[0] === "open" && normalized[1] === "cell" && /^\d+$/.test(normalized[2])) {
    normalized[1] = "sale";
  }
  return normalized.join(" ");
}

export function parseSaleDirectCommand(text = "") {
  const normalized = normalizeSaleDirectCommand(text);
  const match = normalized.match(/^(?:(open|return|refund|credit|undo) )?sale (\d+)$/);
  if (!match) return null;
  const action = match[1] || "open";
  const saleNumber = Number(match[2]);
  if (!DIRECT_SALE_ACTIONS.has(action) || !Number.isSafeInteger(saleNumber) || saleNumber < 1) return null;
  return { action, target: "number", saleNumber };
}

export { DIRECT_SALE_ACTIONS };
