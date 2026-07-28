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

const healthyCatalog = [{ id: "cefixime", name: "Cefixime", stockLeft: 22 }];
const lowCatalog = [{ ...healthyCatalog[0], stockLeft: 5 }];
const lowerCatalog = [{ ...healthyCatalog[0], stockLeft: 4 }];
const lowGenerated = buildDeterministicNotifications({ catalog: lowCatalog, pendingCards: [] });
assert(lowGenerated.length === 1 && lowGenerated[0].id === "inventory-low-cefixime", "Low stock must project one deterministic alert");
const lowRepeated = mergeNotifications(lowGenerated, buildDeterministicNotifications({ catalog: lowCatalog, pendingCards: [] }));
assert(lowRepeated.length === 1, "Repeated low-stock refresh must not duplicate unread counts");
const readLow = [{ ...lowRepeated[0], status: "read" }];
assert(mergeNotifications(readLow, buildDeterministicNotifications({ catalog: lowCatalog }))[0].status === "read", "Unchanged low-stock refresh must preserve owner read state");
const changedLow = mergeNotifications(readLow, buildDeterministicNotifications({ catalog: lowerCatalog }));
assert(changedLow.length === 1 && changedLow[0].status === "unread" && changedLow[0].message.includes("4 left"), "A material stock change must refresh and re-alert the same deterministic notification");
assert(mergeNotifications(changedLow, buildDeterministicNotifications({ catalog: healthyCatalog })).length === 0, "Restoring healthy stock must remove the generated alert");
const outGenerated = buildDeterministicNotifications({ catalog: [{ ...healthyCatalog[0], stockLeft: 0 }] });
assert(outGenerated.length === 1 && outGenerated[0].id === "inventory-out-cefixime", "Out-of-stock must project one distinct deterministic alert");
assert(outGenerated[0].title === "Cefixime is out of stock" && outGenerated[0].message === "Prepare an order or correct stock if the count is wrong.", "Out-of-stock content must remain canonical");
assert(mergeNotifications(outGenerated, buildDeterministicNotifications({ catalog: [{ ...healthyCatalog[0], stockLeft: 0 }] })).length === 1, "Out-of-stock refresh must remain duplicate-safe");
assert(mergeNotifications(outGenerated, buildDeterministicNotifications({ catalog: healthyCatalog })).length === 0, "Restoring healthy stock must clear out-of-stock");

const expiryBaseline = [
  {
    id: "ibuprofen",
    name: "Ibuprofen",
    stockLeft: 27,
    batches: [{ batch: "IBU-200C", expiry: "2028-12" }]
  },
  ...Array.from({ length: 34 }, (_, index) => ({
    id: `healthy-${index}`,
    name: `Healthy Medicine ${index}`,
    stockLeft: 20
  }))
];
const expiryChanged = expiryBaseline.map((item) => item.id === "ibuprofen"
  ? { ...item, batches: [{ batch: "IBU-200C", expiry: "2026-06" }] }
  : item);
const expiryNow = new Date("2026-07-28T09:00:00.000Z");
const expiryGenerated = buildDeterministicNotifications({ catalog: expiryChanged, now: expiryNow });
assert(expiryChanged.length === 35, "Expiry-only editing must preserve all 35 medicines");
assert(expiryChanged[0].stockLeft === 27 && expiryChanged[0].batches[0].batch === "IBU-200C", "Expiry-only editing must preserve protected stock and batch");
assert(expiryGenerated.length === 1, "Changing only Ibuprofen expiry to 2026-06 must create exactly one alert");
assert(expiryGenerated[0].title === "Ibuprofen has expired", "Expiry alert title must remain canonical");
assert(expiryGenerated[0].message === "Batch IBU-200C expires at end of June 2026.", "Expiry alert note must retain the end-of-month rule");
assert(mergeNotifications(expiryGenerated, buildDeterministicNotifications({ catalog: expiryChanged, now: expiryNow })).length === 1, "Expiry refresh must not duplicate the alert");
assert(mergeNotifications(expiryGenerated, buildDeterministicNotifications({ catalog: expiryBaseline, now: expiryNow })).length === 0, "Restoring 2028-12 must remove the expiry alert and return Notifications to Quiet");

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
