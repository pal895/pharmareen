import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const master = fs.readFileSync(path.join(root, "MS2.0_MASTER_LIVE_TEST_SEQUENCE.md"), "utf8");
const roadmapIds = [...master.matchAll(/^\| (\d+) \|/gm)].map((match) => Number(match[1]));
const traceabilityIds = [...master.matchAll(/^### MS2-LT-(\d{3}) —/gm)].map((match) => Number(match[1]));
const expectedCount = roadmapIds.length;

function unique(values) {
  return new Set(values).size === values.length;
}

if (!expectedCount || !unique(roadmapIds)) {
  throw new Error(`Roadmap must contain unique checkpoints; found ${roadmapIds.length}.`);
}
if (traceabilityIds.length !== expectedCount || !unique(traceabilityIds)) {
  throw new Error(`Traceability index must contain ${expectedCount} unique checkpoints; found ${traceabilityIds.length}.`);
}
if (roadmapIds.some((id, index) => id !== traceabilityIds[index])) {
  throw new Error("Traceability checkpoint IDs/order do not match the roadmap.");
}

const requiredFields = [
  "Checkpoint ID",
  "Name",
  "Category",
  "Current status",
  "Repository evidence",
  "Implementation commit(s)",
  "Primary implementation files/modules",
  "Owner live-test evidence",
  "PASS / PROTECTED confirmation",
  "Remaining implementation work",
  "Prerequisite checkpoints",
  "Dependent checkpoints",
];

const blocks = master.split(/^### MS2-LT-\d{3} —/m).slice(1);
for (const [index, block] of blocks.entries()) {
  for (const field of requiredFields) {
    if (!block.includes(`- **${field}:**`)) {
      throw new Error(`MS2-LT-${String(index + 1).padStart(3, "0")} is missing ${field}.`);
    }
  }
}

function expand(value) {
  if (/^(None|Implemented |All )/.test(value)) return [];
  const result = new Set();
  for (const token of value.split(",")) {
    const match = token.trim().match(/^(\d+)(?:[–-](\d+))?$/);
    if (!match) continue;
    const first = Number(match[1]);
    const last = Number(match[2] || match[1]);
    for (let id = first; id <= last; id += 1) result.add(id);
  }
  return [...result];
}

const roadmapRows = new Map();
const roadmapNames = new Set();
const allowedStates = new Set([
  "PASS / PROTECTED",
  "Implemented — awaiting owner live test",
  "Partial implementation",
  "Planned / approved",
  "External qualification",
  "Deprecated with repository evidence",
]);
for (const line of master.split(/\r?\n/)) {
  const cells = line.split("|").slice(1, -1).map((cell) => cell.trim());
  if (cells.length === 9 && /^\d+$/.test(cells[0])) {
    const id = Number(cells[0]);
    const normalizedName = cells[1].toLowerCase();
    if (roadmapNames.has(normalizedName)) throw new Error(`Duplicate checkpoint name: ${cells[1]}.`);
    if (!allowedStates.has(cells[4])) throw new Error(`MS2-LT-${id} has invalid state: ${cells[4]}.`);
    if (cells[4] === "PASS / PROTECTED" && (cells[5] === "Not started" || cells[6] !== "Yes")) {
      throw new Error(`MS2-LT-${id} cannot be protected without owner evidence and Protected=Yes.`);
    }
    roadmapNames.add(normalizedName);
    roadmapRows.set(id, { prerequisites: expand(cells[3]), state: cells[4] });
  }
}

const expectedDependents = new Map(roadmapIds.map((id) => [id, []]));
for (const [id, row] of roadmapRows) {
  for (const prerequisite of row.prerequisites) {
    if (!roadmapRows.has(prerequisite)) throw new Error(`MS2-LT-${id} references missing prerequisite ${prerequisite}.`);
    expectedDependents.get(prerequisite).push(id);
  }
}

const visiting = new Set();
const visited = new Set();
function visit(id) {
  if (visiting.has(id)) throw new Error(`Prerequisite cycle detected at MS2-LT-${id}.`);
  if (visited.has(id)) return;
  visiting.add(id);
  for (const prerequisite of roadmapRows.get(id).prerequisites) visit(prerequisite);
  visiting.delete(id);
  visited.add(id);
}
for (const id of roadmapIds) visit(id);

for (const [index, block] of blocks.entries()) {
  const id = index + 1;
  const dependentLine = block.match(/- \*\*Dependent checkpoints:\*\* (.+)/)?.[1]?.trim();
  const expected = expectedDependents.get(id).length
    ? expectedDependents.get(id).map((value) => `MS2-LT-${String(value).padStart(3, "0")}`).join(", ")
    : "None";
  if (dependentLine !== expected) throw new Error(`MS2-LT-${id} dependent metadata is stale.`);
}

const totalMatch = master.match(/- Total checkpoints: \*\*(\d+)\*\*/);
if (!totalMatch || Number(totalMatch[1]) !== expectedCount) throw new Error("Canonical checkpoint total is stale.");

console.log(`MASTER_TRACEABILITY_OK checkpoints=${expectedCount} metadata_fields=12 prerequisite_graph=acyclic`);
