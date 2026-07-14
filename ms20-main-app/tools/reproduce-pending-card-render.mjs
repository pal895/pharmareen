const storage = new Map([
  ["ms20-main-app:onboarding-complete", "true"],
  ["ms20-main-app:pharmacy-catalog", JSON.stringify([{ id: "aspirin", name: "Aspirin" }])],
  ["ms20-main-app:active-cards", JSON.stringify(Array.from({ length: 4 }, (_, index) => ({
    id: `card-catalog-paste-repro-${index}`,
    type: "CatalogImportCard",
    title: "Review medicine list",
    source: "Bulk paste",
    confidence: 0.65,
    status: "needs_correction",
    aiRequired: false,
    fields: { method: "bulk paste", entry_mode: "paste_input", items_text: "", notes: "One medicine per line." }
  })))]
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
Object.defineProperty(globalThis, "navigator", { value: { onLine: true, userAgent: "node-render-regression" }, configurable: true });
globalThis.Node = { TEXT_NODE: 3 };
globalThis.CSS = { escape: (value) => value };
globalThis.document = {
  querySelector: (selector) => selector === "#app" ? root : null,
  querySelectorAll: () => []
};
globalThis.window = {
  localStorage,
  location: { hostname: "127.0.0.1", protocol: "http:", pathname: "/", port: "5177" },
  addEventListener: () => {},
  setInterval: () => 0,
  speechSynthesis: { cancel: () => {} }
};

await import("../src/app.js");
root.onclick({ target: { closest: () => ({ dataset: { action: "open-chat", workspace: "operations" } }) } });
if (!root.innerHTML.includes("Review medicine list") || !root.innerHTML.includes("Paste one medicine per line")) {
  throw new Error("A resumed Paste List card must render in the Operations workspace");
}
if (root.innerHTML.split("Review medicine list").length - 1 !== 1) {
  throw new Error("Repeated empty Paste List taps must resume as one safe draft");
}
console.log("Pending Paste List render reproduction passed.");
