import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import {
  validateApprovalCoverage,
  validateBridgeSnapshot,
  validateMasterText,
  validateSynchronizedDocument,
} from "./validation-contract-core.mjs";

const root = path.resolve(import.meta.dirname, "..");
const contract = JSON.parse(fs.readFileSync(path.join(root, "scripts", "validation-contract.json"), "utf8"));
const master = fs.readFileSync(path.join(root, contract.master), "utf8");
const manifestPath = path.join(root, contract.bridge_manifest);
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
const protectedBaseline = JSON.parse(fs.readFileSync(path.join(root, contract.protected_baseline), "utf8"));
const approvedImprovements = JSON.parse(fs.readFileSync(path.join(root, contract.approved_improvements), "utf8"));
const count = [...master.matchAll(/^\| \d+ \|/gm)].length;
const protectedCount = [...master.matchAll(/^\| \d+ \|.*\| PASS \/ PROTECTED \|/gm)].length;
const checksum = crypto.createHash("sha256").update(master).digest("hex");
const currentMatch = master.match(/The only current open checkpoint is \*\*#(\d+) ([^*]+)\*\*/);
const expectedCurrent = currentMatch ? `MS2-LT-${String(currentMatch[1]).padStart(3, "0")} — ${currentMatch[2].trim()}` : "None";

if (manifest.authority !== contract.master) throw new Error("Bridge authority does not point to the master.");
if (manifest.checkpoint_count !== count) throw new Error("Bridge checkpoint count is stale.");
if (manifest.protected_checkpoint_ids.length !== protectedCount) throw new Error("Bridge protected registry is stale.");
if (manifest.master_sha256 !== checksum) throw new Error("Bridge master checksum is stale.");
if (manifest.token_policy?.status !== "ACTIVE" || manifest.token_policy?.document !== contract.token_policy.document) {
  throw new Error("Bridge consumers do not inherit the active token policy.");
}
const tokenPolicy = fs.readFileSync(path.join(root, contract.token_policy.document), "utf8");
if (!tokenPolicy.includes("Token policy: **ACTIVE**")) throw new Error("Token policy is not ACTIVE.");
validateBridgeSnapshot(manifest, {
  authority: contract.master,
  count,
  checksum,
  tokenPolicyDocument: contract.token_policy.document,
});

const statusById = new Map();
for (const line of master.split(/\r?\n/)) {
  const cells = line.split("|").slice(1, -1).map((cell) => cell.trim());
  if (cells.length === 9 && /^\d+$/.test(cells[0])) {
    statusById.set(`MS2-LT-${String(cells[0]).padStart(3, "0")}`, {
      status: cells[4],
      ownerValidation: cells[5],
      evidence: cells[8],
    });
  }
}
for (const id of protectedBaseline.protected_checkpoint_ids) {
  const checkpoint = statusById.get(id);
  if (!checkpoint) throw new Error(`Previously protected checkpoint ${id} was deleted.`);
  const preserved = checkpoint.status === "PASS / PROTECTED"
    || (
      checkpoint.status === "Deprecated with repository evidence"
      && checkpoint.ownerValidation.includes("Historical status PASS / PROTECTED")
      && checkpoint.evidence.includes("Lifecycle:")
    )
    || (
      checkpoint.status !== "PASS / PROTECTED"
      && checkpoint.ownerValidation.includes("Historical status PASS / PROTECTED")
      && checkpoint.evidence.includes("Reopened:")
    );
  if (!preserved) throw new Error(`Previously protected checkpoint ${id} lost protection/history.`);
}

const ownerVisibleApprovals = approvedImprovements.improvements.filter((item) => item.owner_visible === true);
const approvalIds = ownerVisibleApprovals.map((item) => item.approval_id);
const approvalCheckpointIds = ownerVisibleApprovals.map((item) => item.checkpoint_id);
if (new Set(approvalIds).size !== approvalIds.length) throw new Error("Duplicate approved-improvement ID.");
if (new Set(approvalCheckpointIds).size !== approvalCheckpointIds.length) throw new Error("An approved improvement maps to a duplicate checkpoint.");
for (const approval of ownerVisibleApprovals) {
  const checkpoint = statusById.get(approval.checkpoint_id);
  if (!checkpoint) throw new Error(`Approved owner-visible improvement ${approval.approval_id} is omitted from the master.`);
}
for (const checkpointId of statusById.keys()) {
  if (!approvalCheckpointIds.includes(checkpointId)) throw new Error(`${checkpointId} is orphaned from the approved-improvement registry.`);
}
const validatedMaster = validateMasterText(master, protectedBaseline.protected_checkpoint_ids);
validateApprovalCoverage(validatedMaster.rows, approvedImprovements.improvements);

for (const document of contract.synchronized_documents) {
  const content = fs.readFileSync(path.join(root, document), "utf8");
  if (!content.includes(contract.master)) throw new Error(`${document} does not reference the master.`);
  if (!/Bridge/i.test(content)) throw new Error(`${document} does not preserve Bridge synchronization guidance.`);
  if (!content.includes("<!-- VALIDATION_CONTRACT_SYNC_START -->")) throw new Error(`${document} lacks the generated contract block.`);
  if (!content.includes(`- Checkpoints: ${count}`)) throw new Error(`${document} has a stale checkpoint count.`);
  if (!content.includes(`- Current: ${expectedCurrent}`)) throw new Error(`${document} has a stale current pointer.`);
  if (!content.includes("- Token policy: ACTIVE")) throw new Error(`${document} does not inherit the active token policy.`);
  validateSynchronizedDocument(content, {
    master: contract.master,
    count,
    current: expectedCurrent,
  });
}

await import("./verify-master-traceability.mjs");
console.log(`VALIDATION_CONTRACT_OK checkpoints=${count} synchronized_documents=${contract.synchronized_documents.length} bridges=${contract.bridge_consumers.length}`);
