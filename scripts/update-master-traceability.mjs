import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const masterPath = path.join(root, "MS2.0_MASTER_LIVE_TEST_SEQUENCE.md");
const startMarker = "<!-- TRACEABILITY_INDEX_START -->";
const endMarker = "<!-- TRACEABILITY_INDEX_END -->";
const unavailable = "Repository evidence not yet available.";
const commitEvidence = JSON.parse(
  fs.readFileSync(path.join(root, "scripts", "checkpoint-implementation-commits.json"), "utf8").replace(/^\uFEFF/, ""),
);

const primaryFiles = JSON.parse(
  fs.readFileSync(path.join(root, "scripts", "checkpoint-primary-files.json"), "utf8").replace(/^\uFEFF/, ""),
);

const markdown = fs.readFileSync(masterPath, "utf8");
let source = markdown.includes(startMarker)
  ? markdown.slice(0, markdown.indexOf(startMarker)).trimEnd()
  : markdown.trimEnd();

let section = "";
const rows = [];
for (const line of source.split(/\r?\n/)) {
  const sectionMatch = line.match(/^## ([1-8])\. (.+)$/);
  if (sectionMatch) section = sectionMatch[2].trim();
  const cells = line.split("|").slice(1, -1).map((cell) => cell.trim());
  if (cells.length === 9 && /^\d+$/.test(cells[0])) {
    rows.push({
      id: Number(cells[0]),
      name: cells[1],
      objective: cells[2],
      prerequisites: cells[3],
      status: cells[4],
      ownerValidation: cells[5],
      protectedValue: cells[6],
      evidence: cells[8],
      category: section,
    });
  }
}

if (!rows.length) throw new Error("No checkpoints found.");

const ids = new Set(rows.map((row) => row.id));
if (ids.size !== rows.length) throw new Error("Duplicate checkpoint IDs detected.");
const names = new Set(rows.map((row) => row.name.toLowerCase()));
if (names.size !== rows.length) throw new Error("Duplicate checkpoint names detected.");

const stateTotals = new Map();
for (const row of rows) stateTotals.set(row.status, (stateTotals.get(row.status) || 0) + 1);
source = source.replace(/- Total checkpoints: \*\*\d+\*\*/, `- Total checkpoints: **${rows.length}**`);
for (const [state, count] of stateTotals) {
  const escaped = state.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  source = source.replace(new RegExp(`- ${escaped}: \\*\\*\\d+\\*\\*`), `- ${state}: **${count}**`);
}

function expandedPrerequisites(value) {
  if (/^(None|Implemented |All )/.test(value)) return [];
  const output = new Set();
  for (const token of value.split(",")) {
    const match = token.trim().match(/^(\d+)(?:[–-](\d+))?$/);
    if (!match) continue;
    const first = Number(match[1]);
    const last = Number(match[2] || match[1]);
    for (let current = first; current <= last; current += 1) output.add(current);
  }
  return [...output];
}

const dependents = new Map(rows.map((row) => [row.id, []]));
for (const row of rows) {
  for (const prerequisite of expandedPrerequisites(row.prerequisites)) {
    if (dependents.has(prerequisite)) dependents.get(prerequisite).push(row.id);
  }
}

function commitsFor(row, files) {
  if (!files.length) return unavailable;
  const commits = commitEvidence[String(row.id)];
  if (!Array.isArray(commits) || !commits.length) return unavailable;
  const ignored = new Set(["checkpoint", "validation", "owner", "current", "shared", "future", "complete"]);
  const shortTechnicalTokens = new Set(["ai", "csv", "ocr", "pdf", "tce", "xlsx"]);
  const tokens = row.name
    .toLowerCase()
    .match(/[a-z0-9]+/g)
    ?.filter((token) => (token.length >= 5 || shortTechnicalTokens.has(token)) && !ignored.has(token)) || [];
  const matching = commits.filter((entry) => {
    const subject = entry.replace(/^[0-9a-f]+ /, "").toLowerCase();
    return tokens.some((token) => subject.includes(token));
  });
  return matching.length ? matching.slice(0, 5).join("; ") : unavailable;
}

function remainingWork(row) {
  if (row.status === "PASS / PROTECTED") return "None; preserve against regression.";
  if (row.status === "Implemented — awaiting owner live test") {
    return `Complete decisive owner live validation for: ${row.objective}`;
  }
  if (row.status === "Partial implementation") {
    return `Complete the unimplemented portion and owner-validate: ${row.objective}`;
  }
  if (row.status === "Planned / approved") {
    return `Implement and owner-validate: ${row.objective}`;
  }
  if (row.status === "External qualification") {
    return `Complete the externally gated qualification: ${row.objective}`;
  }
  return "None; retain only for evidence-backed historical compatibility.";
}

const blocks = rows.map((row) => {
  const files = (primaryFiles[row.id] || []).filter((file) => fs.existsSync(path.join(root, file)));
  const hasOwnerEvidence = row.status === "PASS / PROTECTED"
    || (
      /(owner|passed|fail)/i.test(row.ownerValidation)
      && !/(^not |automated|controlled fixtures|historical bridge|lack|pending)/i.test(row.ownerValidation)
    );
  const ownerEvidence = hasOwnerEvidence
    ? `${row.ownerValidation}; source: ${row.evidence}`
    : unavailable;
  const passConfirmation = row.status === "PASS / PROTECTED"
    ? `Confirmed — Owner validation: ${row.ownerValidation}; Protected: ${row.protectedValue}.`
    : "Not applicable.";
  const dependentIds = dependents.get(row.id);
  return [
    `### MS2-LT-${String(row.id).padStart(3, "0")} — ${row.name}`,
    "",
    `- **Checkpoint ID:** MS2-LT-${String(row.id).padStart(3, "0")}`,
    `- **Name:** ${row.name}`,
    `- **Category:** ${row.category}`,
    `- **Current status:** ${row.status}`,
    `- **Repository evidence:** ${row.evidence || unavailable}`,
    `- **Implementation commit(s):** ${commitsFor(row, files)}`,
    `- **Primary implementation files/modules:** ${files.length ? files.map((file) => `\`${file}\``).join("; ") : unavailable}`,
    `- **Owner live-test evidence:** ${ownerEvidence}`,
    `- **PASS / PROTECTED confirmation:** ${passConfirmation}`,
    `- **Remaining implementation work:** ${remainingWork(row)}`,
    `- **Prerequisite checkpoints:** ${row.prerequisites}`,
    `- **Dependent checkpoints:** ${dependentIds.length ? dependentIds.map((id) => `MS2-LT-${String(id).padStart(3, "0")}`).join(", ") : "None"}`,
  ].join("\n");
});

const appendix = [
  startMarker,
  "## Engineering traceability index",
  "",
  "This generated index is part of the canonical master. Run `node scripts/sync-validation-contract.mjs` after an evidence, status, prerequisite, dependency, implementation-file or checkpoint change. Commit this file and all synchronized Project Brain/Engineering Memory/Bridge references together.",
  "",
  ...blocks,
  endMarker,
  "",
].join("\n\n");

fs.writeFileSync(masterPath, `${source}\n\n${appendix.trimEnd()}\n`, "utf8");
