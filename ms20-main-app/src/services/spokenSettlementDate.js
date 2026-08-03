const MONTHS = Object.freeze({
  january: 1, february: 2, march: 3, april: 4, may: 5, june: 6,
  july: 7, august: 8, september: 9, october: 10, november: 11, december: 12
});

const DAYS = Object.freeze({
  first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6, seventh: 7,
  eighth: 8, ninth: 9, tenth: 10, eleventh: 11, twelfth: 12, thirteenth: 13,
  fourteenth: 14, fifteenth: 15, sixteenth: 16, seventeenth: 17, eighteenth: 18,
  nineteenth: 19, twentieth: 20, "twenty first": 21, "twenty second": 22,
  "twenty third": 23, "twenty fourth": 24, "twenty fifth": 25,
  "twenty sixth": 26, "twenty seventh": 27, "twenty eighth": 28,
  "twenty ninth": 29, thirtieth: 30, "thirty first": 31
});

export function normalizeSpokenSettlementDate(transcript, today = new Date()) {
  const clean = String(transcript || "").toLowerCase().replace(/[,./]/g, " ").replace(/\b(?:the|of|on)\b/g, " ").replace(/\s+/g, " ").trim();
  const iso = /\b(20\d{2})[- ](0?[1-9]|1[0-2])[- ](0?[1-9]|[12]\d|3[01])\b/.exec(clean);
  let parts = iso ? [Number(iso[1]), Number(iso[2]), Number(iso[3])] : naturalDateParts(clean);
  if (!parts) return { applied: false, value: "", feedback: "Say a full date, for example 10 August 2026." };
  const [year, month, day] = parts;
  const value = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  if (!isRealDate(year, month, day)) return { applied: false, value: "", feedback: "That date is not valid. Say a full future date." };
  if (value <= localISODate(today)) return { applied: false, value: "", feedback: "Settlement must be on a future date. Say a later date." };
  return { applied: true, value, feedback: `Settlement date ${value}. Review before adding stock.` };
}

function naturalDateParts(clean) {
  const monthEntry = Object.entries(MONTHS).find(([name]) => new RegExp(`\\b${name}\\b`).test(clean));
  if (!monthEntry) return null;
  const [monthName, month] = monthEntry;
  const yearMatch = /\b(20\d{2})\b/.exec(clean);
  const year = yearMatch ? Number(yearMatch[1]) : spokenYear(clean);
  if (!year) return null;
  const withoutYear = clean.replace(/\b20\d{2}\b/, "").replace(/\btwenty\s+twenty[ -]?six\b/, "");
  const digitDay = new RegExp(`(?:\\b(\\d{1,2})(?:st|nd|rd|th)?\\s+${monthName}\\b|\\b${monthName}\\s+(\\d{1,2})(?:st|nd|rd|th)?\\b)`).exec(withoutYear);
  const spokenDay = Object.entries(DAYS).find(([name]) => new RegExp(`\\b${name.replace(" ", "[ -]")}\\b`).test(withoutYear));
  const day = Number(digitDay?.[1] || digitDay?.[2] || spokenDay?.[1] || 0);
  return day ? [year, month, day] : null;
}

function spokenYear(clean) {
  return /\btwenty\s+twenty[ -]?six\b/.test(clean) ? 2026 : 0;
}

function isRealDate(year, month, day) {
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

function localISODate(date) {
  const year = date.getFullYear();
  return `${year}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
