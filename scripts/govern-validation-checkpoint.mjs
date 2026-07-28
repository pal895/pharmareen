import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const unavailable = "Repository evidence not yet available.";
const contract = JSON.parse(fs.readFileSync(path.join(root, "scripts", "validation-contract.json"), "utf8"));
const masterPath = path.join(root, contract.master);
const commitsPath = path.join(root, "scripts", "checkpoint-implementation-commits.json");
const filesPath = path.join(root, "scripts", "checkpoint-primary-files.json");
const protectedBaselinePath = path.join(root, contract.protected_baseline);
const approvedImprovementsPath = path.join(root, contract.approved_improvements);
const [command, payloadPath] = process.argv.slice(2);

if (!["register", "protect", "reopen", "retire"].includes(command) || !payloadPath) {
  throw new Error("Usage: node scripts/govern-validation-checkpoint.mjs <register|protect|reopen|retire> <payload.json>");
}

const payload = JSON.parse(fs.readFileSync(path.resolve(payloadPath), "utf8"));
const marker = "<!-- TRACEABILITY_INDEX_START -->";
const fullMaster = fs.readFileSync(masterPath, "utf8");
let source = fullMaster.includes(marker) ? fullMaster.slice(0, fullMaster.indexOf(marker)).trimEnd() : fullMaster.trimEnd();
const commits = JSON.parse(fs.readFileSync(commitsPath, "utf8").replace(/^\uFEFF/, ""));
const primaryFiles = JSON.parse(fs.readFileSync(filesPath, "utf8").replace(/^\uFEFF/, ""));
const protectedBaseline = JSON.parse(fs.readFileSync(protectedBaselinePath, "utf8").replace(/^\uFEFF/, ""));
const approvedImprovements = JSON.parse(fs.readFileSync(approvedImprovementsPath, "utf8").replace(/^\uFEFF/, ""));

function tableRows(markdown) {
  const rows = [];
  for (const line of markdown.split(/\r?\n/)) {
    const cells = line.split("|").slice(1, -1).map((cell) => cell.trim());
    if (cells.length === 9 && /^\d+$/.test(cells[0])) rows.push({ id: Number(cells[0]), cells, line });
  }
  return rows;
}

function saveEvidenceMaps() {
  fs.writeFileSync(commitsPath, `${JSON.stringify(commits, null, 2)}\n`, "utf8");
  fs.writeFileSync(filesPath, `${JSON.stringify(primaryFiles, null, 2)}\n`, "utf8");
  fs.writeFileSync(protectedBaselinePath, `${JSON.stringify(protectedBaseline, null, 2)}\n`, "utf8");
  fs.writeFileSync(approvedImprovementsPath, `${JSON.stringify(approvedImprovements, null, 2)}\n`, "utf8");
}

if (command === "register") {
  if (payload.ownerVisible !== true) {
    console.log("VALIDATION_CONTRACT_NO_CHECKPOINT ownerVisible=false");
    process.exit(0);
  }
  if (!contract.categories.includes(payload.category)) throw new Error("Unknown validation category.");
  for (const field of ["name", "objective"]) {
    if (!payload[field]) throw new Error(`register requires ${field}.`);
  }
  const rows = tableRows(source);
  if (rows.some((row) => row.cells[1].toLowerCase() === payload.name.toLowerCase())) {
    throw new Error("A checkpoint with this name already exists.");
  }
  const id = Math.max(...rows.map((row) => row.id)) + 1;
  const status = payload.status || contract.default_owner_visible_status;
  const ownerValidation = payload.ownerValidation || "Awaiting owner validation";
  const protectedValue = status === "PASS / PROTECTED" ? "Yes" : "No";
  if (status === "PASS / PROTECTED" && !payload.ownerEvidence) {
    throw new Error("A new checkpoint cannot be protected without owner evidence.");
  }
  const row = `| ${id} | ${payload.name} | ${payload.objective} | ${payload.prerequisites || "None"} | ${status} | ${ownerValidation} | ${protectedValue} | ${payload.estimatedLiveTest || unavailable} | ${payload.repositoryEvidence || unavailable} |`;
  const heading = `## ${contract.categories.indexOf(payload.category) + 1}. ${payload.category}`;
  const start = source.indexOf(heading);
  if (start < 0) throw new Error("Category heading not found in master.");
  const nextHeading = source.indexOf("\n## ", start + heading.length);
  const end = nextHeading < 0 ? source.length : nextHeading;
  const section = source.slice(start, end).trimEnd();
  const insertion = section.lastIndexOf("\n| ");
  if (insertion < 0) throw new Error("Category table not found.");
  const lastRowEnd = section.indexOf("\n", insertion + 1);
  const position = lastRowEnd < 0 ? section.length : lastRowEnd;
  const updatedSection = `${section.slice(0, position)}\n${row}${section.slice(position)}`;
  source = `${source.slice(0, start)}${updatedSection}\n${source.slice(end).replace(/^\n+/, "")}`;
  commits[String(id)] = Array.isArray(payload.implementationCommits) ? payload.implementationCommits : [];
  primaryFiles[String(id)] = Array.isArray(payload.primaryImplementationFiles) ? payload.primaryImplementationFiles : [];
  approvedImprovements.improvements.push({
    approval_id: payload.approvalId || `APPROVED-MS2-LT-${String(id).padStart(3, "0")}`,
    owner_visible: true,
    checkpoint_id: `MS2-LT-${String(id).padStart(3, "0")}`,
    name: payload.name,
    disposition: "tracked",
  });
  if (status === "PASS / PROTECTED") {
    protectedBaseline.protected_checkpoint_ids.push(`MS2-LT-${String(id).padStart(3, "0")}`);
  }
  console.log(`VALIDATION_CHECKPOINT_REGISTERED MS2-LT-${String(id).padStart(3, "0")}`);
}

if (command === "protect") {
  if (!payload.id || !payload.ownerEvidence) throw new Error("protect requires id and ownerEvidence.");
  const row = tableRows(source).find((candidate) => candidate.id === Number(payload.id));
  if (!row) throw new Error("Checkpoint not found.");
  row.cells[4] = "PASS / PROTECTED";
  row.cells[5] = payload.ownerEvidence;
  row.cells[6] = "Yes";
  if (payload.repositoryEvidence) row.cells[8] = `${row.cells[8]}; ${payload.repositoryEvidence}`;
  source = source.replace(row.line, `| ${row.cells.join(" | ")} |`);
  const stableId = `MS2-LT-${String(row.id).padStart(3, "0")}`;
  if (!protectedBaseline.protected_checkpoint_ids.includes(stableId)) {
    protectedBaseline.protected_checkpoint_ids.push(stableId);
  }
  const current = source.match(/The only current open checkpoint is \*\*#(\d+) ([^*]+)\*\*\./);
  if (current && Number(current[1]) === row.id) {
    if (!payload.nextCheckpointId) throw new Error("Protecting the current checkpoint requires nextCheckpointId.");
    const next = tableRows(source).find((candidate) => candidate.id === Number(payload.nextCheckpointId));
    if (!next) throw new Error("Next checkpoint not found.");
    source = source.replace(current[0], `The only current open checkpoint is **#${next.id} ${next.cells[1]}**.`);
  }
  console.log(`VALIDATION_CHECKPOINT_PROTECTED MS2-LT-${String(row.id).padStart(3, "0")}`);
}

if (command === "retire") {
  if (!payload.id || !payload.reason) throw new Error("retire requires id and reason.");
  const row = tableRows(source).find((candidate) => candidate.id === Number(payload.id));
  if (!row) throw new Error("Checkpoint not found.");
  if (payload.replacementId && !tableRows(source).some((candidate) => candidate.id === Number(payload.replacementId))) {
    throw new Error("Replacement checkpoint not found.");
  }
  const prior = row.cells[4];
  row.cells[4] = "Deprecated with repository evidence";
  row.cells[5] = `Historical status ${prior}; ${payload.reason}`;
  row.cells[6] = "No";
  row.cells[8] = `${row.cells[8]}; Lifecycle: ${payload.reason}${payload.replacementId ? `; Replacement MS2-LT-${String(payload.replacementId).padStart(3, "0")}` : ""}`;
  source = source.replace(row.line, `| ${row.cells.join(" | ")} |`);
  console.log(`VALIDATION_CHECKPOINT_RETIRED MS2-LT-${String(row.id).padStart(3, "0")}`);
}

if (command === "reopen") {
  if (!payload.id || !payload.reason || !payload.repositoryEvidence) {
    throw new Error("reopen requires id, reason and repositoryEvidence.");
  }
  const row = tableRows(source).find((candidate) => candidate.id === Number(payload.id));
  if (!row) throw new Error("Checkpoint not found.");
  if (row.cells[4] !== "PASS / PROTECTED") throw new Error("Only a protected checkpoint can be reopened.");
  row.cells[4] = "Implemented — awaiting owner live test";
  row.cells[5] = `Historical status PASS / PROTECTED; Reopened pending owner validation: ${payload.reason}`;
  row.cells[6] = "No";
  row.cells[8] = `${row.cells[8]}; Reopened: ${payload.reason}; ${payload.repositoryEvidence}`;
  source = source.replace(row.line, `| ${row.cells.join(" | ")} |`);
  console.log(`VALIDATION_CHECKPOINT_REOPENED MS2-LT-${String(row.id).padStart(3, "0")}`);
}

fs.writeFileSync(masterPath, `${source}\n`, "utf8");
saveEvidenceMaps();
await import("./sync-validation-contract.mjs");
