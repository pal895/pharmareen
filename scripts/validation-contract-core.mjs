const allowedStates = new Set([
  "PASS / PROTECTED",
  "Implemented — awaiting owner live test",
  "Partial implementation",
  "Planned / approved",
  "External qualification",
  "Deprecated with repository evidence",
]);

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

export function validateMasterText(master, protectedBaseline = []) {
  const rows = [];
  for (const line of master.split(/\r?\n/)) {
    const cells = line.split("|").slice(1, -1).map((cell) => cell.trim());
    if (cells.length === 9 && /^\d+$/.test(cells[0])) {
      rows.push({
        id: Number(cells[0]),
        stableId: `MS2-LT-${String(cells[0]).padStart(3, "0")}`,
        name: cells[1],
        prerequisites: expand(cells[3]),
        status: cells[4],
        ownerEvidence: cells[5],
        protectedValue: cells[6],
        evidence: cells[8],
      });
    }
  }
  if (!rows.length) throw new Error("No checkpoints found.");
  if (new Set(rows.map((row) => row.id)).size !== rows.length) throw new Error("Duplicate checkpoint ID.");
  if (new Set(rows.map((row) => row.name.toLowerCase())).size !== rows.length) throw new Error("Duplicate checkpoint name.");

  const byId = new Map(rows.map((row) => [row.id, row]));
  for (const row of rows) {
    if (!allowedStates.has(row.status)) throw new Error(`${row.stableId} has invalid status.`);
    for (const prerequisite of row.prerequisites) {
      if (!byId.has(prerequisite)) throw new Error(`${row.stableId} references missing prerequisite MS2-LT-${prerequisite}.`);
    }
    if (row.status === "PASS / PROTECTED") {
      if (row.protectedValue !== "Yes") throw new Error(`${row.stableId} lost protected confirmation.`);
      if (!row.ownerEvidence || /^(Not |Open|Awaiting)/i.test(row.ownerEvidence)) {
        throw new Error(`${row.stableId} lacks owner evidence.`);
      }
    }
  }

  const visiting = new Set();
  const visited = new Set();
  function visit(id) {
    if (visiting.has(id)) throw new Error(`Circular prerequisite at MS2-LT-${id}.`);
    if (visited.has(id)) return;
    visiting.add(id);
    for (const prerequisite of byId.get(id).prerequisites) visit(prerequisite);
    visiting.delete(id);
    visited.add(id);
  }
  for (const row of rows) visit(row.id);

  const blocks = [...master.matchAll(/^### MS2-LT-(\d{3}) — ([^\r\n]+)([\s\S]*?)(?=^### MS2-LT-|\n<!-- TRACEABILITY_INDEX_END -->)/gm)];
  if (blocks.length !== rows.length) throw new Error("Orphan checkpoint or missing traceability block.");
  const blockById = new Map(blocks.map((block) => [Number(block[1]), block]));
  const dependents = new Map(rows.map((row) => [row.id, []]));
  for (const row of rows) for (const prerequisite of row.prerequisites) dependents.get(prerequisite).push(row.id);
  for (const row of rows) {
    const block = blockById.get(row.id);
    if (!block) throw new Error(`${row.stableId} is orphaned from traceability.`);
    if (block[2].trim() !== row.name) throw new Error(`${row.stableId} traceability name is inconsistent.`);
    const traceStatus = block[3].match(/- \*\*Current status:\*\* (.+)/)?.[1]?.trim();
    if (traceStatus !== row.status) throw new Error(`${row.stableId} traceability status is inconsistent.`);
    const expected = dependents.get(row.id).length
      ? dependents.get(row.id).map((id) => `MS2-LT-${String(id).padStart(3, "0")}`).join(", ")
      : "None";
    const actual = block[3].match(/- \*\*Dependent checkpoints:\*\* (.+)/)?.[1]?.trim();
    if (actual !== expected) throw new Error(`${row.stableId} has missing or stale dependent metadata.`);
  }

  for (const stableId of protectedBaseline) {
    const id = Number(stableId.replace("MS2-LT-", ""));
    const row = byId.get(id);
    if (!row) throw new Error(`Previously protected checkpoint ${stableId} was deleted.`);
    const preserved = row.status === "PASS / PROTECTED"
      || (
        row.status === "Deprecated with repository evidence"
        && row.ownerEvidence.includes("Historical status PASS / PROTECTED")
        && row.evidence.includes("Lifecycle:")
      )
      || (
        row.status !== "PASS / PROTECTED"
        && row.evidence.includes("Reopened:")
        && row.ownerEvidence.includes("Historical status PASS / PROTECTED")
      );
    if (!preserved) throw new Error(`Previously protected checkpoint ${stableId} was silently weakened.`);
  }

  return { rows, dependents };
}

export function validateApprovalCoverage(rows, improvements) {
  const ownerVisible = improvements.filter((item) => item.owner_visible === true);
  const approvalIds = ownerVisible.map((item) => item.approval_id);
  const checkpointIds = ownerVisible.map((item) => item.checkpoint_id);
  if (new Set(approvalIds).size !== approvalIds.length) throw new Error("Duplicate approved-improvement ID.");
  if (new Set(checkpointIds).size !== checkpointIds.length) throw new Error("Duplicate approved checkpoint mapping.");
  const rowIds = rows.map((row) => row.stableId);
  for (const item of ownerVisible) {
    if (!rowIds.includes(item.checkpoint_id)) throw new Error(`Approved owner-visible improvement ${item.approval_id} is omitted.`);
  }
  for (const id of rowIds) {
    if (!checkpointIds.includes(id)) throw new Error(`${id} is orphaned from approved improvements.`);
  }
}

export function validateBridgeSnapshot(manifest, expected) {
  if (manifest.authority !== expected.authority) throw new Error("Outdated Bridge authority.");
  if (manifest.checkpoint_count !== expected.count) throw new Error("Outdated Bridge checkpoint count.");
  if (manifest.master_sha256 !== expected.checksum) throw new Error("Outdated Bridge checksum.");
  if (manifest.token_policy?.status !== "ACTIVE") throw new Error("Bridge token policy is not ACTIVE.");
  if (manifest.token_policy?.document !== expected.tokenPolicyDocument) throw new Error("Bridge token-policy reference is inconsistent.");
}

export function validateSynchronizedDocument(content, expected) {
  if (!content.includes(expected.master)) throw new Error("Synchronized document lost master authority.");
  if (!content.includes(`- Checkpoints: ${expected.count}`)) throw new Error("Synchronized document has stale count.");
  if (!content.includes(`- Current: ${expected.current}`)) throw new Error("Synchronized document has stale current checkpoint.");
  if (!content.includes("- Token policy: ACTIVE")) throw new Error("Synchronized document lost active token policy.");
}
