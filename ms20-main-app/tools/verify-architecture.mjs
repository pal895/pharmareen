import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const requiredFiles = [
  "index.html",
  "manifest.json",
  "package.json",
  "src/app.js",
  "src/styles.css",
  "src/contracts/integrationContracts.js",
  "src/cards/editableCards.js",
  "src/services/cloudGateway.js",
  "src/services/offlineQueue.js",
  "src/services/syncAdapter.js",
  "src/services/localIntelligence.js",
  "src/services/visualPipeline.js",
  "src/services/brainAdapters.js",
  "src/services/liveBackendGateway.js",
  "src/services/backendAdapters.js",
  "src/routes/routeRegistry.js",
  "src/data/demoState.js",
  "README.md",
  "FINAL_REPORT.md"
];

const requiredCards = [
  "SaleCard",
  "InvoiceCard",
  "RestockCard",
  "OnboardingCard",
  "StockCorrectionCard",
  "ReportCard",
  "VoiceReviewCard",
  "PhotoReviewCard",
  "MedicineMatchCard",
  "VisualScanCard",
  "SyncReviewCard"
];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function read(rel) {
  return fs.readFileSync(path.join(root, rel), "utf8");
}

for (const rel of requiredFiles) {
  assert(fs.existsSync(path.join(root, rel)), `Missing ${rel}`);
}

const appSource = read("src/app.js");
const html = read("index.html");
const css = read("src/styles.css");
const contracts = read("src/contracts/integrationContracts.js");
const liveGatewaySource = read("src/services/liveBackendGateway.js");
const backendAdapterSource = read("src/services/backendAdapters.js");
const runtimeSources = [appSource, liveGatewaySource, backendAdapterSource].join("\n");
const oldBrand = ["Phar", "Mareen"].join("");

assert(html.includes("MS2.0 Main App"), "HTML title is not branded MS2.0");
assert(!appSource.includes(oldBrand), "User-facing app source still contains old brand");
assert(!html.includes(oldBrand), "HTML still contains old brand");
assert(css.includes("@media (max-width: 720px)"), "Mobile responsive layout missing");
assert(appSource.includes("conversationHeaderTemplate"), "Messaging-first shell missing");
assert(css.includes(".message-os"), "Messaging-first CSS shell missing");

for (const card of requiredCards) {
  assert(appSource.includes(card) || contracts.includes(card), `Missing card type ${card}`);
}

assert(contracts.includes("/api/ms20"), "MS2.0 API route slot missing");
assert(contracts.includes("/live/readiness"), "Live readiness route missing");
assert(contracts.includes("cloud"), "Cloud memory contract missing");
assert(contracts.includes("Baileys WhatsApp bridge"), "External channel compatibility missing");
assert(liveGatewaySource.includes("127.0.0.1:5000"), "Local backend gateway fallback missing");
assert(appSource.includes("pathname.startsWith(\"/main-app/\")"), "Replit /main-app backend auto-probe missing");
assert(backendAdapterSource.includes("safe_queue_only"), "Live backend writes must remain queue-only in this merge");
for (const pattern of [/api\.openai/i, /new OpenAI/i, /responses\.create/i, /chat\/completions/i, /OPENAI_API_KEY/]) {
  assert(!pattern.test(runtimeSources), `Unsafe provider call pattern found: ${pattern}`);
}

const { parseLocalCommand } = await import(pathToFileURL(path.join(root, "src/services/localIntelligence.js")));
const { OfflineQueue } = await import(pathToFileURL(path.join(root, "src/services/offlineQueue.js")));
const { CloudMemoryGateway } = await import(pathToFileURL(path.join(root, "src/services/cloudGateway.js")));
const { runVisualPipeline } = await import(pathToFileURL(path.join(root, "src/services/visualPipeline.js")));
const { BackendAdapterRegistry } = await import(pathToFileURL(path.join(root, "src/services/backendAdapters.js")));

const sale = parseLocalCommand("panadol2cash");
assert(sale.kind === "sale", "Demo text command did not create a sale parse");
assert(sale.cardType === "SaleCard", "Demo text command did not route to SaleCard");
assert(sale.aiRequired === false, "Known structured sale should be zero-token");

const invoice = runVisualPipeline({ fileName: "invoice.jpg", scanType: "invoice" });
assert(invoice.outputCardType === "InvoiceCard", "Invoice scan did not route to InvoiceCard");
assert(invoice.aiRequired === false, "Photo placeholder should not call AI");

const queue = new OfflineQueue(null);
const queued = queue.add({ id: "verify-action-1", type: "SaleCard" });
const duplicate = queue.add({ id: "verify-action-1", type: "SaleCard" });
assert(queued.added === true, "Offline queue did not accept action");
assert(duplicate.duplicate === true, "Offline queue did not block duplicate action");

const cloud = new CloudMemoryGateway();
const recovery = await cloud.recoverWorkspace("verify-session");
assert(recovery.recovered === true, "Cloud recovery placeholder failed");

const backendAdapters = new BackendAdapterRegistry();
const adapterStatus = backendAdapters.status();
assert(adapterStatus.commandParserAdapter === true, "Command parser adapter missing");
assert(adapterStatus.saleEngineAdapter === true, "Sale engine adapter slot is not live-wired");
assert(adapterStatus.stockEngineAdapter === true, "Stock engine adapter slot is not live-wired");
assert(adapterStatus.reportEngineAdapter === true, "Report engine adapter slot is not live-wired");
assert(adapterStatus.onboardingEngineAdapter === true, "Onboarding engine adapter slot is not live-wired");
assert(adapterStatus.externalChannelAdapter === true, "Baileys/external channel adapter slot is not live-wired");
assert(backendAdapters.endpointLinks().health.endsWith("/health"), "Health endpoint link missing");

console.log(JSON.stringify({
  status: "PASS",
  checkedFiles: requiredFiles.length,
  checkedCards: requiredCards.length,
  zeroTokenProof: {
    sale_ai_required: sale.aiRequired,
    visual_ai_required: invoice.aiRequired,
    openai_api_calls: false,
    local_backend_probe_supported: true
  },
  protectedLiveSystem: "No files outside ms20-main-app are modified by this verification."
}, null, 2));
