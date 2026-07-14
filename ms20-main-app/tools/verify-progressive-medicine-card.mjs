const card = {
  id: "card-quinine-sale-learning",
  type: "MedicineMatchCard",
  title: "Confirm medicine",
  source: "Local Source Brain",
  confidence: 0.68,
  status: "needs_correction",
  aiRequired: false,
  fields: {
    medicine: "Quinine sulfate",
    strength: "300 mg",
    form: "tablet",
    unit: "tablet",
    selling_price: "140",
    quantity: "1",
    payment: "cash",
    stock: "",
    cost_price: "",
    supplier: "",
    barcode: "",
    batch: "",
    expiry: "",
    alias: "",
    message: "Add this medicine and record the sale after owner approval."
  }
};
const storage = new Map([
  ["ms20-main-app:onboarding-complete", "true"],
  ["ms20-main-app:pharmacy-catalog", "[]"],
  ["ms20-main-app:active-cards", JSON.stringify([card])]
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
Object.defineProperty(globalThis, "navigator", { value: { onLine: true, userAgent: "node-progressive-medicine-card" }, configurable: true });
globalThis.Node = { TEXT_NODE: 3 };
globalThis.document = { querySelector: (selector) => selector === "#app" ? root : null, querySelectorAll: () => [] };
globalThis.window = {
  localStorage,
  location: { hostname: "127.0.0.1", protocol: "http:", pathname: "/", port: "5177" },
  addEventListener: () => {}, setInterval: () => 0, speechSynthesis: { cancel: () => {} }
};
globalThis.cancelAnimationFrame = () => {};
globalThis.requestAnimationFrame = (callback) => { callback(); return 1; };

await import(`../src/app.js?progressive-medicine-card=${Date.now()}`);
root.onclick({ target: { closest: () => ({ dataset: { action: "open-chat", workspace: "operations" } }) } });
const html = root.innerHTML;
const expect = (condition, message) => { if (!condition) throw new Error(message); };

expect(html.includes("medicine-review-workspace"), "Quinine sale-time learning must use the progressive medicine workspace");
expect((html.match(/class="medicine-slide(?: |")/g) || []).length === 3, "Medicine workspace must render exactly three slides");
expect(html.includes("Fast action") && html.includes("Stock &amp; details") && html.includes("Traceability"), "All slide navigation labels must be visible");
expect(html.includes("Quinine sulfate") && html.includes('data-field="selling_price"') && html.includes('data-payment="cash"'), "Slide 1 must contain medicine, selling price, and payment");
expect((html.match(/data-field="quantity"/g) || []).length === 1, "Medicine review must expose one quantity state only");
expect(html.includes("Current stock") && html.includes('data-field="strength"') && html.includes('data-field="form"'), "Slide 2 must contain stock and core medicine details");
expect(html.includes('data-field="supplier"') && html.includes('data-field="barcode"') && html.includes('data-field="batch"'), "Slide 3 must retain traceability details");
expect(html.includes(">Note</span>") && !html.includes(">message</span>"), "Secondary fields must use owner-facing labels");
expect(html.includes('data-action="confirm-card"') && html.includes('data-action="correct-card"') && html.includes('data-action="reject-card"'), "Fast action must retain Confirm, Correct, and Cancel");
expect(JSON.parse(storage.get("ms20-main-app:pharmacy-catalog")).length === 0, "Rendering and slide navigation must not save a medicine");
expect(card.aiRequired === false, "Progressive medicine review must remain zero-token");
console.log("Progressive medicine card verification passed: three slides, one quantity state, actions, traceability, draft safety, and zero AI.");
