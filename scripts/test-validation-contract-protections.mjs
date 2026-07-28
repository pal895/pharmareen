import assert from "node:assert/strict";
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
const master = fs.readFileSync(path.join(root, "MS2.0_MASTER_LIVE_TEST_SEQUENCE.md"), "utf8");
const baseline = JSON.parse(fs.readFileSync(path.join(root, "scripts", "protected-checkpoint-baseline.json"), "utf8"))
  .protected_checkpoint_ids;
const contract = JSON.parse(fs.readFileSync(path.join(root, "scripts", "validation-contract.json"), "utf8"));
const approvals = JSON.parse(fs.readFileSync(path.join(root, contract.approved_improvements), "utf8")).improvements;
const manifest = JSON.parse(fs.readFileSync(path.join(root, contract.bridge_manifest), "utf8"));

const validated = validateMasterText(master, baseline);
validateApprovalCoverage(validated.rows, approvals);

function mustReject(name, mutate, pattern) {
  assert.throws(() => validateMasterText(mutate(master), baseline), pattern, name);
}

const row1 = master.match(/^\| 1 \|.*$/m)[0];
mustReject("duplicate ID", (text) => text.replace(row1, `${row1}\n${row1.replace("Main App shell and navigation", "Duplicate ID fixture")}`), /Duplicate checkpoint ID/);
mustReject("deleted checkpoint", (text) => text.replace(`${row1}\n`, ""), /deleted|orphan|missing prerequisite/i);
mustReject("orphan checkpoint", (text) => text.replace(/^### MS2-LT-001 —[\s\S]*?(?=^### MS2-LT-002 —)/m, ""), /Orphan checkpoint/);
mustReject(
  "missing prerequisite",
  (text) => text.replace(
    /(\| 13 \| Editable-card voice viewport\/focus \|[^|\r\n]*\|) 10–12 (\|)/,
    "$1 999 $2",
  ),
  /missing prerequisite/,
);
mustReject("circular prerequisite", (text) => text.replace("| 1 | Main App shell and navigation | Open Home, Assistant, Notifications, Catalog and Payment Queue without unintended mutation. | None |", "| 1 | Main App shell and navigation | Open Home, Assistant, Notifications, Catalog and Payment Queue without unintended mutation. | 2 |"), /Circular prerequisite/);
mustReject("missing dependent", (text) => text.replace("- **Dependent checkpoints:** MS2-LT-002, MS2-LT-012, MS2-LT-058", "- **Dependent checkpoints:** None"), /dependent metadata/);
mustReject("weakened protected status", (text) => text.replace("| 1 | Main App shell and navigation | Open Home, Assistant, Notifications, Catalog and Payment Queue without unintended mutation. | None | PASS / PROTECTED | Passed | Yes |", "| 1 | Main App shell and navigation | Open Home, Assistant, Notifications, Catalog and Payment Queue without unintended mutation. | None | Partial implementation | Not passed | No |"), /silently weakened|status is inconsistent/);
mustReject("removed owner evidence", (text) => text.replace("| PASS / PROTECTED | Passed | Yes | 5 min | CVS; ARCH; `verify-architecture.mjs` |", "| PASS / PROTECTED | Awaiting owner validation | Yes | 5 min | CVS; ARCH; `verify-architecture.mjs` |"), /lacks owner evidence/);
mustReject("inconsistent traceability status", (text) => text.replace("- **Current status:** PASS / PROTECTED", "- **Current status:** Partial implementation"), /status is inconsistent/);

assert.throws(
  () => validateApprovalCoverage(validated.rows, [...approvals, {
    approval_id: "APPROVED-MISSING",
    owner_visible: true,
    checkpoint_id: "MS2-LT-999",
    name: "Missing approved improvement",
  }]),
  /omitted/,
);

const bridgeExpected = {
  authority: contract.master,
  count: validated.rows.length,
  checksum: crypto.createHash("sha256").update(master).digest("hex"),
  tokenPolicyDocument: contract.token_policy.document,
};
validateBridgeSnapshot(manifest, bridgeExpected);
assert.throws(() => validateBridgeSnapshot({ ...manifest, checkpoint_count: 75 }, bridgeExpected), /Outdated Bridge/);
assert.throws(() => validateBridgeSnapshot({ ...manifest, token_policy: { status: "INACTIVE" } }, bridgeExpected), /token policy/);

const current = "MS2-LT-013 — Editable-card voice viewport/focus";
const synchronized = fs.readFileSync(path.join(root, contract.synchronized_documents[0]), "utf8");
const synchronizedExpected = { master: contract.master, count: validated.rows.length, current };
validateSynchronizedDocument(synchronized, synchronizedExpected);
assert.throws(
  () => validateSynchronizedDocument(synchronized.replace("- Checkpoints: 76", "- Checkpoints: 75"), synchronizedExpected),
  /stale count/,
);
assert.throws(
  () => validateSynchronizedDocument(synchronized.replace("- Token policy: ACTIVE", "- Token policy: BLOCKED"), synchronizedExpected),
  /token policy/,
);

console.log("VALIDATION_PROTECTION_TESTS_OK cases=16");
