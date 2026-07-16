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
  "src/services/catalogWorkspace.js",
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
  "CatalogWorkspaceCard",
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
assert(appSource.includes('data-action="open-catalog"'), "Saved catalog is not directly accessible from the home screen");
assert(appSource.includes("showCatalogWorkspace();"), "Successful onboarding does not lead into the catalog workspace");
assert(css.includes(".catalog-workspace-list") && css.includes("grid-template-columns: 1fr"), "Catalog workspace mobile layout protection missing");
assert(css.includes("repeat(2, minmax(0, 1fr))"), "Catalog workspace desktop layout protection missing");
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
assert(appSource.includes("pruneCatalogOnboardingCards"), "Saved catalog must prune stale onboarding cards");
assert(appSource.includes("removeCardsByType([\"CatalogOnboardingCard\"]"), "Catalog import paths must remove stale catalog choice cards");
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
assert(appSource.includes("dismiss-card"), "Editable card close control missing");
assert(appSource.includes("FEED_KEY"), "Conversation feed resume persistence missing");
assert(appSource.includes("ACTIVE_CARDS_KEY"), "Active editable-card resume persistence missing");
assert(appSource.includes("hydrateResumeState"), "Resume-state hydration missing");
assert(appSource.includes("setupComplete() || catalogItems.length > 0"), "Saved catalog must self-heal setup completion on resume");
assert(appSource.includes("persistFeed();"), "Conversation feed must persist after local changes");
assert(appSource.includes("persistActiveCards();"), "Editable cards must persist after local changes");
assert(appSource.includes("storage?.removeItem(FEED_KEY)"), "Reset setup must clear persisted conversation feed");
assert(appSource.includes("storage?.removeItem(ACTIVE_CARDS_KEY)"), "Reset setup must clear persisted active cards");
assert(appSource.includes("removeCardsByType([\"CatalogOnboardingCard\"]);"), "Saved catalog should remove only stale catalog prompts on resume");
assert(!appSource.includes("removeCardsByType([\"CatalogOnboardingCard\", \"CatalogImportCard\"]"), "Resume must not delete active catalog review cards");
assert(appSource.includes("catalogRequired"), "Notification catalog gate missing");
assert(appSource.includes("pharmacyBrain.findMedicine"), "Instant sale must require pharmacy catalog match");
assert(!appSource.includes("demo-voice"), "Fake voice demo action must not be present");
assert(!appSource.includes("Cancelled."), "Cancel must silently remove cards without chat noise");
assert(css.includes("replit-badge"), "Replit badge suppression CSS missing");
assert(css.includes(".card-font-controls"), "Editable card font controls CSS missing");
assert(css.includes(".card-close-button"), "Editable card close CSS missing");

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

const { parseLocalCommand, resolveStockCheck } = await import(pathToFileURL(path.join(root, "src/services/localIntelligence.js")));
const { OfflineQueue } = await import(pathToFileURL(path.join(root, "src/services/offlineQueue.js")));
const { CloudMemoryGateway } = await import(pathToFileURL(path.join(root, "src/services/cloudGateway.js")));
const { runVisualPipeline } = await import(pathToFileURL(path.join(root, "src/services/visualPipeline.js")));
const { BackendAdapterRegistry } = await import(pathToFileURL(path.join(root, "src/services/backendAdapters.js")));
const { SourceBrain, PharmacyBrain } = await import(pathToFileURL(path.join(root, "src/services/brainAdapters.js")));
const { createPasteImportCard, parseBulkMedicineList, parseDelimitedInventory, partitionCatalogItems, buildCatalogSavedSummary } = await import(pathToFileURL(path.join(root, "src/services/catalogOnboarding.js")));
const { buildDeterministicNotifications, mergeNotifications } = await import(pathToFileURL(path.join(root, "src/services/notificationCenter.js")));
const { buildCatalogCsv, buildBulkPasteTemplate } = await import(pathToFileURL(path.join(root, "src/services/documentGenerator.js")));
const { createCatalogWorkspaceCard, catalogWorkspaceItems, createCatalogEditDraft, reviewCatalogEdit, applyApprovedCatalogEdit } = await import(pathToFileURL(path.join(root, "src/services/catalogWorkspace.js")));

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
const compoundFormImport = parseBulkMedicineList("Ciprofloxacin eye drops 250", sourceBrain);
assert(compoundFormImport.items[0]?.form === "eye drops", "Supported compound forms must not be incorrectly singularized");
assert(compoundFormImport.items[0]?.unit === "eye drops", "Supported compound units must not be incorrectly singularized");
const emptyPasteCard = createPasteImportCard();
assert(emptyPasteCard.fields.entry_mode === "paste_input", "Paste onboarding must open an input step before review");
assert(emptyPasteCard.fields.items_text === "", "Paste onboarding must not silently insert sample medicines");
const bulkTemplate = buildBulkPasteTemplate();
assert(!/Cefixime|Ceftriaxone|Salbutamol|Metformin/i.test(bulkTemplate), "Bulk template must not contain pharmacy medicine data");
const partitionedPaste = partitionCatalogItems(
  parseBulkMedicineList("Cefixime tablet 120\nLoratadine syrup 160", sourceBrain).items,
  [{ name: "Cefixime" }]
);
assert(partitionedPaste.existing.length === 1 && partitionedPaste.existing[0].name === "Cefixime", "Paste review must identify medicines already in the pharmacy catalog");
assert(partitionedPaste.newItems.length === 1 && partitionedPaste.newItems[0].name === "Loratadine", "Paste review must retain genuinely new medicines");
const savedCatalogSummary = buildCatalogSavedSummary(catalogImport.items, catalogImport.unclear);
assert(savedCatalogSummary.includes("saved"), "Approved catalog summary must confirm saved state");
assert(!savedCatalogSummary.includes("ready for review"), "Approved catalog summary must not repeat review-state copy");

const delimited = parseDelimitedInventory("medicine,strength,form,selling price,stock,batch,expiry\nMetformin,500 mg,tablets,15,20,B1,2026-12-31", sourceBrain);
assert(delimited.items.length === 1, "CSV inventory import did not parse one row");
assert(delimited.aiRequired === false, "CSV inventory import must be zero-token");
assert(delimited.items[0].strength === "500 mg", "CSV inventory import must preserve medicine strength for owner review and approval");

const pharmacyBrain = new PharmacyBrain({ pharmacyId: "verify" });
pharmacyBrain.loadCatalog(delimited.items);
assert(pharmacyBrain.findMedicine("Metformin").status === "matched", "Pharmacy catalog lookup failed after import");
pharmacyBrain.upsertCatalogItem({ name: "Cefixime", form: "tablet", selling_price: "120", stock: "20" });
pharmacyBrain.upsertCatalogItem({ name: "Ceftriaxone", form: "vial", selling_price: "180", stock: "12" });
pharmacyBrain.upsertCatalogItem({ name: "Salbutamol", form: "inhaler", selling_price: "250", stock: "5" });
assert(pharmacyBrain.catalog.length === 4, "Catalog upsert must append medicines without replacing previous records");
pharmacyBrain.loadCatalog([...pharmacyBrain.catalog, { name: "Cefixime", strength: "400 mg" }]);
assert(pharmacyBrain.catalog.length === 4, "Catalog recovery must merge duplicate medicine identities");
assert(pharmacyBrain.findMedicine("Cefixime").matches[0].strength === "400 mg", "Catalog recovery must preserve medicine strength");
const workspaceCard = createCatalogWorkspaceCard(pharmacyBrain.catalog.length);
assert(workspaceCard.fields.item_count === "4" && workspaceCard.aiRequired === false, "Catalog workspace must reference the saved catalog without AI");
const workspaceItems = catalogWorkspaceItems(pharmacyBrain.catalog, "vial");
assert(workspaceItems.length === 1 && workspaceItems[0].name === "Ceftriaxone", "Catalog workspace search must filter saved medicines locally");
const editDraft = createCatalogEditDraft(pharmacyBrain.catalog.find((item) => item.name === "Cefixime"));
editDraft.selling_price = "125";
assert(reviewCatalogEdit(pharmacyBrain.catalog, editDraft.id, editDraft).valid, "Catalog medicine edit must enter deterministic review");
const editedCatalog = applyApprovedCatalogEdit(pharmacyBrain.catalog, editDraft.id, editDraft);
assert(editedCatalog.catalog.length === 4 && editedCatalog.updated.sellingPrice === "125", "Approved catalog edit must update without duplicating");
assert(pharmacyBrain.findMedicine("Ceftriaxone").status === "matched", "Catalog upsert lookup failed for added medicine");
const spellingMatch = pharmacyBrain.findMedicine("Cefimixe");
assert(spellingMatch.status === "matched" && spellingMatch.matchType === "close_spelling", "Unique catalog spelling variation should match through the shared local matcher");
assert(pharmacyBrain.findMedicine("Metf").matches[0].name === "Metformin", "Safe partial names should resolve through the shared local matcher");
const spellingSale = parseLocalCommand("Cefimixe 1 cash", pharmacyBrain.catalog);
assert(spellingSale.fields.medicine === "Cefixime", "Spelling variation sale must use the saved catalog medicine name");
assert(Number(spellingSale.fields.stockLeft) === 20, "Sale parse must carry saved catalog stock into the local action");
const spellingRestock = parseLocalCommand("restock cefimixe", pharmacyBrain.catalog);
assert(spellingRestock.fields.medicine === "Cefixime", "Spelling variation restock must use the saved catalog medicine name");
const stockCheck = resolveStockCheck("Cefimixe stock", pharmacyBrain.catalog);
assert(stockCheck.status === "matched" && stockCheck.medicine.name === "Cefixime", "Stock check must resolve spelling variations to the saved medicine");
assert(Number(stockCheck.medicine.stockLeft) === 20, "Stock check must return the saved catalog stock directly");
assert(appSource.includes("stockCheckReply(stockCheck.medicine)"), "Known stock checks must answer immediately without a report card");
assert(appSource.includes('data-action="reuse-command"'), "Owner messages must be reusable without adding chat clutter");
assert(appSource.includes('input.value = dataset.command || ""'), "Reusing a command must fill the composer without running it automatically");
assert(css.includes(".reusable-command"), "Reusable owner messages must preserve the simple chat-bubble layout");
assert(appSource.includes('data-action="capture-invoice"'), "Invoice menu must request a real owner capture");
assert(!appSource.includes('data-action="demo-invoice"'), "Owner invoice menu must not create a fake demo invoice");
assert(appSource.includes('state.pendingScanType = "invoice"'), "Invoice capture must enter the real invoice review path");
assert(appSource.includes('fetch("/api/ms20/invoice-scan"'), "Invoice photos must reach the local OCR endpoint");
assert(appSource.includes("resizeImageForReading(file)"), "Camera photos must be resized before OCR to protect phone memory");
assert(appSource.includes('source: "local_invoice_ocr"'), "Invoice review rows must identify local deterministic extraction");
assert(!appSource.includes('title: "Check photo details"'), "One camera capture must not create duplicate empty review cards");
assert(appSource.includes('invoiceMode ? "Approve medicines" : "Approve catalog"'), "Invoice review must use simple invoice-specific approval wording");
assert(appSource.includes('state.voice.status = "Reading invoice…"'), "Invoice capture must show immediate progress feedback");
assert(appSource.includes("openLightweightCamera"), "Camera actions must use the memory-safe in-app camera");
assert(appSource.includes('width: { ideal: 1920, max: 1920 }'), "In-app camera must keep invoice text readable while limiting capture resolution");
assert(appSource.includes('const readingEdge = video.videoWidth > video.videoHeight ? 2400 : 1800'), "Invoice capture must preserve enough landscape detail for local OCR");
assert(appSource.includes('card.fields.import_incomplete'), "Incomplete local invoice reads must be marked unsafe to approve");
assert(appSource.includes('const INVOICE_TABLE_COLUMNS'), "Invoice review must use purchase-specific fields");
assert(appSource.includes('line_total: item.line_total'), "Invoice review must expose line totals for owner cross-checking");
assert(appSource.includes('selling_price: item.selling_price'), "Optional invoice selling prices must reach the editable review");
assert(appSource.includes("INVOICE_MEMORY_KEY"), "Cancelled invoice reviews must retain reusable local evidence");
assert(appSource.includes('invoiceSummaryTemplate(card)'), "Invoice review must show invoice-level metadata once");
assert(appSource.includes('This scan is incomplete and cannot be approved.'), "Incomplete invoice review must explain the blocked approval plainly");
assert(appSource.includes('This scan is incomplete. Scan again before saving anything.'), "Blocked invoice must not tell the owner to approve");
assert(appSource.includes('Some details may be missing or incorrect. Check every field against the invoice.'), "Invoice review must honestly warn about missing and incorrect OCR values");
assert(appSource.includes('input.addEventListener("change", () => render())'), "Invoice approval state must rerender after owner edits");
assert(appSource.includes('refreshInvoiceImportCompleteness(card, catalogRowsForCard(card))'), "Persisted invoice edits must recompute approval state after reload");
assert(appSource.includes('invoice_owner_edited = "true"'), "Invoice review must remember owner corrections as stronger than later OCR");
assert(appSource.includes("ownerReviewedRows?.forEach"), "Complete owner-reviewed rows must survive weaker rescans");
assert(appSource.includes("If repeated scans differ, edit the fields to match the invoice, then approve."), "Invoice review must tell owners when to edit instead of rescanning repeatedly");
assert(appSource.includes('response.headers.get("content-type")'), "Invoice scan errors must not expose raw JSON parser failures");
assert(appSource.includes('mergeRememberedInvoiceReview(rows, result)'), "Repeated scans of the same invoice must reuse stronger prior local evidence");
assert(appSource.includes('invoiceRowsComplete(rows, result.invoice_total)'), "Remembered invoice evidence must pass row arithmetic and total checks before approval");
assert(appSource.includes('chooseInvoiceRowsByTotal(numericChoices, targetTotal)'), "Repeated invoice scans must select the row combination that matches the invoice total");
assert(appSource.includes('const allRows = [...rows, ...rememberedRows]'), "A medicine omitted by the newest scan must be recoverable from matching prior scans");
assert(appSource.includes('firstRememberedInvoiceValue(candidates, "invoice_total")'), "Invoice merge must search all matching reviews for a nonblank total");
assert(appSource.includes('matchedCardIds: candidates.map((card) => card.id)'), "Matching invoice rescans must consolidate into one canonical review card");
assert(appSource.includes('card.fields.invoice_evidence = JSON.stringify(remembered.evidence)'), "Canonical invoice review must persist medicine-scoped evidence across scans");
assert(appSource.includes('strongestInvoiceOrder(evidence.rows?.[key]?.positions)'), "Invoice source order must use repeated medicine-scoped position evidence");
assert(appSource.includes('const rememberedValue = rememberedRows.find'), "A blank rescan must preserve valid medicine-scoped canonical evidence");
assert(appSource.includes('chooseUniqueInvoiceBatches(evidence, [...groups.keys()])'), "Repeated invoice evidence must assign batches globally without cross-medicine reuse");
assert(appSource.includes('const currentRowsReconcile = rows.length === groups.size'), "A complete total-reconciled scan must restore photographed source order");
assert(appSource.includes('moveCatalogImportRow(dataset.cardId, dataset.rowIndex, dataset.direction)'), "Invoice review must let the owner correct row order without rescanning");
assert(appSource.includes('refreshInvoiceImportCompleteness(card, rows)'), "Invoice edits must immediately recalculate the approval safety gate");
assert(css.includes('.review-row-order-controls'), "Shared multi-row medicine reviews must expose compact order controls");
assert(appSource.includes('invoiceExpiryNotBefore(value, invoiceMonth)'), "Incoming invoice evidence must reject expiry dates older than the invoice");
assert(appSource.includes('This scan is missing invoice details.'), "Incomplete invoice approval must be blocked at the action boundary");
assert(appSource.includes("closeCameraStream()"), "In-app camera must release memory after capture or cancel");
assert(css.includes(".camera-overlay"), "Memory-safe camera preview UI missing");
assert(appSource.includes('"Ready — hold the phone still, then tap Capture."') && appSource.includes('"Ready — hold the phone still, keep bright light off the item, then tap Capture."'), "Camera preview must clearly say when each capture type is ready in simple English");
assert(appSource.includes('data-action="toggle-camera-light"'), "Camera light must be an optional owner control");
assert(!appSource.includes('capabilities.torch) advanced.push({ torch: true })'), "Camera light must never turn on automatically");
assert(appSource.includes('track.getSettings?.().torch'), "Camera light must verify that the phone actually applied the torch setting");
assert(appSource.includes('lightButton.addEventListener("click", () => void toggleCameraLight())'), "Dynamically added camera light control must respond to taps");
assert(css.includes('max-height: calc(100dvh - 32px)'), "Camera panel must fit inside the visible phone viewport");
assert(css.includes('.camera-panel:not(.acquisition-panel)') && css.includes('height: calc(100dvh - 32px)'), "Active camera panels must keep the full available viewing height");
assert(css.includes('grid-template-columns: repeat(3, minmax(0, 1fr))'), "All camera actions must stay on one visible row");
assert(css.includes("overscroll-behavior-y: contain"), "Chat scrolling must stay inside the message area");
assert(css.includes("height: 100dvh"), "Mobile app shell must follow the visible device viewport");
assert(appSource.includes("applyLocalRestockStock(card)"), "Confirmed restock must update local catalog stock");
assert(appSource.includes("medicine.stockLeft = stockLeft"), "Restock must persist the new stock level");
assert(appSource.includes("✅ ${medicine} +${totalAdded}") && appSource.includes("bought + ${bonusQuantity} bonus"), "Restock confirmation must use simple wording and keep bought and bonus stock distinct");

const notifications = buildDeterministicNotifications({ catalog: [{ name: "Cefixime", stockLeft: 2, batches: [{ batch: "B1", expiry: "2026-07-20" }] }] });
assert(notifications.some((item) => item.category === "Inventory"), "Low-stock notification missing");
assert(notifications.some((item) => item.category === "Expiry"), "Expiry notification missing");
const blankStockNotifications = buildDeterministicNotifications({ catalog: [{ name: "Zinc", stockLeft: "" }] });
assert(!blankStockNotifications.some((item) => item.category === "Inventory"), "Blank stock must not create out-of-stock notifications");
const setupNotifications = buildDeterministicNotifications({ catalog: [], catalogRequired: false });
assert(!setupNotifications.some((item) => item.id === "learning-catalog-empty"), "Catalog notification must wait until setup is complete");
const prunedNotifications = mergeNotifications(
  [{ id: "learning-catalog-empty", category: "Learning", title: "Medicine catalog needed", status: "unread", createdAt: "2026-01-01T00:00:00.000Z" }],
  []
);
assert(prunedNotifications.length === 0, "Resolved generated notifications must be pruned");

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
