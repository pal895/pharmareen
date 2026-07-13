import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const css = fs.readFileSync(path.join(root, "src/styles.css"), "utf8");
const {
  applyApprovedCatalogEdit,
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
assert(app.includes('class="show-me-action"') && app.indexOf('class="show-me-action"') < app.indexOf('function chatScreenTemplate'), "SHOW ME must be a top-level action outside Operations Chat");
assert(app.includes('data-action="open-catalog-medicine"'), "Catalog rows must open a Medicine Action Card");
assert(app.includes('data-action="approve-catalog-edit"') && app.includes('data-action="cancel-catalog-edit"'), "Medicine edits need approve and discard actions");
assert(css.includes("grid-template-columns: repeat(2") && css.includes(".catalog-edit-grid") && css.includes("grid-template-columns: 1fr"), "Desktop and mobile catalog editor layouts must be protected");

const draft = createCatalogEditDraft(original[0]);
draft.selling_price = "130";
const review = reviewCatalogEdit(original, "med-1", draft);
assert(review.valid && review.changes.includes("selling_price"), "Changed fields must be reviewed before approval");
assert(original[0].sellingPrice === "120", "Draft edits must not mutate persisted data");
const approved = applyApprovedCatalogEdit(original, "med-1", draft);
assert(approved.valid && approved.catalog.length === 2 && approved.updated.sellingPrice === "130", "Approved edit must update the existing medicine");
assert(JSON.parse(JSON.stringify(approved.catalog))[0].sellingPrice === "130", "Approved edit must survive persisted-data reload");
assert(original[0].sellingPrice === "120", "A cancelled/unapproved draft must leave stored data unchanged");

const collisionDraft = createCatalogEditDraft(original[0]);
collisionDraft.name = "Metformin";
const collision = reviewCatalogEdit(original, "med-1", collisionDraft);
assert(!collision.valid && collision.identityCollision, "Identity replacement must detect an existing catalog medicine");
const blocked = applyApprovedCatalogEdit(original, "med-1", collisionDraft);
assert(blocked.catalog.length === 2 && blocked.catalog[0].name === "Cefixime", "Blocked replacement must not merge or duplicate medicines");

console.log("Catalog workspace focused verification passed: SHOW ME, persisted loading, safe draft/approve/discard, refresh, duplicate protection, responsive zero-token editing.");
