const medicines = [
  "Amitriptyline",
  "Artemether Lumefantrine",
  "Ciprofloxacin",
  "Loratadine"
];
const pasted = [
  "Amitriptyline tablet 45",
  "Artemether Lumefantrine tablet 180",
  "Ciprofloxacin eye drops 250",
  "Loratadine syrup 160"
].join("\n");
const pasteCard = {
  id: "card-existing-paste-feedback",
  type: "CatalogImportCard",
  title: "Review medicine list",
  source: "Bulk paste",
  confidence: 0.65,
  status: "needs_correction",
  aiRequired: false,
  fields: { method: "bulk paste", entry_mode: "paste_input", items_text: pasted }
};
const catalog = medicines.map((name, index) => ({ id: `medicine-${index}`, name }));
const storage = new Map([
  ["ms20-main-app:onboarding-complete", "true"],
  ["ms20-main-app:pharmacy-catalog", JSON.stringify(catalog)],
  ["ms20-main-app:active-cards", JSON.stringify([pasteCard])]
]);
const localStorage = {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: (key) => storage.delete(key)
};
const root = {
  dataset: {},
  innerHTML: "",
  querySelector: () => null,
  querySelectorAll: () => [],
  onclick: null,
  addEventListener: () => {},
  contains: () => true
};
globalThis.localStorage = localStorage;
Object.defineProperty(globalThis, "navigator", { value: { onLine: true, userAgent: "node-existing-paste-feedback" }, configurable: true });
globalThis.Node = { TEXT_NODE: 3 };
globalThis.document = { querySelector: (selector) => selector === "#app" ? root : null, querySelectorAll: () => [] };
globalThis.window = {
  localStorage,
  location: { hostname: "127.0.0.1", protocol: "http:", pathname: "/", port: "5177" },
  addEventListener: () => {},
  setInterval: () => 0,
  speechSynthesis: { cancel: () => {} }
};

await import(`../src/app.js?existing-paste-feedback=${Date.now()}`);
root.onclick({ target: { closest: () => ({ dataset: { action: "open-chat", workspace: "operations" } }) } });
root.onclick({ target: { closest: () => ({ dataset: { action: "review-paste-list", cardId: pasteCard.id } }) } });

if (!root.innerHTML.includes('<p class="card-note">No new medicines found. Already in this pharmacy:')) {
  throw new Error("Existing-medicine Paste List feedback is not visible in the main card body");
}
if (!root.innerHTML.includes("Medicine list") || root.innerHTML.includes("items text")) {
  throw new Error("Paste List must use an owner-facing field label");
}
const savedCatalog = JSON.parse(storage.get("ms20-main-app:pharmacy-catalog"));
if (savedCatalog.length !== catalog.length) {
  throw new Error("Reviewing existing medicines must not create duplicate catalog records");
}
console.log("Existing Paste List feedback and duplicate prevention reproduction passed.");
