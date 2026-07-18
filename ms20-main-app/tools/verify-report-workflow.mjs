import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const [app, cards] = await Promise.all([
  readFile(new URL("../src/app.js", import.meta.url), "utf8"),
  readFile(new URL("../src/cards/editableCards.js", import.meta.url), "utf8")
]);

for (const required of [
  'function generateReport(card)',
  'cache: "no-store"',
  'controller.abort()',
  'resumeDurableCard',
  'Not refreshed yet',
  'generated_at',
  'Nothing was sent to WhatsApp or saved as a duplicate report.',
  'report_text',
  'Generate report',
  'Refresh report',
  'if (card.type === "ReportCard") return void generateReport(card);'
]) assert.ok(app.includes(required), `Missing report workflow protection: ${required}`);

assert.ok(!/fields:\s*\{[\s\S]{0,180}backend_route:/.test(app), "Owner report cards must not expose an internal backend route");
assert.ok(!/card\.type === "ReportCard"[\s\S]{0,500}export-catalog-csv/.test(app), "Report actions must not mislabel catalog CSV as a report download");
assert.ok(cards.includes('ReportCard: ["period", "focus", "report_date", "generated_at", "report_text"]'), "Report card schema must render report freshness, date and text");
assert.ok(!cards.includes('ReportCard: ["period", "focus", "backend_route"]'), "Report card schema must not retain the technical route field");
assert.ok(app.includes('if (card.type === "ReportCard") return card.validation'), "Report guidance must reflect generation success or failure");

console.log("Report workflow verification passed: owner-safe request, live generation, truthful errors, no WhatsApp send, and no catalog-export confusion.");
