import fs from "node:fs";
import { SourceBrain } from "../src/services/brainAdapters.js";
import { catalogItemsToText, parseDelimitedInventory } from "../src/services/catalogOnboarding.js";

const csv = fs.readFileSync(new URL("../fixtures/test-4-csv-import.csv", import.meta.url), "utf8");
const parsed = parseDelimitedInventory(csv, new SourceBrain());
const reviewCard = {
  id: "card-csv-render-repro",
  type: "CatalogImportCard",
  title: "Review medicine list",
  source: "test-4-csv-import.csv",
  confidence: 0.82,
  status: "needs_correction",
  aiRequired: false,
  fields: {
    method: "bulk paste",
    entry_mode: "review",
    items_text: catalogItemsToText(parsed.items),
    notes: "One medicine per line. Price can be the last number."
  }
};
const storage = new Map([
  ["ms20-main-app:onboarding-complete", "true"],
  ["ms20-main-app:pharmacy-catalog", JSON.stringify([{ id: "zinc", name: "Zinc" }])],
  ["ms20-main-app:active-cards", JSON.stringify([reviewCard])]
]);
const localStorage = { getItem: (key) => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, String(value)), removeItem: (key) => storage.delete(key) };
const root = { dataset: {}, innerHTML: "", querySelector: () => null, querySelectorAll: () => [], onclick: null, addEventListener: () => {}, contains: () => true };
globalThis.localStorage = localStorage;
Object.defineProperty(globalThis, "navigator", { value: { onLine: true, userAgent: "node-csv-render-regression" }, configurable: true });
globalThis.Node = { TEXT_NODE: 3 };
globalThis.document = { querySelector: (selector) => selector === "#app" ? root : null, querySelectorAll: () => [] };
globalThis.window = { localStorage, location: { hostname: "127.0.0.1", protocol: "http:", pathname: "/", port: "5177" }, addEventListener: () => {}, setInterval: () => 0, speechSynthesis: { cancel: () => {} } };

await import(`../src/app.js?csv-render=${Date.now()}`);
root.onclick({ target: { closest: () => ({ dataset: { action: "open-chat", workspace: "operations" } }) } });
if (!root.innerHTML.includes("Aspirin") || root.innerHTML.includes("Draft could not be displayed")) {
  throw new Error(`CSV review card failed to render: ${storage.get("ms20-main-app:quarantined-cards") || "rows missing"}`);
}
console.log("CSV review card render reproduction passed.");
