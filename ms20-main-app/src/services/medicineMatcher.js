const FORM_VARIANTS = new Map([
  ["sirup", "syrup"], ["syrups", "syrup"], ["tabs", "tablet"], ["tab", "tablet"],
  ["tablets", "tablet"], ["caps", "capsule"], ["cap", "capsule"], ["capsules", "capsule"],
  ["vials", "vial"], ["creams", "cream"], ["gels", "gel"], ["drops", "drop"],
  ["eyedrop", "eye drop"], ["eyedrops", "eye drop"], ["inhalers", "inhaler"]
]);

export function normalizeMedicineText(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/([a-z])0(?=[a-z])/g, "$1o")
    .replace(/([a-z])1(?=[a-z])/g, "$1i")
    .replace(/([a-z])5(?=[a-z])/g, "$1s")
    .replace(/([a-z])([0-9])/g, "$1 $2")
    .replace(/([0-9])([a-z%])/g, "$1 $2")
    .replace(/[^a-z0-9%]+/g, " ")
    .trim()
    .split(/\s+/)
    .map((token) => FORM_VARIANTS.get(token) || safeSingular(token))
    .join(" ");
}

export function rankMedicineMatches(query, medicines = [], { limit = 5 } = {}) {
  const wanted = normalizeMedicineText(query);
  if (!wanted) return [];
  return medicines
    .map((medicine) => scoreMedicine(wanted, medicine))
    .filter((entry) => entry.score >= 0.42)
    .sort((left, right) => right.score - left.score || left.name.localeCompare(right.name))
    .slice(0, limit);
}

export function matchMedicine(query, medicines = []) {
  const wanted = normalizeMedicineText(query);
  if (!wanted) return { status: "missing_name", confidence: 0, matches: [], ranked: [] };
  const ranked = rankMedicineMatches(wanted, medicines);
  if (!ranked.length) return { status: "not_in_catalog", confidence: 0.2, matches: [], ranked: [] };
  const top = ranked[0];
  const second = ranked[1];
  const closeAlternative = second && second.score >= 0.66 && top.score - second.score < 0.09;
  if (closeAlternative || top.score < 0.72) {
    return {
      status: "ambiguous",
      confidence: top.score,
      matches: ranked.filter((entry) => entry.score >= Math.max(0.55, top.score - 0.12)).map((entry) => entry.medicine),
      ranked,
      matchType: top.reason
    };
  }
  return {
    status: "matched",
    confidence: top.score,
    matches: [top.medicine],
    ranked,
    matchType: top.reason
  };
}

function scoreMedicine(wanted, medicine) {
  const labels = medicineLabels(medicine);
  let best = { score: 0, reason: "nearby" };
  for (const label of labels) {
    const result = scoreLabel(wanted, label);
    if (result.score > best.score) best = result;
  }
  return { ...best, medicine, name: String(medicine.name || medicine.medicine || "") };
}

function medicineLabels(medicine) {
  const name = medicine.name || medicine.medicine || "";
  const aliases = [...(medicine.aliases || []), ...(medicine.brandNames || []), ...(medicine.genericNames || [])];
  const forms = [medicine.form, ...(medicine.forms || []), medicine.unit, ...(medicine.units || [])].filter(Boolean);
  const strength = medicine.strength || "";
  return [...new Set([
    name, ...aliases,
    ...forms.map((form) => `${name} ${form}`),
    ...(strength ? [`${name} ${strength}`, ...forms.map((form) => `${name} ${strength} ${form}`)] : []),
    ...aliases.flatMap((alias) => forms.map((form) => `${alias} ${form}`))
  ].map(normalizeMedicineText).filter(Boolean))];
}

function scoreLabel(wanted, label) {
  if (wanted === label) return { score: 1, reason: "exact" };
  const compactWanted = wanted.replace(/\s/g, "");
  const compactLabel = label.replace(/\s/g, "");
  if (compactWanted === compactLabel) return { score: 0.99, reason: "normalized" };
  if (label.startsWith(wanted) && wanted.length >= 3) return { score: 0.93, reason: "prefix" };
  if (label.includes(wanted) && wanted.length >= 3) return { score: 0.9, reason: "partial" };
  if (compactLabel.includes(compactWanted) && compactWanted.length >= 4) return { score: 0.89, reason: "compact_partial" };

  const wantedTokens = wanted.split(" ");
  const labelTokens = label.split(" ");
  const tokenScores = wantedTokens.map((token) => Math.max(...labelTokens.map((candidate) => tokenSimilarity(token, candidate))));
  const coverage = tokenScores.reduce((sum, value) => sum + value, 0) / tokenScores.length;
  const strongTokens = tokenScores.filter((value) => value >= 0.74).length / tokenScores.length;
  const orderIndependentExact = wantedTokens.every((token) => labelTokens.includes(token));
  if (orderIndependentExact) return { score: 0.95, reason: "token_order" };
  const lengthBalance = Math.min(compactWanted.length, compactLabel.length) / Math.max(compactWanted.length, compactLabel.length);
  const score = coverage * 0.7 + strongTokens * 0.2 + lengthBalance * 0.1;
  return { score: Math.min(0.91, score), reason: score >= 0.72 ? "close_spelling" : "nearby" };
}

function tokenSimilarity(left, right) {
  if (left === right) return 1;
  const ocrLeft = normalizeOcrToken(left);
  const ocrRight = normalizeOcrToken(right);
  if (ocrLeft === ocrRight) return 0.94;
  if ((left.startsWith(right) || right.startsWith(left)) && Math.min(left.length, right.length) >= 3) return 0.9;
  const longest = Math.max(left.length, right.length);
  if (!longest) return 1;
  const distance = editDistance(left, right);
  const spelling = 1 - distance / longest;
  const phonetic = soundex(left) && soundex(left) === soundex(right) ? 0.82 : 0;
  return Math.max(spelling, phonetic);
}

function normalizeOcrToken(token) {
  if (!/[a-z]/.test(token)) return token;
  return token.replace(/0/g, "o").replace(/1/g, "i").replace(/5/g, "s");
}

function editDistance(left, right) {
  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let row = 1; row <= left.length; row += 1) {
    const current = [row];
    for (let column = 1; column <= right.length; column += 1) {
      const cost = left[row - 1] === right[column - 1] ? 0 : 1;
      current[column] = Math.min(current[column - 1] + 1, previous[column] + 1, previous[column - 1] + cost);
    }
    previous = current;
  }
  return previous[right.length];
}

function safeSingular(token) {
  if (token.length > 5 && token.endsWith("s") && !token.endsWith("ss")) return token.slice(0, -1);
  return token;
}

function soundex(value) {
  const clean = String(value || "").replace(/[^a-z]/g, "");
  if (!clean) return "";
  const groups = { b: 1, f: 1, p: 1, v: 1, c: 2, g: 2, j: 2, k: 2, q: 2, s: 2, x: 2, z: 2, d: 3, t: 3, l: 4, m: 5, n: 5, r: 6 };
  const digits = clean.slice(1).split("").map((letter) => groups[letter] || 0).filter((digit, index, all) => digit && digit !== all[index - 1]);
  return `${clean[0]}${digits.join("")}000`.slice(0, 4);
}
