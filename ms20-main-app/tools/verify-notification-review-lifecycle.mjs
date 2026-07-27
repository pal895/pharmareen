import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

const appSource = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const { createPasteImportCard, parseBulkMedicineList, prepareCatalogImport } =
  await import(pathToFileURL(path.join(root, "src/services/catalogOnboarding.js")));
const { SourceBrain } = await import(pathToFileURL(path.join(root, "src/services/brainAdapters.js")));
const { buildDeterministicNotifications, mergeNotifications, notificationToCard } =
  await import(pathToFileURL(path.join(root, "src/services/notificationCenter.js")));

const sourceBrain = new SourceBrain();
const catalog = Array.from({ length: 35 }, (_, index) => ({ id: `saved-${index}`, name: `Saved Medicine ${index}` }));
const draft = createPasteImportCard();

assert(draft.fields.entry_mode === "paste_input", "Paste List must begin as raw input, not a pending review");
assert(buildDeterministicNotifications({ catalog, pendingCards: [draft] }).length === 0, "Raw input must not create a review notification");
assert(catalog.length === 35, "Opening Paste List must not mutate the saved catalog");

draft.fields.items_text = "Notification Action Test 10 mg tablet 1";
assert(buildDeterministicNotifications({ catalog, pendingCards: [draft] }).length === 0, "Typing or speaking raw input must not create a review notification");

const parsed = parseBulkMedicineList(draft.fields.items_text, sourceBrain);
const { newItems } = prepareCatalogImport(parsed.items, catalog);
assert(newItems.length === 1, "Review list must deterministically parse one new medicine");
draft.fields.entry_mode = "review";
draft.fields.catalog_rows = JSON.stringify(newItems);

const generated = buildDeterministicNotifications({ catalog, pendingCards: [draft] });
assert(generated.length === 1, "The review-ready transition must create exactly one notification");
assert(generated[0].status === "unread", "The new review notification must be unread");

const repeated = mergeNotifications(generated, buildDeterministicNotifications({ catalog, pendingCards: [draft] }));
assert(repeated.length === 1, "Repeated refresh/navigation must not duplicate the notification");
const card = notificationToCard(repeated[0]);
assert(card.notificationAction?.targetCardId === draft.id, "Review import must target the same draft identifier");
assert(card.notificationAction?.label === "Review import", "The linked action must retain its compact label");
assert(!Object.hasOwn(card.fields, "action"), "The action must not render as a field-like value");
assert(catalog.length === 35, "Review creation and navigation must not save catalog data");

const afterCancel = mergeNotifications(repeated, buildDeterministicNotifications({ catalog, pendingCards: [] }));
assert(afterCancel.length === 0, "Cancelling the draft must clear its generated notification");
assert(catalog.length === 35, "Cancelling must preserve the catalog count");

const informational = notificationToCard({
  id: "information-only",
  category: "System",
  title: "Information",
  message: "No action required.",
  status: "unread"
});
assert(informational.notificationAction === null, "Informational notifications must not gain false action buttons");

assert(appSource.includes("function reviewPasteList(cardId)"), "Review list must retain one shared parsing boundary");
assert(appSource.includes("applyCatalogPasteReview(card, newItems"), "Review list must enter the shared review transition");
assert(appSource.includes("function openNotificationAction(cardId)"), "Review import must retain one shared action router");
assert(appSource.includes("focusCard(targetCardId)"), "Review import must focus the linked existing draft");
assert(appSource.includes('data-action="open-notification-action"'), "Linked notification actions must render as compact controls");

console.log(JSON.stringify({
  status: "PASS",
  lifecycle: "paste_input -> Review list -> review-ready draft + one unread notification",
  savedCatalogCount: catalog.length,
  duplicateNotifications: 0,
  zeroAi: true
}, null, 2));
