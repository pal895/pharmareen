import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const { appendActivity, createCatalogActivityEntry } =
  await import(pathToFileURL(path.join(root, "src/services/activityHistory.js")));

const expect = (condition, message) => {
  if (!condition) throw new Error(message);
};

const first = createCatalogActivityEntry({
  pharmacyId: "main",
  medicine: "Ibuprofen",
  changes: ["selling_price"],
  source: "manual",
  timestamp: "2026-07-28T09:00:00.000Z"
});
const second = createCatalogActivityEntry({
  pharmacyId: "main",
  medicine: "Ibuprofen",
  changes: ["cost_price"],
  source: "voice",
  timestamp: "2026-07-28T09:01:00.000Z"
});
let history = appendActivity([], first);
history = appendActivity(history, first);
expect(history.length === 1, "Refresh/replay must not duplicate an activity entry");
history = appendActivity(history, second);
expect(history.length === 2 && history[0].source === "voice", "Approved saves must remain newest-first and retain source");
expect(first.kenyaTime.includes("28/07/2026"), "Activity timestamp must render in Africa/Nairobi");
expect(first.outcome === "saved" && first.changedFields.join() === "selling_price", "Audit entry must retain outcome and changed field names");
expect(app.includes("recordCatalogActivity({") && app.includes("result.changes"), "Only the approved Catalog persistence boundary may create Catalog activity");
expect(!app.includes('addFeed("system", `${result.updated.name} updated in the Pharmacy Catalog.`)'), "Catalog saves must not append permanent feed messages");
expect(app.includes("isLegacyCatalogUpdateFeed") && app.includes("state.feed.filter"), "Legacy Catalog-update feed noise must be compacted without erasing unrelated messages");
expect(app.includes('type: "ActivityHubCard"') && app.includes("View Activity History"), "One compact Activity status and separate history must be available");
expect(app.includes('source: card.fields.voice_feedback ? "voice" : "manual"'), "Voice-approved edits must retain their audit source");
expect(!app.includes("recordCatalogActivity({ transcript"), "Voice search must not create Catalog-update activity");

console.log("Activity compaction verification passed: one status card, deterministic history, refresh dedupe, zero feed spam.");
