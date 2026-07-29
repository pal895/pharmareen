import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const master = fs.readFileSync(path.join(root, "MS2.0_MASTER_LIVE_TEST_SEQUENCE.md"), "utf8");
const roadmap = fs.readFileSync(path.join(root, "docs", "engineering-memory", "launch-readiness-roadmap.md"), "utf8");

const rows = [];
for (const line of master.split(/\r?\n/)) {
  const cells = line.split("|").slice(1, -1).map((cell) => cell.trim());
  if (cells.length === 9 && /^\d+$/.test(cells[0])) {
    rows.push({ id: Number(cells[0]), status: cells[4] });
  }
}

const legacyNonProtected = rows.filter((row) => row.id <= 76 && row.status !== "PASS / PROTECTED");
const migrationIds = [...roadmap.matchAll(/^\| MS2-LT-(\d{3}) [^|]+\| (Launch Critical|Demo Mode|Continuous Improvement) \|/gm)]
  .map((match) => ({ id: Number(match[1]), classification: match[2] }));
assert.equal(migrationIds.length, legacyNonProtected.length, "Every non-protected legacy checkpoint must have one migration row.");
assert.equal(new Set(migrationIds.map((item) => item.id)).size, migrationIds.length, "Migration rows must be unique.");
assert.deepEqual(
  migrationIds.map((item) => item.id).sort((a, b) => a - b),
  legacyNonProtected.map((item) => item.id).sort((a, b) => a - b),
  "Legacy migration coverage must be exact.",
);

for (const id of [77, 78, 79, 80, 81, 82, 83, 84]) {
  assert.ok(rows.some((row) => row.id === id), `MS2-LT-${id} must be registered.`);
}

const allowedGateStatuses = new Set(["NOT STARTED", "IN PROGRESS", "BLOCKED", "READY FOR OWNER TEST", "PASS", "PROTECTED"]);
const gateBlock = roadmap.match(/## MS2\.0 Launch Gate([\s\S]*?)\n## Locked improvements/)?.[1] || "";
const gateRows = gateBlock.split(/\r?\n/).filter((line) => /^\| [^|-]/.test(line) && !line.startsWith("| Mandatory launch requirement"));
assert.ok(gateRows.length >= 22, "Launch Gate must cover every required launch domain.");
for (const line of gateRows) {
  const cells = line.split("|").slice(1, -1).map((cell) => cell.trim());
  assert.ok(allowedGateStatuses.has(cells[2]), `Invalid Launch Gate status: ${cells[2]}`);
}

assert.ok(roadmap.includes("Launch Gate status: BLOCKED"), "Launch Gate must state its truthful overall status.");
assert.ok(roadmap.includes("former automatic linear progression is historical") || roadmap.includes("former ascending checkpoint order is historical"), "Old linear order must be disabled.");
assert.ok(roadmap.includes("| Launch Critical | 24 |"), "Launch Critical count must remain synchronized.");
assert.ok(roadmap.includes("| Demo Mode | 2 |"), "Demo Mode count must remain synchronized.");
assert.ok(roadmap.includes("| Continuous Improvement | 15 |"), "Continuous Improvement count must remain synchronized.");
assert.ok(master.includes("former automatic linear progression is historical"), "Master must disable automatic linear progression.");
assert.ok(master.includes("Token policy: **ACTIVE**"), "Token policy must remain active.");

console.log("LAUNCH_ROADMAP_OK legacy_migrations=33 launch_critical=24 demo_mode=2 continuous_improvement=15 gate=BLOCKED");
