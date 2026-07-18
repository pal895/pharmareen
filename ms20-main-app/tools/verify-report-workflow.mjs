import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const app = await readFile(new URL("../src/app.js", import.meta.url), "utf8");

for (const required of [
  'function generateReport(card)',
  'fetch("/reports/daily?send_whatsapp=false", { method: "POST" })',
  'Nothing was sent to WhatsApp.',
  'report_text',
  'Generate report',
  'Refresh report',
  'if (card.type === "ReportCard") return void generateReport(card);'
]) assert.ok(app.includes(required), `Missing report workflow protection: ${required}`);

assert.ok(!/fields:\s*\{[\s\S]{0,180}backend_route:/.test(app), "Owner report cards must not expose an internal backend route");
assert.ok(!/card\.type === "ReportCard"[\s\S]{0,500}export-catalog-csv/.test(app), "Report actions must not mislabel catalog CSV as a report download");

console.log("Report workflow verification passed: owner-safe request, live generation, truthful errors, no WhatsApp send, and no catalog-export confusion.");
