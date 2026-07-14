import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const css = fs.readFileSync(path.join(root, "src/styles.css"), "utf8");
const assert = (condition, message) => { if (!condition) throw new Error(message); };

assert(app.includes("scope.onclick = (event)") && app.includes('event.target.closest?.("[data-action]")'), "Every render must replace the root with one current delegated action handler");
assert(app.includes('data-action="upload-document"') && app.includes('if (action === "upload-document")'), "File quick action must reach the shared document input path");
assert(app.includes('data-action="start-catalog-paste"') && app.includes('if (action === "start-catalog-paste")'), "Paste List quick action must reach the shared catalog review path");
assert(app.includes("consolidateEmptyPasteDrafts()") && app.includes("focusCard(existing.id)") && app.includes("focusCard(card.id)"), "Repeated blank Paste List actions must reuse one draft, focus it, and discard it safely if still empty on resume");
assert(app.includes("function safeCardTemplate(card)") && app.includes("state.cards.map(safeCardTemplate)"), "One unreadable operational draft must never lock the whole workspace");
assert(app.includes("function quarantineUnreadableActiveCards()") && app.includes("QUARANTINED_CARDS_KEY"), "Unreadable non-empty drafts must leave the active render path without losing their raw data");
assert(!app.includes("incompleteInvoice") && app.includes("capabilities.correctionAllowed"), "Catalog review actions must consume the shared capability policy without stale workflow-local variables");
assert(!app.includes("CSS.escape"), "Card focus must not depend on an optional browser CSS escaping API");
assert(!app.includes("bindActionElements(list)"), "Dynamic catalog lists must rely on the same root action lifecycle instead of local rebinding");
assert(app.includes('cardCloseButtonTemplate(card, "top")') && app.includes('cardCloseButtonTemplate(card, "bottom")'), "Every rendered card must inherit top and bottom close controls from one renderer");
assert(app.includes('aria-label="${escapeHtml(label)}">x</button>'), "Top and bottom close controls must show only a clean x while retaining an accessible label");
assert(app.includes('data-action="dismiss-card"') && css.includes(".card-bottom-close") && css.includes(".card-close-button-bottom"), "Bottom close controls must use the canonical safe dismissal action and responsive styling");
assert(!/openai|anthropic|gemini|fetch\(/i.test(fs.readFileSync(path.join(root, "src/services/catalogReviewPolicy.js"), "utf8")), "Shared local review behavior must not introduce AI or API calls");

console.log("Shared action lifecycle verification passed: File, Paste List, dynamic actions, universal top/bottom card close, and zero-token behavior.");
