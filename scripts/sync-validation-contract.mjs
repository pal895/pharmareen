import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const root = path.resolve(import.meta.dirname, "..");
const contract = JSON.parse(fs.readFileSync(path.join(root, "scripts", "validation-contract.json"), "utf8"));

await import("./update-master-traceability.mjs");

const masterPath = path.join(root, contract.master);
const master = fs.readFileSync(masterPath, "utf8");
const rows = [];
let category = "";
for (const line of master.split(/\r?\n/)) {
  const section = line.match(/^## \d+\. (.+)$/);
  if (section) category = section[1];
  const cells = line.split("|").slice(1, -1).map((cell) => cell.trim());
  if (cells.length === 9 && /^\d+$/.test(cells[0])) {
    rows.push({ id: Number(cells[0]), name: cells[1], status: cells[4], category });
  }
}

const currentMatch = master.match(/The only current open checkpoint is \*\*#(\d+) ([^*]+)\*\*/);
const checksum = crypto.createHash("sha256").update(master).digest("hex");
const manifest = {
  schema: contract.schema,
  authority: contract.master,
  checkpoint_count: rows.length,
  current_checkpoint: currentMatch
    ? { id: `MS2-LT-${String(currentMatch[1]).padStart(3, "0")}`, name: currentMatch[2].trim() }
    : null,
  protected_checkpoint_ids: rows
    .filter((row) => row.status === "PASS / PROTECTED")
    .map((row) => `MS2-LT-${String(row.id).padStart(3, "0")}`),
  bridge_consumers: contract.bridge_consumers,
  token_policy: contract.token_policy,
  master_sha256: checksum,
  rule: "Load the master and its Engineering Traceability Index; never reconstruct or maintain a parallel sequence."
};

const syncStart = "<!-- VALIDATION_CONTRACT_SYNC_START -->";
const syncEnd = "<!-- VALIDATION_CONTRACT_SYNC_END -->";
const synchronizedBlock = [
  syncStart,
  "## Generated validation-contract reference",
  "",
  `- Authority: \`${contract.master}\``,
  `- Checkpoints: ${rows.length}`,
  `- Current: ${manifest.current_checkpoint ? `${manifest.current_checkpoint.id} — ${manifest.current_checkpoint.name}` : "None"}`,
  `- Bridge manifest: \`${contract.bridge_manifest}\``,
  `- Token policy: ${contract.token_policy.status} — \`${contract.token_policy.document}\``,
  "- Rule: Codex and ChatGPT Bridges load the master and Engineering Traceability Index; no parallel sequence is permitted.",
  syncEnd,
].join("\n");

for (const document of contract.synchronized_documents) {
  const documentPath = path.join(root, document);
  const current = fs.readFileSync(documentPath, "utf8");
  const withoutOldBlock = current.includes(syncStart)
    ? `${current.slice(0, current.indexOf(syncStart)).trimEnd()}\n${current.slice(current.indexOf(syncEnd) + syncEnd.length).trimStart()}`
    : current.trimEnd();
  fs.writeFileSync(documentPath, `${withoutOldBlock.trimEnd()}\n\n${synchronizedBlock}\n`, "utf8");
}

fs.writeFileSync(
  path.join(root, contract.bridge_manifest),
  `${JSON.stringify(manifest, null, 2)}\n`,
  "utf8",
);

console.log(`VALIDATION_CONTRACT_SYNCED checkpoints=${rows.length} bridge_manifest=${contract.bridge_manifest}`);
