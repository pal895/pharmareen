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

const primaryFiles = {
  1: ["ms20-main-app/src/app.js", "ms20-main-app/src/routes/routeRegistry.js"],
  2: ["app/services/pharmacy_onboarding.py", "app/pharmacy_registry.py"],
  3: ["app/services/local_invoice_ocr.py", "app/services/medicine_onboarding.py"],
  4: ["ms20-main-app/src/services/catalogOnboarding.js"],
  5: ["ms20-main-app/src/services/catalogOnboarding.js"],
  6: ["ms20-main-app/src/services/catalogOnboarding.js"],
  7: ["ms20-main-app/src/data/barcodeTestFixtures.js", "ms20-main-app/src/services/medicineMatcher.js"],
  8: ["app/services/photo_intake.py", "ms20-main-app/src/services/visualPipeline.js"],
  9: ["app/services/photo_intake.py", "ms20-main-app/src/services/visualPipeline.js"],
  10: ["ms20-main-app/src/services/catalogWorkspace.js", "ms20-main-app/src/services/activityHistory.js"],
  11: ["ms20-main-app/src/cards/editableCards.js", "ms20-main-app/src/services/catalogReviewPolicy.js"],
  12: ["app/transcription.py", "ms20-main-app/src/app.js"],
  13: ["ms20-main-app/src/services/voiceViewportAnchor.js", "ms20-main-app/src/cards/editableCards.js"],
  14: ["app/intake.py", "ms20-main-app/src/services/transactionCompletionEngine.js"],
  15: ["app/intake.py", "app/services/image_restock.py"],
  16: ["ms20-main-app/src/services/localIntelligence.js", "app/intake.py"],
  17: ["ms20-main-app/src/services/stockCorrectionExecution.js", "ms20-main-app/src/services/stockCorrectionPolicy.js"],
  18: ["ms20-main-app/src/services/stockFixEvidencePipeline.js", "app/services/local_stock_fix_ocr.py"],
  19: ["app/intake.py", "ms20-main-app/src/services/transactionCompletionEngine.js"],
  20: ["app/services/offline_sync.py", "ms20-main-app/src/services/offlineQueue.js"],
  21: ["app/reports.py", "ms20-main-app/src/services/localIntelligence.js"],
  22: ["app/intake.py", "app/services/operational_intelligence.py"],
  23: ["app/services/operational_intelligence.py"],
  24: ["ms20-main-app/src/services/notificationCenter.js", "ms20-main-app/src/services/localIntelligence.js"],
  25: ["ms20-main-app/src/services/notificationCenter.js", "ms20-main-app/src/services/localIntelligence.js"],
  26: ["app/reports.py", "app/services/operational_intelligence.py"],
  30: ["ms20-main-app/src/services/notificationCenter.js", "app/services/operational_intelligence.py"],
  31: ["app/medicine_brain.py", "ms20-main-app/src/services/medicineMatcher.js"],
  32: ["app/services/medicine_catalog.py", "ms20-main-app/src/services/catalogWorkspace.js"],
  33: ["app/correction_learning.py", "app/services/pharmacy_alias_store.py"],
  34: ["app/services/operational_intelligence.py", "app/training_store.py"],
  35: ["app/services/medicine_onboarding.py", "ms20-main-app/src/services/brainAdapters.js"],
  36: ["app/services/operational_intelligence.py", "app/services/photo_intake.py"],
  37: ["app/ai_policy.py", "app/ai.py"],
  39: ["app/reports.py", "ms20-main-app/src/services/localIntelligence.js"],
  40: ["ms20-main-app/src/services/documentGenerator.js", "ms20-main-app/src/services/exportFormatMetadata.js"],
  41: ["ms20-main-app/src/services/excelInventory.js", "ms20-main-app/src/services/ooxmlPackage.js"],
  42: ["ms20-main-app/src/services/documentGenerator.js"],
  43: ["ms20-main-app/src/services/documentGenerator.js", "ms20-main-app/src/services/ooxmlPackage.js"],
  44: ["ms20-main-app/src/services/documentGenerator.js", "ms20-main-app/src/services/ooxmlPackage.js"],
  45: ["ms20-main-app/src/services/documentGenerator.js", "ms20-main-app/src/services/medicineFinder.js"],
  46: ["ms20-main-app/src/services/exportFormatMetadata.js", "ms20-main-app/src/app.js"],
  47: ["ms20-main-app/src/services/documentGenerator.js", "ms20-main-app/tools/verify-export-hub.mjs"],
  50: ["app/intake.py", "ms20-main-app/src/services/paymentAdapters.js"],
  51: ["ms20-main-app/src/services/transactionCompletionEngine.js"],
  52: ["ms20-main-app/src/services/transactionCompletionEngine.js", "ms20-main-app/src/services/paymentAdapters.js"],
  53: ["ms20-main-app/src/services/transactionCompletionEngine.js"],
  54: ["ms20-main-app/src/services/transactionCompletionEngine.js", "ms20-main-app/src/services/notificationCenter.js"],
  55: ["app/intake.py", "ms20-main-app/src/services/transactionCompletionEngine.js"],
  56: ["app/intake.py", "ms20-main-app/src/services/transactionCompletionEngine.js"],
  58: ["app/main.py", "ms20-main-app/src/services/liveBackendGateway.js"],
  59: ["app/sheets.py", "app/services/pharmacy_onboarding.py"],
  60: ["baileys-bridge.js", "app/whatsapp.py"],
  61: ["app/services/offline_sync.py", "offline_app/app.js"],
  62: ["app/routes/meta_webhook.py", "app/providers/meta_whatsapp.py"],
  63: ["local_whatsapp_bridge.js", "whatsapp-web-bridge.js"],
  65: ["app/pharmacy_registry.py", "app/actor_context.py"],
  66: ["ms20-main-app/src/services/activityHistory.js", "ms20-main-app/src/services/transactionCompletionEngine.js"],
  67: ["app/actor_context.py", "app/routes/admin.py"],
  70: ["app/main.py", "start.sh"],
  71: ["app/main.py", "app/reports.py"],
  72: ["ms20-main-app/tools/verify-consistency-gate.mjs", "ms20-main-app/tools/verify-architecture.mjs"],
  73: ["app/provisioning.py", "app/deployment.py"],
};

const markdown = fs.readFileSync(masterPath, "utf8");
const source = markdown.includes(startMarker)
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

if (rows.length !== 76) throw new Error(`Expected 76 checkpoints, found ${rows.length}.`);

const ids = new Set(rows.map((row) => row.id));
if (ids.size !== rows.length) throw new Error("Duplicate checkpoint IDs detected.");

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
  return matching.length ? matching.slice(0, 3).join("; ") : unavailable;
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
      /(owner|passed)/i.test(row.ownerValidation)
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
  "This generated index is part of the canonical master. Run `node scripts/update-master-traceability.mjs` after an evidence, status, prerequisite, dependency, implementation-file or checkpoint change. Commit this file and all directly affected Project Brain/Engineering Memory references together.",
  "",
  ...blocks,
  endMarker,
  "",
].join("\n\n");

fs.writeFileSync(masterPath, `${source}\n\n${appendix.trimEnd()}\n`, "utf8");
