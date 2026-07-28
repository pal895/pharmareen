import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const css = fs.readFileSync(path.join(root, "src/styles.css"), "utf8");
const {
  applyApprovedCatalogEdit,
  applyCatalogEditVoice,
  applyCatalogSearchVoice,
  catalogEditPresentation,
  catalogWorkspaceItems,
  createCatalogEditDraft,
  createCatalogWorkspaceCard,
  reviewCatalogEdit
} = await import(pathToFileURL(path.join(root, "src/services/catalogWorkspace.js")));

const assert = (condition, message) => { if (!condition) throw new Error(message); };
const original = [
  { id: "med-1", name: "Cefixime", forms: ["tablet"], sellingPrice: "120", stockLeft: "8", aliases: ["Fixime"] },
  { id: "med-2", name: "Metformin", forms: ["tablet"], sellingPrice: "15", stockLeft: "20" }
];
const card = createCatalogWorkspaceCard(original.length);
assert(card.aiRequired === false, "Catalog workspace must remain zero-token");
assert(catalogWorkspaceItems(original, "Cefimixe").length === 1, "Catalog search must recognize a safe common misspelling locally");
assert(catalogWorkspaceItems([{ id: "zinc", name: "Zinc", forms: ["syrup"], aliases: ["Zinc syrup"] }], "zinc sirup").length === 1, "Catalog search must use the shared multi-word medicine matcher");
const syrupCatalog = [
  { id: "zinc", name: "Zinc", forms: ["syrup"], aliases: ["Zinc syrup"] },
  { id: "loratadine", name: "Loratadine", forms: ["syrup"] }
];
assert(catalogWorkspaceItems(syrupCatalog, "zinc sirup").map((item) => item.id).join() === "zinc", "Multi-term catalog search must not include medicines matching only a generic form term");
assert(app.includes('class="icon-button header-catalog-action"') && app.includes('aria-label="Open Pharmacy Catalog"'), "The chat header must expose one compact accessible catalog action");
assert(app.includes("function navigateToCatalogWorkspace()"), "All catalog entry points must share one navigation controller");
assert((app.match(/navigateToCatalogWorkspace\(\)/g) || []).length >= 5, "Header, home, typed, voice, and card catalog entry points must use the shared controller");
assert(/if \(action === "open-catalog-card"\) \{\s*navigateToCatalogWorkspace\(\);\s*render\(\);\s*\}/.test(app), "Duplicate-result Open catalog must render the shared catalog route immediately");
assert((app.match(/showCatalogWorkspace\(\)/g) || []).length === 3, "Catalog workspace mutation must remain behind the shared controller except the post-save refresh");
assert(app.includes("function isCatalogNavigationIntent(text)"), "Typed and voice catalog navigation must use one shared intent guard");
assert(app.includes('["show me", "show catalog", "show my catalog", "open catalog", "pharmacy catalog"]'), "Natural catalog navigation phrases must be recognized locally and case-insensitively");
assert(app.indexOf("if (isCatalogNavigationIntent(trimmed))") < app.indexOf("if (looksLikeMedicineList(trimmed))"), "Catalog navigation must be handled before medicine/list parsing");
assert(app.includes('data-action="open-catalog-medicine"'), "Catalog rows must open a Medicine Action Card");
assert(app.includes('data-action="approve-catalog-edit"') && app.includes('data-action="cancel-catalog-edit"'), "Medicine edits need approve and discard actions");
assert(app.includes("function bindActionElements(scope)") && app.includes("scope.onclick = (event)") && app.includes('event.target.closest?.("[data-action]")'), "Every render must install one current delegated action handler");
assert(app.includes('catalogSearchTemplate(card, query, "top")') && app.includes('catalogSearchTemplate(card, query, "bottom")'), "Long catalog lists must expose the same search component above and below the results");
assert(app.includes('querySelectorAll("[data-catalog-search]")'), "Top and bottom catalog search controls must stay synchronized and interactive");
const spokenSearch = applyCatalogSearchVoice("  Cefixime  ");
assert(spokenSearch.applied && spokenSearch.query === "Cefixime", "Catalog voice search must normalize the shared transcript deterministically");
assert(catalogWorkspaceItems(original, spokenSearch.query).map((item) => item.id).join() === "med-1", "Catalog voice search must filter through the existing local catalog matcher");
const repeatedSearch = applyCatalogSearchVoice("Metformin");
assert(repeatedSearch.applied && catalogWorkspaceItems(original, repeatedSearch.query).map((item) => item.id).join() === "med-2", "Catalog voice search must remain accurate after repeated use");
assert(catalogWorkspaceItems(original, "").length === original.length, "Clearing Catalog voice search must restore the complete saved catalog");
assert(!applyCatalogSearchVoice("  ").applied, "Empty voice search must not replace the current query");
assert(app.includes('data-action="catalog-search-voice"') && app.includes("startCatalogSearchVoice"), "Both Catalog search positions must expose the shared Mic controller");
assert(app.includes("applyCatalogSearchVoice(transcript)") && app.includes("startVoiceCapture("), "Catalog Search Mic must reuse shared capture and deterministic local query processing");
assert(css.includes(".catalog-search-control"), "Catalog Search Mic must remain beside the search input");
assert(css.includes("grid-template-columns: repeat(2") && css.includes(".catalog-edit-grid") && css.includes("grid-template-columns: 1fr"), "Desktop and mobile catalog editor layouts must be protected");

const draft = createCatalogEditDraft(original[0]);
const unchangedReview = reviewCatalogEdit(original, "med-1", draft);
assert(catalogEditPresentation(unchangedReview).status === "Saved medicine", "An unchanged saved Medicine Action Card must not claim to be an unsaved draft");
draft.selling_price = "130";
const review = reviewCatalogEdit(original, "med-1", draft);
assert(review.valid && review.changes.includes("selling_price"), "Changed fields must be reviewed before approval");
assert(catalogEditPresentation(review).status === "Unsaved changes", "A changed Medicine Action Card must expose its unsaved state truthfully");
assert(original[0].sellingPrice === "120", "Draft edits must not mutate persisted data");
const approved = applyApprovedCatalogEdit(original, "med-1", draft);
assert(approved.valid && approved.catalog.length === 2 && approved.updated.sellingPrice === "130", "Approved edit must update the existing medicine");
assert(JSON.parse(JSON.stringify(approved.catalog))[0].sellingPrice === "130", "Approved edit must survive persisted-data reload");
assert(original[0].sellingPrice === "120", "A cancelled/unapproved draft must leave stored data unchanged");

const voiceSource = createCatalogEditDraft(original[0]);
const voiceStock = applyCatalogEditVoice(voiceSource, "five", "stock");
assert(voiceStock.applied && voiceStock.draft.stock === "5", "Focused Catalog voice editing must apply a spoken stock value");
assert(voiceSource.stock === "8", "Voice editing must not mutate the saved/source draft");
const explicitStock = applyCatalogEditVoice(voiceStock.draft, "current stock twenty two");
assert(explicitStock.applied && explicitStock.draft.stock === "22", "Catalog voice editing must detect an explicit field and spoken compound number");
const voicePrice = applyCatalogEditVoice(explicitStock.draft, "selling price 130");
assert(voicePrice.applied && voicePrice.draft.selling_price === "130", "Catalog voice editing must use the same draft path for commercial fields");
const rejectedVoice = applyCatalogEditVoice(voicePrice.draft, "many", "stock");
assert(!rejectedVoice.applied && rejectedVoice.draft.stock === "22", "Invalid numeric voice input must leave the draft unchanged");
assert(app.includes('data-action="catalog-edit-voice"') && app.includes("startCatalogEditVoice"), "Catalog Medicine Action Cards must expose the shared Mic controller");
assert(app.includes("startVoiceCapture(") && app.includes("selectCatalogVoiceField"), "Catalog voice editing must reuse shared capture and focused-field selection");

const collisionDraft = createCatalogEditDraft(original[0]);
collisionDraft.name = "Metformin";
const collision = reviewCatalogEdit(original, "med-1", collisionDraft);
assert(!collision.valid && collision.identityCollision, "Identity replacement must detect an existing catalog medicine");
assert(catalogEditPresentation(collision).status === "Needs attention", "An invalid Medicine Action Card must expose its blocked state truthfully");
const blocked = applyApprovedCatalogEdit(original, "med-1", collisionDraft);
assert(blocked.catalog.length === 2 && blocked.catalog[0].name === "Cefixime", "Blocked replacement must not merge or duplicate medicines");

console.log("Catalog workspace focused verification passed: SHOW ME, persisted loading, safe draft/approve/discard, refresh, duplicate protection, responsive zero-token editing.");
