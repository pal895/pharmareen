import { matchMedicine, normalizeMedicineText, rankMedicineMatches } from "../src/services/medicineMatcher.js";
import { PharmacyBrain, SourceBrain } from "../src/services/brainAdapters.js";
import { catalogWorkspaceItems } from "../src/services/catalogWorkspace.js";
import { matchMedicineName, parseLocalCommand, resolveStockCheck } from "../src/services/localIntelligence.js";

const assert = (condition, message) => { if (!condition) throw new Error(message); };
const catalog = [
  { id: "zinc", name: "Zinc", aliases: ["Zinc syrup"], forms: ["syrup"], units: ["bottle"], sellingPrice: 70 },
  { id: "cefixime-200", name: "Cefixime", strength: "200 mg", aliases: ["Fixime"], forms: ["tablet"] },
  { id: "cefixime-400", name: "Cefixime", strength: "400 mg", aliases: ["Fixime Forte"], forms: ["tablet"] },
  { id: "panadol", name: "Paracetamol", brandNames: ["Panadol"], aliases: ["PCM"], forms: ["tablet"] },
  { id: "amoxicillin", name: "Amoxicillin", aliases: ["Amox"], forms: ["capsule"] },
  { id: "artemether", name: "Artemether Lumefantrine", aliases: ["AL"], forms: ["tablet"] }
];

assert(matchMedicine("Zinc", catalog).status === "matched", "Exact canonical match failed");
assert(matchMedicine("  ZINC   ", catalog).matches[0].id === "zinc", "Case/whitespace normalization failed");
assert(matchMedicine("zinc sirup", catalog).matches[0].id === "zinc", "Multi-word form spelling variation failed");
assert(matchMedicine("pnadol", catalog).matches[0].id === "panadol", "Common brand misspelling failed");
assert(matchMedicine("amox", catalog).matches[0].id === "amoxicillin", "Partial/abbreviation match failed");
assert(matchMedicine("Fixime Forte", catalog).matches[0].id === "cefixime-400", "Alias resolution failed");
assert(matchMedicine("Panadol", catalog).matches[0].name === "Paracetamol", "Brand-to-generic resolution failed");
assert(matchMedicine("Lumefantrine Artemether", catalog).matches[0].id === "artemether", "Reversed word order failed");
assert(matchMedicine("am0xicillin", catalog).matches[0].id === "amoxicillin", "OCR-style character error failed");
assert(matchMedicine("Cefixime 400mg", catalog).matches[0].id === "cefixime-400", "Strength-aware ranking failed");
assert(matchMedicine("Cefixime", catalog).status === "ambiguous", "Different strengths must remain safely ambiguous");
const accentCatalog = [
  { id: "cefixime", name: "Cefixime", forms: ["tablet"] },
  { id: "zinc", name: "Zinc", forms: ["syrup"] }
];
assert(matchMedicine("suffix may", accentCatalog).matches[0].id === "cefixime", "Accent-shaped multi-word speech must match a close catalog medicine phonetically");
assert(matchMedicine("syrup", catalog).status === "insufficient_identity", "A generic form alone must never identify one medicine");
assert(matchMedicine("bottle", catalog).status === "insufficient_identity", "A generic unit alone must never identify one medicine");
assert(rankMedicineMatches("zinc sirup", catalog)[0].medicine.id === "zinc", "Ranked result must put intended medicine first");
assert(catalogWorkspaceItems(catalog, "zinc sirup")[0].id === "zinc", "Pharmacy Catalog must use shared matcher");

const pharmacy = new PharmacyBrain({ pharmacyId: "test", catalog });
assert(pharmacy.findMedicine("zinc sirup").matches[0].id === "zinc", "Pharmacy Brain must use shared matcher");
assert(resolveStockCheck("stock for zinc sirup", catalog).medicine.id === "zinc", "Operations Chat stock lookup must use shared matcher");
assert(parseLocalCommand("restock zinc sirup", catalog).medicineMatch.matches[0].id === "zinc", "Restock lookup must use shared matcher");
const genericRestock = parseLocalCommand("restock syrup 12", catalog);
assert(genericRestock.medicineMatch.status === "insufficient_identity" && genericRestock.fields.medicine === "", "A voice transcript missing the medicine name must create a blocked restock review");
assert(parseLocalCommand("zinc sirup 2 cash", catalog).medicineMatch.matches[0].id === "zinc", "Sales lookup must use shared matcher");
const spokenNumberSale = parseLocalCommand("zinc syrup one cash", catalog);
assert(spokenNumberSale.fields.quantity === 1 && spokenNumberSale.fields.payment === "cash", "Spoken number words must become editable sale quantities");
const spokenNumberRestock = parseLocalCommand("restock zinc syrup twelve", catalog);
assert(spokenNumberRestock.fields.quantity === "12", "Spoken number words must become editable restock quantities");
const genericSale = parseLocalCommand("syrup 12 cash", catalog);
assert(genericSale.cardType === "MedicineMatchCard" && genericSale.fields.medicine === "", "A generic-form sale must ask for medicine identity instead of selecting a catalog record");
assert(matchMedicineName("zinc sirup", catalog).matches[0].id === "zinc", "Speech-recognized text must be ready for shared local matching");

const source = new SourceBrain({ medicines: catalog });
assert(source.lookupMedicine("pnadol").matches[0].id === "panadol", "Onboarding/import Source Brain must use shared matcher");
assert(normalizeMedicineText("Eye-drops") === "eye drop", "Form and punctuation normalization failed");
assert(catalog.length === 6 && new Set(catalog.map((item) => item.id)).size === 6, "Recognition must not create or merge records");

console.log("Medicine matcher focused verification passed: centralized ranked local recognition across catalog, Source Brain, chat, onboarding/import, sales, restock and speech text; safe strength ambiguity; zero AI calls.");
