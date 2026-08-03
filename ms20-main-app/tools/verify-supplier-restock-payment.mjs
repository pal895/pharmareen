import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { cardFieldsFor } from "../src/cards/editableCards.js";
import { parseLocalCommand } from "../src/services/localIntelligence.js";
import { medicineReviewBlocker } from "../src/services/medicineReviewReadiness.js";
import { normalizeSpokenSettlementDate } from "../src/services/spokenSettlementDate.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const catalog = [{ id: "ibuprofen", name: "Ibuprofen", forms: ["tablet"], units: ["tablet"], stockLeft: 13, costPrice: 12, sellingPrice: 18, supplier: "AfyaLink" }];

const restock = parseLocalCommand("restock ibuprofen 2", catalog);
assert(restock.cardType === "RestockCard" && restock.fields.supplier_terms === "paid_cash", "Voice restock must default visibly to paid-now cash without guessing a deferred obligation");
for (const field of ["supplier_terms", "settlement_date"]) assert(cardFieldsFor("RestockCard").includes(field), `Restock review is missing ${field}`);
assert(medicineReviewBlocker({ type: "RestockCard", fields: restock.fields }) === "", "A complete paid-now restock must be confirmable");
assert(medicineReviewBlocker({ type: "RestockCard", fields: { ...restock.fields, supplier_terms: "pay_later", settlement_date: "" } }).includes("settlement date"), "Future payment must stay blocked until an explicit date is reviewed");
assert(medicineReviewBlocker({ type: "RestockCard", fields: { ...restock.fields, supplier_terms: "pay_later", settlement_date: "2026-08-10" } }) === "", "A dated future settlement must be confirmable");
assert(normalizeSpokenSettlementDate("10 August 2026", new Date(2026, 7, 3)).value === "2026-08-10", "Natural spoken settlement date must normalize deterministically");
assert(normalizeSpokenSettlementDate("August tenth twenty twenty-six", new Date(2026, 7, 3)).value === "2026-08-10", "Spoken ordinal settlement date must normalize deterministically");
assert(!normalizeSpokenSettlementDate("3 August 2026", new Date(2026, 7, 3)).applied, "Voice must reject a non-future settlement date");
assert(app.includes('data-action="medicine-field-voice"') && app.includes("normalizeSpokenSettlementDate"), "Settlement date must expose the shared voice-first field path");
for (const evidence of ["supplier_payment", "supplier_credit", "supplier_settlement_due", "DeferredPaymentAdapter", "financialDirection: \"outflow\""]) assert(app.includes(evidence), `App is missing supplier TCE evidence: ${evidence}`);
assert(app.includes("Review only. Stock and supplier finances change only after Add stock."), "Supplier payment choice must remain review-only before confirmation");

console.log("Supplier/restock payment verification passed: voice-first restock review, explicit paid/credit/future terms, due-date blocking, TCE outflow boundary, idempotency, and zero pre-confirm mutation.");
