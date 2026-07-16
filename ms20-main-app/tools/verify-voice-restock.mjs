import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseLocalCommand } from "../src/services/localIntelligence.js";
import { cardFieldsFor } from "../src/cards/editableCards.js";
import { medicineReviewBlocker } from "../src/services/medicineReviewReadiness.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const catalog = [{
  id: "zinc",
  name: "Zinc",
  strength: "20 mg",
  form: "syrup",
  unit: "bottle",
  pack_size: "100 ml",
  cost_price: 45,
  selling_price: 70,
  supplier: "Trusted Supplier",
  stockLeft: 8,
  batches: [{ batch: "ZN-1", expiry: "2028-10" }]
}];

const spoken = parseLocalCommand("restock zinc syrup", catalog);
assert(spoken.cardType === "RestockCard" && spoken.fields.medicine === "Zinc", "Recognized restock speech must retain the Restock card and canonical medicine");
assert(spoken.fields.quantity === "", "A missing spoken restock quantity must stay blank instead of defaulting or guessing");
assert(spoken.fields.unit === "bottle" && spoken.fields.cost_price === 45 && spoken.fields.selling_price === 70, "Known restock facts must reuse trusted catalog values");
assert(spoken.fields.batch === "ZN-1" && spoken.fields.expiry === "2028-10", "Known traceability values must reach the restock review");

const complete = parseLocalCommand("restock zinc syrup 12", catalog);
assert(complete.fields.quantity === "12" && complete.fields.medicine === "Zinc", "A spoken quantity must be separated from the medicine and remain editable");
assert(medicineReviewBlocker({ type: "RestockCard", fields: spoken.fields }).includes("stock quantity"), "Restock confirmation must stay blocked until stock quantity is supplied");
assert(medicineReviewBlocker({ type: "RestockCard", fields: complete.fields }) === "", "A known medicine, positive quantity, and unit must be ready for owner confirmation");

for (const field of ["medicine", "quantity", "bonus_quantity", "unit", "pack_size", "cost_price", "selling_price", "supplier", "batch", "expiry", "barcode", "shelf", "delivery_reference", "note"]) {
  assert(cardFieldsFor("RestockCard").includes(field), `Restock review is missing ${field}`);
}

assert(app.includes('Voice needs internet on this phone. You can type while offline.'), "Offline voice must explain the actual limitation");
assert(app.includes('I did not hear any words. Tap Mic and try again.'), "No-result voice attempts need a clear recovery");
assert(app.includes('card.type === "RestockCard"') && app.includes("card.fields.voice_transcript"), "Voice restock must preserve its workflow card and visible transcript");
assert(app.includes('card.type === "RestockCard" ? "Add stock" : "Confirm"'), "Restock approval must use simple action wording");
assert(app.includes('state.voice.starting ? "Wait" : state.voice.listening ? "Speak" : "Mic"') && app.includes("const voiceBusy = state.voice.starting || state.voice.listening"), "The compact Mic control must distinguish startup from ready-to-speak without overlapping Send");
assert(app.includes('state.voice.status = "Starting microphone… Please wait."') && app.includes('state.voice.status = "Speak now."'), "Voice must not tell the owner to speak before the browser audio stream is ready");
assert(app.includes("recognition.onaudiostart = markAudioReady") && app.includes("recognition.onstart = markAudioReady"), "The ready state must follow the browser's actual recognition/audio start event");
assert(app.includes("card.voiceSource = true") && app.includes("removeCardsByPredicate((item) => item.voiceSource === true)"), "A new voice result must replace an older voice draft instead of leaving a stale card visible");
assert(app.includes("if (card.voiceSource && card.fields?.review_feedback)"), "Every voice review must show exactly what was heard before the action fields");
assert(!/handleVoiceTranscript[\s\S]{0,900}canRecordInstantly/.test(app), "Voice commands must remain review-first instead of mutating immediately after recognition");
assert(!/openai|anthropic|gemini|fetch\(/i.test(fs.readFileSync(path.join(root, "src/services/localIntelligence.js"), "utf8")), "Voice restock parsing must remain local and zero-token");

console.log("Voice restock verification passed: honest offline/no-result recovery, canonical local matching, complete three-section review, blocked incomplete approval, bonus stock, and zero-token behavior.");
