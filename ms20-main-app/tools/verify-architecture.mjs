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
  "src/services/catalogOnboarding.js",
  "src/services/notificationCenter.js",
  "src/services/documentGenerator.js",
  "src/services/liveBackendGateway.js",
  "src/services/backendAdapters.js",
  "src/routes/routeRegistry.js",
  "src/data/sourceMedicines.js",
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
  "CatalogOnboardingCard",
  "CatalogImportCard",
  "ImportMappingCard",
  "NotificationCard",
  "DocumentExportCard",
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
assert(appSource.includes("chatHomeTemplate"), "Messaging app home missing");
assert(appSource.includes("chatScreenTemplate"), "Messaging app conversation screen missing");
assert(appSource.includes("Notifications"), "Separate Notifications workspace missing");
assert(appSource.includes("CatalogOnboardingCard"), "Catalog onboarding card flow missing");
assert(appSource.includes("catalog-onboarding-prompt"), "Catalog onboarding prompt must not render as generic editable fields");
assert(appSource.includes("CatalogImportCard"), "Catalog import card flow missing");
assert(appSource.includes("catalog-import-editor"), "Catalog import card must use owner-friendly paste editor");
assert(appSource.includes("catalog-import-table"), "Catalog import card must expose column editing");
assert(appSource.includes("catalogImportMobileRowTemplate"), "Catalog import card must expose mobile medicine rows");
assert(appSource.includes("catalog-mobile-rows"), "Catalog import card must render mobile-friendly rows");
assert(appSource.includes("data-catalog-field"), "Catalog table cells must be editable");
assert(appSource.includes("updateCatalogImportCell"), "Catalog table edits must update the approved payload");
assert(appSource.includes("MEDICINE_DETAIL_CARD_TYPES"), "Reusable medicine-detail card layout missing");
assert(appSource.includes("exportCatalogCsv"), "Catalog CSV export action missing");
assert(appSource.includes("speechSynthesis"), "Local read-aloud support missing");
assert(appSource.includes("canRecordInstantly"), "Instant complete-sale behavior missing");
assert(css.includes(".chat-app"), "Messaging app CSS shell missing");
assert(css.includes(".conversation-row"), "Chat home conversation row missing");
assert(css.includes(".message-bubble"), "Chat message bubbles missing");
assert(css.includes(".catalog-onboarding-prompt"), "Catalog onboarding prompt CSS missing");
assert(css.includes(".catalog-import-editor"), "Catalog import editor CSS missing");
assert(css.includes(".catalog-import-table"), "Catalog import table CSS missing");
assert(css.includes(".catalog-mobile-row"), "Catalog mobile row CSS missing");
assert(css.includes(".medicine-detail-grid"), "Medicine detail grid CSS missing");
assert(appSource.includes("ensureOnboardingStarted"), "First-run onboarding guard missing");
assert(appSource.includes("startVoiceCapture"), "Browser voice capture path missing");
assert(appSource.includes("capture=\"environment\""), "Direct camera capture input missing");
assert(appSource.includes("CARD_FONT_SCALE_KEY"), "Editable card text-size persistence missing");
assert(appSource.includes("increase-card-font"), "Editable card zoom-in control missing");
assert(appSource.includes("decrease-card-font"), "Editable card zoom-out control missing");
assert(appSource.includes("pharmacyBrain.findMedicine"), "Instant sale must require pharmacy catalog match");
assert(!appSource.includes("demo-voice"), "Fake voice demo action must not be present");
assert(!appSource.includes("Cancelled."), "Cancel must silently remove cards without chat noise");
assert(css.includes("replit-badge"), "Replit badge suppression CSS missing");
assert(css.includes(".card-font-controls"), "Editable card font controls CSS missing");

for (const card of requiredCards) {
  assert(appSource.includes(card) || contracts.includes(card), `Missing card type ${card}`);
}

assert(contracts.includes("/api/ms20"), "MS2.0 API route slot missing");
assert(contracts.includes("/live/readiness"), "Live readiness route missing");
assert(contracts.includes("IntelligenceSeparationContract"), "Brain/catalog separation contract missing");
assert(contracts.includes("WorkspaceContract"), "Operations/notifications contract missing");
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
const { SourceBrain, PharmacyBrain } = await import(pathToFileURL(path.join(root, "src/services/brainAdapters.js")));
const { parseBulkMedicineList, parseDelimitedInventory } = await import(pathToFileURL(path.join(root, "src/services/catalogOnboarding.js")));
const { buildDeterministicNotifications } = await import(pathToFileURL(path.join(root, "src/services/notificationCenter.js")));
const { buildCatalogCsv } = await import(pathToFileURL(path.join(root, "src/services/documentGenerator.js")));

const sale = parseLocalCommand("panadol2cash");
assert(sale.kind === "sale", "Demo text command did not create a sale parse");
assert(sale.cardType === "SaleCard", "Demo text command did not route to SaleCard");
assert(sale.aiRequired === false, "Known structured sale should be zero-token");

const invoice = runVisualPipeline({ fileName: "invoice.jpg", scanType: "invoice" });
assert(invoice.outputCardType === "InvoiceCard", "Invoice scan did not route to InvoiceCard");
assert(invoice.aiRequired === false, "Photo placeholder should not call AI");
assert(invoice.tokenControl?.aiUsed === false, "Visual pipeline token-control proof missing");
assert(invoice.steps.some((step) => step.name === "local_fingerprint"), "Visual fingerprint step missing");

const sourceBrain = new SourceBrain();
const cefixime = sourceBrain.lookupMedicine("Cefixime");
assert(cefixime.status === "matched", "Source brain did not recognize Cefixime");

const catalogImport = parseBulkMedicineList("Cefixime tablets 120\nCeftriaxone vial 180\nZinc syrup 70", sourceBrain);
assert(catalogImport.aiRequired === false, "Bulk import must be zero-token");
assert(catalogImport.items.length === 3, "Bulk medicine import did not parse three lines");

const delimited = parseDelimitedInventory("medicine,form,selling price,stock,batch,expiry\nMetformin,tablets,15,20,B1,2026-12-31", sourceBrain);
assert(delimited.items.length === 1, "CSV inventory import did not parse one row");
assert(delimited.aiRequired === false, "CSV inventory import must be zero-token");

const pharmacyBrain = new PharmacyBrain({ pharmacyId: "verify" });
pharmacyBrain.loadCatalog(delimited.items);
assert(pharmacyBrain.findMedicine("Metformin").status === "matched", "Pharmacy catalog lookup failed after import");
pharmacyBrain.upsertCatalogItem({ name: "Cefixime", form: "tablet", selling_price: "120", stock: "20" });
pharmacyBrain.upsertCatalogItem({ name: "Ceftriaxone", form: "vial", selling_price: "180", stock: "12" });
pharmacyBrain.upsertCatalogItem({ name: "Salbutamol", form: "inhaler", selling_price: "250", stock: "5" });
assert(pharmacyBrain.catalog.length === 4, "Catalog upsert must append medicines without replacing previous records");
assert(pharmacyBrain.findMedicine("Ceftriaxone").status === "matched", "Catalog upsert lookup failed for added medicine");

const notifications = buildDeterministicNotifications({ catalog: [{ name: "Cefixime", stockLeft: 2, batches: [{ batch: "B1", expiry: "2026-07-20" }] }] });
assert(notifications.some((item) => item.category === "Inventory"), "Low-stock notification missing");
assert(notifications.some((item) => item.category === "Expiry"), "Expiry notification missing");

const csv = buildCatalogCsv(pharmacyBrain.catalog);
assert(csv.includes("Metformin"), "Catalog CSV export missing medicine");

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
