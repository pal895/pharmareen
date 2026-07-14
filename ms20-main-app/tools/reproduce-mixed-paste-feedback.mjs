const pasteCard = {
  id: "card-mixed-paste-feedback",
  type: "CatalogImportCard",
  title: "Review medicine list",
  source: "Bulk paste",
  confidence: 0.65,
  status: "needs_correction",
  aiRequired: false,
  fields: {
    method: "bulk paste",
    entry_mode: "paste_input",
    items_text: "Amitriptyline tablet 45\nQuinine sulfate tablet 300 mg 140"
  }
};
const catalog = [{ id: "amitriptyline", name: "Amitriptyline", form: "tablet", selling_price: "45" }];
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
  dataset: {}, innerHTML: "", querySelector: () => null, querySelectorAll: () => [],
  onclick: null, addEventListener: () => {}, contains: () => true
};
globalThis.localStorage = localStorage;
Object.defineProperty(globalThis, "navigator", { value: { onLine: true, userAgent: "node-mixed-paste-feedback" }, configurable: true });
globalThis.Node = { TEXT_NODE: 3 };
globalThis.document = { querySelector: (selector) => selector === "#app" ? root : null, querySelectorAll: () => [] };
globalThis.window = {
  localStorage,
  location: { hostname: "127.0.0.1", protocol: "http:", pathname: "/", port: "5177" },
  addEventListener: () => {}, setInterval: () => 0, speechSynthesis: { cancel: () => {} }
};

await import(`../src/app.js?mixed-paste-feedback=${Date.now()}`);
root.onclick({ target: { closest: () => ({ dataset: { action: "open-chat", workspace: "operations" } }) } });
root.onclick({ target: { closest: () => ({ dataset: { action: "review-paste-list", cardId: pasteCard.id } }) } });

if (!root.innerHTML.includes('<p class="card-note">1 new medicine(s) ready for review. 1 existing medicine(s) were not added again: Amitriptyline.')) {
  throw new Error("Mixed Paste List partition feedback is not visible in the main card body");
}
if (!root.innerHTML.includes("Quinine Sulfate") || root.innerHTML.includes('data-field="name" value="Amitriptyline"')) {
  throw new Error("Mixed Paste List must review only the new medicine row");
}
if (JSON.parse(storage.get("ms20-main-app:pharmacy-catalog")).length !== 1) {
  throw new Error("Mixed Paste List review must not save or duplicate medicines before approval");
}
console.log("Mixed Paste List feedback, partitioning, and draft safety reproduction passed.");
