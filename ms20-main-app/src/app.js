import { demoState, nowLabel } from "./data/demoState.js";
import { CloudMemoryGateway } from "./services/cloudGateway.js";
import { OfflineQueue } from "./services/offlineQueue.js";
import { SyncAdapter } from "./services/syncAdapter.js";
import { BackendAdapterRegistry } from "./services/backendAdapters.js";
import { PharmacyBrain, SourceBrain, AIFallbackAdapter } from "./services/brainAdapters.js";
import { findBarcodeTestFixture } from "./data/barcodeTestFixtures.js";
import { findShelfTestFixture } from "./data/shelfTestFixtures.js";
import { findMedicinePhotoTestFixture } from "./data/medicinePhotoTestFixtures.js";
import { runVisualPipeline, buildPhotoReviewCard } from "./services/visualPipeline.js";
import {
  createCatalogChoiceCard,
  createPasteImportCard,
  parseBulkMedicineList,
  parseCatalogText,
  parseDelimitedInventory,
  catalogItemsToText,
  prepareCatalogImport,
  buildImportSummary,
  buildCatalogSavedSummary
} from "./services/catalogOnboarding.js";
import { buildDeterministicNotifications, buildTransactionNotification, mergeNotifications, notificationToCard } from "./services/notificationCenter.js";
import {
  buildBulkPasteTemplate, buildCanonicalInventoryExport, buildDocumentCard,
  buildInventoryCsv, buildInventoryDocx, buildInventoryPdf, buildInventoryPptx,
  buildInventoryXlsx, buildPrintHtml, downloadBlobFile, downloadTextFile, exportFilename,
  validateInventoryPptxPackage
} from "./services/documentGenerator.js";
import { EXPORT_FORMATS, exportCompletionSummary, exportFormat } from "./services/exportFormatMetadata.js";
import { appendActivity, createCatalogActivityEntry } from "./services/activityHistory.js";
import { createVoiceViewportAnchor, restoreVoiceViewportAnchor, settleVoiceViewportAnchor } from "./services/voiceViewportAnchor.js";
import {
  CATALOG_EDIT_FIELDS,
  applyCatalogEditVoice,
  applyCatalogSearchVoice,
  applyApprovedCatalogEdit,
  catalogItemId,
  createCatalogEditDraft,
  createCatalogWorkspaceCard,
  catalogWorkspaceItems,
  catalogEditPresentation,
  reviewCatalogEdit
} from "./services/catalogWorkspace.js";
import { cardFieldsFor, createEditableCard, paymentOptions, quantityBumps } from "./cards/editableCards.js";
import {
  CATALOG_IMPORT_FIELD_KEYS,
  MEDICINE_DETAIL_FIELD_ORDER,
  MEDICINE_FIELD_DEFINITIONS,
  medicineFieldColumns,
  medicineFieldLabel,
  medicineRecordFromFields,
  normalizeMedicineReviewRow
} from "./services/medicineFieldSchema.js";
import { resolveStockCheck } from "./services/localIntelligence.js";
import { matchMedicine } from "./services/medicineMatcher.js";
import { catalogReviewCapabilities, reorderedCatalogRows } from "./services/catalogReviewPolicy.js";
import { medicineReviewBlocker } from "./services/medicineReviewReadiness.js";
import { CashPaymentAdapter, ManualPaymentAdapter, SimulatorPaymentAdapter } from "./services/paymentAdapters.js";
import { TransactionCompletionEngine } from "./services/transactionCompletionEngine.js";
import { applyStockCorrectionVoice, PharmacyPronunciationMemory, reviewStockCorrection, stockCorrectionGuidance, trustedCatalogStock } from "./services/stockCorrectionPolicy.js";
import { executeStockCorrection, replayPendingStockCorrections } from "./services/stockCorrectionExecution.js";
import { prepareProductionSaleCard, productionSaleSummary, saleFieldsFromTransaction } from "./services/productionSaleCard.js";
import { completedSaleByReference, SaleAdjustmentEngine, saleDetailFields, saleReferenceFromReceipt } from "./services/saleAdjustmentReview.js";
import { parseSaleDirectCommand } from "./services/saleDirectCommand.js";
import { hydrateStockFixDraft, normalizeStockFixEvidence } from "./services/stockFixEvidencePipeline.js";
import { readXlsxInventory } from "./services/excelInventory.js";
import { listRouteSlots, resolveOfflineSlot } from "./routes/routeRegistry.js";
import {
  TokenPolicy,
  CloudMemoryContract,
  IntelligenceSeparationContract,
  WorkspaceContract
} from "./contracts/integrationContracts.js";

const state = structuredClone(demoState);
const cloudGateway = new CloudMemoryGateway();
const queue = new OfflineQueue();
const syncAdapter = new SyncAdapter({ queue, cloudGateway });
const backendAdapters = new BackendAdapterRegistry();
const paymentSimulator = new SimulatorPaymentAdapter({ scenario: "delayed_confirmation" });
const transactionEngine = new TransactionCompletionEngine({
  adapters: {
    cash: new CashPaymentAdapter(),
    manual: new ManualPaymentAdapter(),
    simulator: paymentSimulator
  }
});
const saleAdjustmentEngine = new SaleAdjustmentEngine({ storage: safeLocalStorage(), staffIdentity: () => "Owner" });
const pharmacyBrain = new PharmacyBrain({ pharmacyId: state.pharmacy.id });
const pronunciationMemory = new PharmacyPronunciationMemory(state.pharmacy.id, safeLocalStorage());
const sourceBrain = new SourceBrain();
const aiFallback = new AIFallbackAdapter();
const SETUP_KEY = "ms20-main-app:onboarding-complete";
const CARD_FONT_SCALE_KEY = "ms20-main-app:card-font-scale";
const CATALOG_KEY = "ms20-main-app:pharmacy-catalog";
const NOTIFICATION_KEY = "ms20-main-app:notifications";
const FEED_KEY = "ms20-main-app:conversation-feed";
const ACTIVE_CARDS_KEY = "ms20-main-app:active-cards";
const INVOICE_MEMORY_KEY = "ms20-main-app:invoice-memory";
const QUARANTINED_CARDS_KEY = "ms20-main-app:quarantined-cards";
const EXPORT_HISTORY_KEY_PREFIX = "ms20-main-app:export-history";
const ACTIVITY_HISTORY_KEY_PREFIX = "ms20-main-app:activity-history";
const EXPORT_HISTORY_LIMIT = 50;
const FEED_RESUME_LIMIT = 40;
const ACTIVE_CARD_RESUME_LIMIT = 12;
const CARD_FONT_SCALE_MIN = 0.85;
const CARD_FONT_SCALE_MAX = 1.25;
let speechControl = { cardId: "", paused: false, segments: [], index: 0 };
let speechRunId = 0;
let activeReportRequest = null;
let activeFinderWindow = null;
const CARD_FONT_SCALE_STEP = 0.1;
let activeStockFixScan = null;
let pendingStockFixEvidenceSource = "photo";
const CATALOG_TABLE_COLUMNS = medicineFieldColumns(CATALOG_IMPORT_FIELD_KEYS);
const INVOICE_TABLE_COLUMNS = [
  ...CATALOG_TABLE_COLUMNS.filter((column) => column.key !== "supplier"),
  { key: "line_total", label: "Line total", min: 120, inputMode: "decimal" }
];
const MEDICINE_DETAIL_CARD_TYPES = new Set([
  "InvoiceCard",
  "RestockCard",
  "StockCorrectionCard",
  "PhotoReviewCard",
  "MedicineMatchCard",
  "VisualScanCard"
]);
const PROGRESSIVE_MEDICINE_CARD_TYPES = new Set(MEDICINE_DETAIL_CARD_TYPES);
const DURABLE_CARD_TYPES = new Set([
  "SaleCard",
  "InvoiceCard",
  "RestockCard",
  "OnboardingCard",
  "StockCorrectionCard",
  "ReportCard",
  "PhotoReviewCard",
  "MedicineMatchCard",
  "VisualScanCard",
  "CatalogOnboardingCard",
  "CatalogImportCard",
  "CatalogWorkspaceCard",
  "ImportMappingCard",
  "DocumentExportCard",
  "ExportHubCard",
  "ActivityHubCard",
  "SyncReviewCard"
]);
const FIELD_LABELS = {
  ...Object.fromEntries(Object.entries(MEDICINE_FIELD_DEFINITIONS).map(([key, definition]) => [key, definition.label])),
  medicine: "Medicine",
  form: "Form",
  unit: "Unit",
  pack_size: "Pack size",
  quantity: "Quantity",
  stock: "Quantity",
  current_stock: "Current stock",
  correct_stock: "Correct stock",
  stockLeft: "Stock left",
  cost_price: "Buying price",
  line_total: "Line total",
  invoice_supplier: "Supplier",
  invoice_number: "Invoice number",
  invoice_date: "Invoice date",
  invoice_total: "Invoice total",
  selling_price: "Selling price",
  supplier: "Supplier",
  barcode: "Barcode",
  batch: "Batch",
  expiry: "Expiry",
  shelf: "Shelf",
  category: "Category",
  reason: "Reason",
  alias: "Alias",
  file: "File",
  scan_type: "Scan type",
  total: "Total",
  payment: "Payment",
  message: "Note",
  transcript: "Transcript",
  backend_route: "Backend route",
  items_text: "Medicine list"
};
const PRODUCTION_SALE_EDITABLE_FIELDS = Object.freeze([
  "medicine", "form", "unit", "pack_conversion", "selling_price", "quantity", "payment",
  "current_stock", "strength", "cost_price", "supplier", "barcode", "batch", "expiry",
  "aliases", "note"
]);
const PRODUCTION_SALE_REFRESH_FIELDS = Object.freeze([
  ...PRODUCTION_SALE_EDITABLE_FIELDS,
  "expected_total", "stock_before", "stock_after", "sale_status", "stock_deduction",
  "base_stock_unit"
]);
let activeRecognition = null;
let voiceCaptureAttempt = 0;
let stockFixReading = null;
let stockFixReadingSequence = 0;

state.ui = { screen: "home", workspace: "operations" };
state.voice = { starting: false, listening: false, status: "" };
state.camera = { open: false, scanType: "medicine_photo", stream: null, status: "", lightAvailable: false, lightOn: false, capturedFile: null, capturedUrl: "", retryRequired: false };
state.printPreview = null;
state.shelfAcquisitionOpen = false;
state.pendingScanType = "medicine_photo";
state.stockFixPhotoCardId = "";
state.catalogPasteCaptureCardId = "";
state.cardFontScale = readCardFontScale();
hydrateResumeState();
state.notifications = readNotifications();
state.liveBackend = {
  baseUrl: backendAdapters.liveBackendGateway.baseUrl,
  health: { ok: false, status: 0 },
  readinessSummary: { status: "not_checked", sheets: false, baileys: false, offline: false, blocked: [] },
  routes: backendAdapters.endpointLinks(),
  writeMode: "safe_queue_only",
  tokenImpact: "zero_openai_api_tokens"
};
refreshNotifications();

const root = document.querySelector("#app");
let activeVoiceViewportAnchor = null;
let activeCardViewportAnchor = null;

function render() {
  state.sync.online = navigator.onLine;
  state.sync.pending = queue.pendingCount();
  if (activeVoiceViewportAnchor && refreshContextualFieldVoiceDom()) return;
  const existingPrintFrame = root.querySelector("#ms20PrintPreview");
  const cameraOverlayIsRendered = Boolean(root.querySelector(".camera-overlay"));
  if (state.printPreview && existingPrintFrame && cameraOverlayIsRendered === state.camera.open) {
    refreshPrintPreviewDom(existingPrintFrame);
    return;
  }
  root.innerHTML = `
    <main class="chat-app" style="--card-font-scale: ${state.cardFontScale};">
      ${state.ui.screen === "chat" ? chatScreenTemplate() : state.ui.screen === "payments" ? paymentQueueScreenTemplate() : chatHomeTemplate()}
      ${shelfAcquisitionTemplate()}
      ${state.printPreview ? `<section class="print-preview-overlay" aria-label="Print preview"><iframe id="ms20PrintPreview" title="MS2.0 Pharmacy Inventory print preview"></iframe></section>` : ""}
      ${cameraOverlayTemplate()}
    </main>
  `;
  const printFrame = root.querySelector("#ms20PrintPreview");
  if (printFrame && state.printPreview) printFrame.srcdoc = buildPrintHtml(state.printPreview.model, {
    bridgeId: state.printPreview.bridgeId,
    initialQuery: state.printPreview.query,
    initialMessage: state.printPreview.message
  });
  bindEvents();
  hideReplitBadge();
  if (state.ui.screen === "payments") root.querySelector("#paymentQueueBody")?.scrollTo({ top: 0 });
  else if (activeVoiceViewportAnchor) {
    settleVoiceViewportAnchor(
      root,
      activeVoiceViewportAnchor,
      window,
      { restoreFocus: !state.voice.starting && !state.voice.listening }
    );
  } else if (activeCardViewportAnchor) {
    if (!settleVoiceViewportAnchor(root, activeCardViewportAnchor, window, { restoreFocus: false })) {
      activeCardViewportAnchor = null;
      scrollChatToBottom();
    }
  } else {
    scrollChatToBottom();
  }
}

function refreshPrintPreviewDom(frame) {
  const documentRoot = frame.contentDocument;
  if (!documentRoot || !state.printPreview) return;
  const input = documentRoot.querySelector("#medicine-search");
  if (input && input.value !== state.printPreview.query) {
    input.value = state.printPreview.query;
    const filter = documentRoot.querySelector("#medicine-filter");
    if (filter) filter.value = "all";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }
  const status = documentRoot.querySelector("#finder-status");
  if (status) status.textContent = state.printPreview.message || "";
}

function chatHomeTemplate() {
  const statusText = onboardingStatusText();
  const unread = unreadNotifications();
  const notificationPreview = latestNotificationPreview();
  return `
    <section class="chat-home" aria-label="MS2.0 chat home">
      <header class="home-header">
        <div class="brand-lockup">
          <span class="brand-mark">MS2.0</span>
          <span>Pharmacy operating intelligence</span>
        </div>
      </header>
      <button class="conversation-row" type="button" data-action="open-chat" data-workspace="operations" aria-label="Open MS2.0 Operations">
        <span class="assistant-avatar">M</span>
        <span class="conversation-copy">
          <strong>MS2.0 Assistant</strong>
          <small>${statusText}</small>
          <span>${state.onboarding.completed ? pharmacyBrain.catalog.length ? "Sales, scans, invoices, reports, and approvals." : "Add your medicine catalog to begin." : "Set up your pharmacy to begin."}</span>
        </span>
        <span class="row-arrow">Open</span>
      </button>
      <button class="conversation-row notifications-row" type="button" data-action="open-chat" data-workspace="notifications" aria-label="Open notifications">
        <span class="assistant-avatar notification-avatar">${unread}</span>
        <span class="conversation-copy">
          <strong>Notifications</strong>
          <small>${unread ? `${unread} unread` : "Quiet"}</small>
          <span>${escapeHtml(notificationPreview)}</span>
        </span>
        <span class="row-arrow">Open</span>
      </button>
      <button class="conversation-row" type="button" data-action="open-payment-queue" aria-label="Open Payment Queue">
        <span class="assistant-avatar">P</span>
        <span class="conversation-copy">
          <strong>Payment Queue</strong>
          <small>${transactionEngine.pending().length} waiting</small>
          <span>Keep serving while payment confirmation is pending.</span>
        </span>
        <span class="row-arrow">Open</span>
      </button>
    </section>
  `;
}

function paymentQueueScreenTemplate() {
  const settings = transactionEngine.settings();
  const simulatorMode = settings.environment !== "production";
  const pending = transactionEngine.pending();
  const recent = transactionEngine.list().slice(-10).reverse();
  return `
    <section class="chat-screen" aria-label="Payment Queue">
      <header class="chat-header">
        <button class="icon-button" type="button" data-action="back-home" aria-label="Back">&lt;</button>
        <span class="assistant-avatar">P</span>
        <span class="chat-title"><strong>Payment Queue</strong><small>${pending.length} waiting${simulatorMode ? " · Simulator only" : ""}</small></span>
      </header>
      <section class="chat-body payment-queue-body" id="paymentQueueBody">
        <article class="operation-card payment-setup-card">
          <p class="card-eyebrow">Transaction completion</p>
          <h2>Choose how sales complete</h2>
          <p>${simulatorMode ? "No real payment is requested in simulator mode." : "Electronic payments complete automatically after an authenticated provider event."}</p>
          <div class="card-actions">
            <button data-action="set-completion-mode" data-mode="always_fast_record" class="${settings.completionMode === "always_fast_record" ? "selected" : ""}">Fast Record</button>
            <button data-action="set-completion-mode" data-mode="request_verify" class="${settings.completionMode === "request_verify" ? "selected" : ""}">Request &amp; Verify</button>
          </div>
        </article>
        ${pending.length ? pending.map(paymentQueueItemTemplate).join("") : '<article class="operation-card"><h2>No payments waiting</h2><p>New pending requests will appear here without blocking the next sale.</p></article>'}
        ${recent.length ? `<article class="operation-card"><p class="card-eyebrow">Recent by pharmacy day</p>${recent.map(paymentHistoryLineTemplate).join("")}</article>` : ""}
      </section>
    </section>`;
}

function paymentQueueItemTemplate(item) {
  const simulatorMode = transactionEngine.settings().environment !== "production";
  return `<article class="operation-card payment-queue-item production-sale-card">
    ${productionSaleCardBody(saleFieldsFromTransaction(item), `${transactionDayLabel(item)} · ${item.saleLabel || "Transaction"}`)}
    <p class="sale-consequence">Serving can continue. Stock changes only after verified payment.</p>
    ${simulatorMode ? `<div class="card-actions">
      <button data-action="simulate-payment-result" data-transaction-id="${escapeHtml(item.id)}" data-status="confirmed">Simulate paid</button>
      <button data-action="simulate-payment-result" data-transaction-id="${escapeHtml(item.id)}" data-status="failed">Simulate failed</button>
    </div>` : ""}
  </article>`;
}

function paymentHistoryLineTemplate(item) {
  const medicine = item.metadata?.medicine || "Payment";
  const quantity = Number(item.metadata?.quantity || 0);
  return `<p><strong>${escapeHtml(transactionDayLabel(item))} · ${escapeHtml(item.saleLabel || item.kind)}</strong> · ${escapeHtml(medicine)} x${quantity} · ${escapeHtml(paymentAmountLabel(item.amount))} · ${escapeHtml(paymentLabel(item.paymentMethod))} · ${escapeHtml(item.status)}</p>`;
}

function paymentAmountLabel(amount) {
  const value = Number(amount);
  if (!Number.isFinite(value) || value < 0) return "Amount unavailable";
  return `KES ${value.toLocaleString("en-KE", { maximumFractionDigits: 2 })}`;
}

function transactionDayLabel(item) {
  return item.businessDay === transactionEngine.businessDay() ? "Today" : item.businessDay || "Previous day";
}

function chatScreenTemplate() {
  const isNotifications = state.ui.workspace === "notifications";
  return `
    <section class="chat-screen" aria-label="${isNotifications ? "MS2.0 notifications conversation" : "MS2.0 assistant conversation"}">
      <header class="chat-header">
        <button class="icon-button" type="button" data-action="back-home" aria-label="Back to chat home">&lt;</button>
        <span class="assistant-avatar">M</span>
        <span class="chat-title">
          <strong>${isNotifications ? "Notifications" : "MS2.0"}</strong>
          <small>${state.sync.online ? "Online" : "Offline"} / ${isNotifications ? `${unreadNotifications()} unread` : onboardingStatusText()}</small>
        </span>
        ${isNotifications ? "" : `
          <button class="icon-button header-catalog-action" type="button" data-action="open-catalog" aria-label="Open Pharmacy Catalog" title="Open Pharmacy Catalog">
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M5 4.5h12a2 2 0 0 1 2 2v12H7a2 2 0 0 1-2-2v-12Zm2 0v12h12M9.5 8h6M9.5 11.5h6" />
            </svg>
          </button>
        `}
        ${adminMenuTemplate()}
      </header>
      <section class="chat-body" id="chatBody" aria-label="Messages">
        <div class="message-list">
          ${chatMessageTemplates()}
          ${isNotifications ? "" : state.cards.map(safeCardTemplate).join("")}
        </div>
      </section>
      ${isNotifications ? notificationsFooterTemplate() : composerTemplate()}
    </section>
  `;
}

function chatMessageTemplates() {
  if (state.ui.workspace === "notifications") {
    const intro = {
      id: "notifications-intro",
      type: "system",
      text: "Notifications stay here, separate from daily sales.",
      time: "Now"
    };
    const cards = activeNotificationCards();
    return [intro].map(feedItemTemplate).join("") + cards.map(safeCardTemplate).join("");
  }
  const intro = {
    id: "intro",
    type: "system",
    text: state.onboarding.completed
      ? pharmacyBrain.catalog.length
        ? `${greetingText()} How can I help today?`
        : "Let's add your medicines quickly. How would you like to show me your pharmacy?"
      : "Welcome. Let's set up your pharmacy first.",
    time: "Now"
  };
  return [intro, ...state.feed].map(feedItemTemplate).join("");
}

function feedItemTemplate(item) {
  if (item.type === "owner") {
    return `
      <button class="message-bubble owner reusable-command" type="button" data-action="reuse-command" data-command="${escapeHtml(item.text)}" aria-label="Use this command again">
        <p>${escapeHtml(item.text)}</p>
        <span>You / ${escapeHtml(item.time)} · Tap to use again</span>
      </button>
    `;
  }
  if (item.adjustmentReference) {
    const reference = item.adjustmentReference;
    const typeLabel = adjustmentTypeLabel(reference.type);
    return `
      <button class="message-bubble system completed-sale-receipt" type="button" data-action="open-sale-adjustment"
        data-adjustment-id="${escapeHtml(reference.adjustmentId || "")}"
        aria-label="Open ${escapeHtml(typeLabel)} for Sale ${escapeHtml(reference.saleNumber || "")}">
        ${reference.saleNumber ? `<p class="adjustment-receipt-copy"><strong>${escapeHtml(typeLabel)} for Sale ${escapeHtml(reference.saleNumber)}</strong>
          <small>${escapeHtml(typeLabel)} record #${escapeHtml(reference.recordNumber)}</small>
          <span>${escapeHtml(reference.medicine)} x${escapeHtml(reference.quantity)}</span>
          <span>${escapeHtml(adjustmentMoneyResult(reference))}</span>
          <span>Stock added back: ${escapeHtml(reference.stockAddedBack)}</span></p>` : `<p>${escapeHtml(item.text)}</p>`}
        <span>MS2.0 / ${escapeHtml(item.time)} · Tap to open adjustment</span>
      </button>
    `;
  }
  const saleReference = item.saleReference || saleReferenceFromReceipt(item.text);
  if (saleReference) {
    return `
      <button class="message-bubble system completed-sale-receipt" type="button" data-action="open-completed-sale"
        data-sale-number="${escapeHtml(String(saleReference.saleNumber || ""))}"
        data-transaction-id="${escapeHtml(String(saleReference.transactionId || ""))}"
        aria-label="Open completed Sale ${escapeHtml(String(saleReference.saleNumber || ""))}">
        <p>${escapeHtml(item.text)}</p>
        <span>MS2.0 / ${escapeHtml(item.time)} · Tap to open sale</span>
      </button>
    `;
  }
  return `
    <article class="message-bubble ${item.type}" aria-label="MS2.0 message">
      <p>${escapeHtml(item.text)}</p>
      <span>MS2.0 / ${escapeHtml(item.time)}</span>
    </article>
  `;
}

function composerTemplate() {
  const voiceBusy = state.voice.starting || state.voice.listening;
  const voiceLabel = state.voice.starting ? "Wait" : state.voice.listening ? "Speak" : "Mic";
  return `
    <footer class="chat-composer" aria-label="Message composer">
      <details class="attach-menu">
        <summary aria-label="Open quick actions">+</summary>
        <div class="attach-sheet">
          <button type="button" data-action="take-photo">Camera</button>
          <button type="button" data-action="upload-photo">Photo library</button>
          <button type="button" data-action="choose-shelf-photo-method">Shelf photo</button>
          <button type="button" data-action="upload-document">File</button>
          <button type="button" data-action="capture-invoice">Invoice</button>
          <button type="button" data-action="scan-barcode">Scan barcode</button>
          <button type="button" data-action="start-catalog-paste">Paste list</button>
          <button type="button" data-action="demo-stock-correction">Stock fix</button>
          <button type="button" data-action="demo-report">Report</button>
          <button type="button" data-action="open-export-hub">Export Hub</button>
          <button type="button" data-action="demo-onboarding">Setup</button>
        </div>
      </details>
      <form class="message-form" id="commandForm">
        <input id="commandInput" type="text" autocomplete="off" inputmode="text" placeholder="Message MS2.0">
        <button class="icon-button ${voiceBusy ? "listening" : ""}" type="button" data-action="start-voice" aria-label="${state.voice.starting ? "Starting microphone" : state.voice.listening ? "Speak now" : "Use voice"}" ${voiceBusy ? "disabled" : ""}>
          ${voiceLabel}
        </button>
        <button class="send-button" type="submit">Send</button>
      </form>
      ${state.voice.status ? `<p class="composer-hint">${escapeHtml(state.voice.status)}</p>` : ""}
      <input id="photoInput" class="hidden-input" type="file" accept="image/*">
      <input id="cameraInput" class="hidden-input" type="file" accept="image/*" capture="environment">
      <input id="documentInput" class="hidden-input" type="file" accept=".csv,.txt,.tsv,.xls,.xlsx,.pdf,image/*,text/csv,text/plain">
      <input id="stockFixFileInput" class="hidden-input" type="file" accept="image/*">
    </footer>
  `;
}

function cameraOverlayTemplate() {
  if (!state.camera.open) return "";
  return `
    <section class="camera-overlay" aria-label="MS2.0 camera">
      <div class="camera-panel">
        <h2>${state.camera.scanType === "invoice" ? "Photograph invoice" : state.camera.scanType === "barcode" ? "Scan barcode" : state.camera.scanType === "shelf_photo" ? "Photograph shelf" : "Photograph medicine"}</h2>
        <p>${state.camera.scanType === "barcode" ? "Keep one barcode clear inside the frame, then tap Capture." : state.camera.scanType === "shelf_photo" ? "Show the whole medicine packs and shelf label. Keep the words clear. Hold the phone still. Keep bright light off the packs or screen." : "Keep the whole item clear inside the frame."}</p>
        ${state.camera.capturedUrl
          ? `<img class="camera-captured-preview" src="${escapeHtml(state.camera.capturedUrl)}" alt="Captured photo preview">`
          : `<video id="ms20CameraPreview" autoplay muted playsinline></video>`}
        <p class="camera-status" aria-live="polite">${escapeHtml(state.camera.status)}</p>
        <div class="camera-actions">
          <button type="button" data-action="close-camera">Cancel</button>
          ${state.camera.capturedUrl
            ? `<button type="button" data-action="retake-camera-photo">Retake</button>${state.camera.retryRequired ? "" : '<button class="primary-action" type="button" data-action="use-camera-photo">Use photo</button>'}`
            : `${state.camera.lightAvailable ? `<button type="button" data-action="toggle-camera-light">${state.camera.lightOn ? "Light off" : "Light on"}</button>` : ""}<button class="primary-action" type="button" data-action="capture-camera-frame">Capture</button>`}
        </div>
      </div>
    </section>
  `;
}

function shelfAcquisitionTemplate() {
  if (!state.shelfAcquisitionOpen) return "";
  return `
    <section class="camera-overlay" aria-label="Choose shelf photo source">
      <div class="camera-panel acquisition-panel">
        <h2>Add shelf photo</h2>
        <p>Take a new shelf photo now, or choose one already saved on this phone.</p>
        <div class="camera-actions acquisition-actions">
          <button type="button" data-action="cancel-shelf-photo">Cancel</button>
          <button type="button" data-action="choose-shelf-photo">Choose from phone</button>
          <button class="primary-action" type="button" data-action="take-shelf-photo">Take photo</button>
        </div>
      </div>
    </section>`;
}

function notificationsFooterTemplate() {
  return `
    <footer class="chat-composer notification-footer" aria-label="Notifications controls">
      <button type="button" data-action="back-home">Back</button>
      <button type="button" data-action="mark-notifications-read">Mark read</button>
    </footer>
  `;
}

function adminMenuTemplate() {
  const onlineText = state.sync.online ? "Online" : "Offline";
  const live = state.liveBackend || {};
  const readiness = live.readinessSummary || {};
  const offlineSlot = resolveOfflineSlot(state.liveBackend);
  return `
    <details class="admin-menu">
      <summary aria-label="Open settings">Menu</summary>
      <div class="admin-sheet">
        <strong>Settings, diagnostics, and admin</strong>
        <div class="diagnostic-grid">
          <span class="status-pill ${state.sync.online ? "ok" : "warn"}">${onlineText}</span>
          <span class="status-pill ${live.health?.ok ? "ok" : "warn"}">Backend: ${live.health?.ok ? "OK" : "Check"}</span>
          <span class="status-pill ${readiness.sheets ? "ok" : "warn"}">Sheets: ${readiness.sheets ? "OK" : "Check"}</span>
          <span class="status-pill ${readiness.baileys ? "ok" : "warn"}">Baileys: ${readiness.baileys ? "OK" : "Check"}</span>
          <span class="status-pill">Queue: ${state.sync.pending}</span>
        </div>
        <div class="admin-actions">
          <button type="button" data-action="refresh-live-status">Check system</button>
          <button type="button" data-action="sync-now">Sync ${queue.pendingCount()}</button>
          <button type="button" data-action="demo-sync">Sync review</button>
          <button type="button" data-action="reset-onboarding">Reset setup</button>
          <a class="button-link" href="${escapeHtml(offlineSlot.url)}" target="_blank" rel="noreferrer">Offline app</a>
        </div>
        <details class="developer-mode">
          <summary>Developer mode</summary>
          <div class="contract-grid">
            <pre>${escapeHtml(JSON.stringify(TokenPolicy, null, 2))}</pre>
            <pre>${escapeHtml(JSON.stringify(CloudMemoryContract, null, 2))}</pre>
            <pre>${escapeHtml(JSON.stringify(IntelligenceSeparationContract, null, 2))}</pre>
            <pre>${escapeHtml(JSON.stringify(WorkspaceContract, null, 2))}</pre>
            <pre>${escapeHtml(JSON.stringify(listRouteSlots(state.liveBackend), null, 2))}</pre>
          </div>
        </details>
      </div>
    </details>
  `;
}

function cardTemplate(card) {
  if (card.type === "ExportHubCard") return exportHubCardTemplate(card);
  if (card.type === "ActivityHubCard") return activityHubCardTemplate(card);
  if (card.type === "CompletedSaleDetailCard") return completedSaleDetailCardTemplate(card);
  if (card.type === "SaleAdjustmentReviewCard") return saleAdjustmentReviewCardTemplate(card);
  if (card.type === "SaleAdjustmentDetailCard") return saleAdjustmentDetailCardTemplate(card);
  const fields = cardFieldsFor(card.type);
  const displayed = fields.length ? fields : Object.keys(card.fields || {});
  const progressiveMedicine = PROGRESSIVE_MEDICINE_CARD_TYPES.has(card.type);
  const note = ownerCardNote(card);
  const noteBeforeBody = (["CatalogImportCard", "VisualScanCard", "PhotoReviewCard"].includes(card.type)
    || card.voiceSource === true)
    && Boolean(String(card.fields?.review_feedback || "").trim());
  return `
    <article class="card-message ${card.status}" data-card-id="${card.id}">
      <div class="card-top">
        <span class="card-heading">
          <span class="card-type">${escapeHtml(friendlyCardLabel(card))}</span>
          <strong>${escapeHtml(card.title)}</strong>
        </span>
        <span class="card-top-actions">
          ${cardFontControlsTemplate()}
          ${cardCloseButtonTemplate(card, "top")}
        </span>
      </div>
      ${noteBeforeBody ? `<p class="card-note card-note-before-review">${escapeHtml(note)}</p>` : ""}
      ${cardBodyTemplate(card, displayed)}
      ${card.type === "StockCorrectionCard" && card.voiceTranscripts?.length ? `<section class="stock-fix-voice-transcript" aria-label="Voice transcript"><strong>Voice transcript</strong>${card.voiceTranscripts.map((entry, index) => `<p>${index + 1}. ${escapeHtml(entry)}</p>`).join("")}</section>` : ""}
      ${!progressiveMedicine && card.type === "RestockCard" ? quantityToolbar(card) : ""}
      ${noteBeforeBody ? "" : `<p class="card-note" data-card-note="${card.id}">${escapeHtml(note)}</p>`}
      ${progressiveMedicine || card.type === "SaleCard" ? "" : activeActionsTemplate(card)}
      <details class="card-technical">
        <summary>Details</summary>
        ${card.source ? `<p>From: ${escapeHtml(card.source)}</p>` : ""}
        <p>Type: ${escapeHtml(card.type)}. Confidence: ${Math.round((card.confidence || 0) * 100)}%.</p>
        ${card.parser ? `<p>Parser: ${escapeHtml(card.parser)}</p>` : ""}
        ${card.integration ? `<p>${escapeHtml(card.integration.summary)}</p>` : ""}
        ${card.validation ? `<p>${escapeHtml(card.validation)}</p>` : ""}
      </details>
      <div class="card-bottom-close">
        ${cardCloseButtonTemplate(card, "bottom")}
      </div>
    </article>
  `;
}

function completedSaleDetailCardTemplate(card) {
  const fields = card.fields || {};
  const linked = saleAdjustmentEngine.list().filter((item) => item.original_transaction_id === fields.transaction_id);
  const adjustmentsBlocked = fields.adjustment_available === false;
  return `
    <article class="card-message ready sale-detail-card" data-card-id="${escapeHtml(card.id)}">
      <div class="card-top">
        <span class="card-heading"><span class="card-type">Completed sale</span><strong>${escapeHtml(card.title)}</strong></span>
        ${cardCloseButtonTemplate(card, "top")}
      </div>
      ${saleDetailList([
        ["Medicine", fields.medicine],
        ["Form", fields.form],
        ["Unit", fields.unit],
        ["Quantity sold", fields.quantity],
        ["Unit price", fields.unit_price ? `KES ${fields.unit_price}` : ""],
        ["Total", fields.total ? `KES ${fields.total}` : ""],
        ["Payment", paymentLabel(fields.payment || "")],
        ["Stock after sale", fields.stock_after_sale],
        ["Status", fields.status]
      ])}
      <p class="card-note">${adjustmentsBlocked
        ? escapeHtml(fields.adjustment_block_message)
        : `Choose one adjustment. The original Sale ${escapeHtml(String(fields.sale_number))} remains in history. Nothing changes until a later confirmation.`}</p>
      <div class="card-actions sale-adjustment-actions" aria-label="Sale adjustment options">
        <button type="button" data-action="start-sale-adjustment" data-card-id="${escapeHtml(card.id)}" data-adjustment-type="refund" ${adjustmentsBlocked ? "disabled" : ""}>Refund</button>
        <button type="button" data-action="start-sale-adjustment" data-card-id="${escapeHtml(card.id)}" data-adjustment-type="return" ${adjustmentsBlocked ? "disabled" : ""}>Return</button>
        <button type="button" data-action="start-sale-adjustment" data-card-id="${escapeHtml(card.id)}" data-adjustment-type="credit" ${adjustmentsBlocked ? "disabled" : ""}>Credit</button>
      </div>
      ${linked.length ? `<section class="linked-adjustments"><strong>Linked adjustments</strong>${linked.map((item) =>
        `<button type="button" data-action="open-sale-adjustment" data-adjustment-id="${escapeHtml(item.id)}">${escapeHtml(adjustmentTypeLabel(item.adjustment_type))} for Sale ${fields.sale_number}<small>Record #${item.adjustment_number} · KES ${item.financial_adjustment}</small></button>`
      ).join("")}</section>` : ""}
      <div class="card-bottom-close">${cardCloseButtonTemplate(card, "bottom")}</div>
    </article>
  `;
}

function saleAdjustmentReviewCardTemplate(card) {
  const fields = card.fields || {};
  const typeLabel = String(fields.adjustment_type || "adjustment").replace(/^./, (letter) => letter.toUpperCase());
  const adjustmentQuantity = Number(fields.adjustment_quantity || 0);
  const remainingQuantity = Number(fields.remaining_quantity || 0);
  const remainingAfter = Math.max(0, remainingQuantity - adjustmentQuantity);
  return `
    <article class="card-message ready sale-adjustment-review-card" data-card-id="${escapeHtml(card.id)}">
      <div class="card-top">
        <span class="card-heading"><span class="card-type">${escapeHtml(typeLabel)} review</span><strong>${escapeHtml(card.title)}</strong></span>
        ${cardCloseButtonTemplate(card, "top")}
      </div>
      ${saleDetailList([
        ["Original sale", `Sale ${fields.original_sale_number}`],
        ["Medicine", fields.medicine],
        ["Unit", fields.unit],
        ["Quantity sold", fields.sold_quantity],
        ["Previously adjusted", String(fields.previously_adjusted_quantity ?? 0)],
        ["Remaining before this adjustment", String(remainingQuantity)],
        ["Quantity to adjust", fields.adjustment_quantity],
        ["Remaining after confirmation", String(remainingAfter)],
        ["Unit price", fields.unit_price ? `KES ${fields.unit_price}` : ""],
        [fields.adjustment_type === "credit" ? "Account credit" : "Money back", `KES ${fields.financial_adjustment}`],
        ["Stock added back", String(fields.stock_to_restore ?? 0)],
        ["Payment impact", fields.payment_impact],
        ["Original sale", fields.original_sale_status]
      ])}
      <div class="quantity-toolbar" aria-label="Adjustment quantity">
        <button type="button" data-action="bump-sale-adjustment" data-card-id="${escapeHtml(card.id)}" data-delta="-1" aria-label="Reduce adjustment quantity" ${adjustmentQuantity <= 1 ? "disabled" : ""}>-1</button>
        <button type="button" data-action="bump-sale-adjustment" data-card-id="${escapeHtml(card.id)}" data-delta="1" aria-label="Increase adjustment quantity" ${adjustmentQuantity >= remainingQuantity ? "disabled" : ""}>+1</button>
      </div>
      ${fields.adjustment_type === "refund" ? `<fieldset class="refund-stock-choice"><legend>Should this medicine go back into stock?</legend>
        <button type="button" data-action="set-refund-stock" data-card-id="${escapeHtml(card.id)}" data-restore-stock="false" aria-pressed="${!fields.restore_stock}"><span aria-hidden="true">✓</span> Money only</button>
        <button type="button" data-action="set-refund-stock" data-card-id="${escapeHtml(card.id)}" data-restore-stock="true" aria-pressed="${fields.restore_stock}"><span aria-hidden="true">✓</span> Money back + medicine back in stock</button>
      </fieldset>` : ""}
      <p class="card-note">${escapeHtml(fields.review_status)}. The original sale has not been deleted or edited.</p>
      <div class="card-actions">
        <button type="button" data-action="dismiss-card" data-card-id="${escapeHtml(card.id)}">Cancel review</button>
        <button type="button" data-action="confirm-sale-adjustment" data-card-id="${escapeHtml(card.id)}">Confirm ${escapeHtml(typeLabel)}</button>
      </div>
    </article>
  `;
}

function saleAdjustmentDetailCardTemplate(card) {
  const fields = card.fields || {};
  const typeLabel = String(fields.adjustment_type || "adjustment").replace(/^./, (letter) => letter.toUpperCase());
  return `
    <article class="card-message ready sale-adjustment-review-card" data-card-id="${escapeHtml(card.id)}">
      <div class="card-top"><span class="card-heading"><span class="card-type">Completed ${escapeHtml(typeLabel)} · ${escapeHtml(typeLabel)} record #${fields.adjustment_number}</span><strong>${escapeHtml(typeLabel)} for Sale ${fields.original_sale_number}</strong></span>${cardCloseButtonTemplate(card, "top")}</div>
      ${saleDetailList([
        ["Original sale", `Sale ${fields.original_sale_number}`],
        ["Medicine", fields.medicine], ["Unit", fields.unit],
        ["Quantity adjusted", fields.adjustment_quantity],
        [fields.adjustment_type === "credit" ? "Account credit" : "Money back", `KES ${fields.financial_adjustment}`],
        ["Stock added back", String(fields.stock_to_restore ?? 0)],
        ["Payment impact", fields.payment_impact],
        ["Status", fields.status],
        ["Confirmed", fields.confirmed_at],
        ["Staff", fields.staff_identity]
      ])}
      <p class="card-note">This permanent adjustment is linked to the immutable original sale.</p>
      <div class="card-actions">
        <button type="button" data-action="open-adjustment-original" data-sale-number="${fields.original_sale_number}" data-transaction-id="${escapeHtml(fields.original_transaction_id)}">Open original Sale ${fields.original_sale_number}</button>
      </div>
    </article>`;
}

function safeCardTemplate(card) {
  try {
    return cardTemplate(card);
  } catch (error) {
    console.error("MS2.0 isolated an unreadable review card", card?.id, error);
    return `
      <article class="card-message needs_correction" data-card-id="${escapeHtml(card?.id || "unreadable-card")}">
        <div class="card-top">
          <span class="card-heading"><span class="card-type">Review</span><strong>Draft could not be displayed</strong></span>
          ${cardCloseButtonTemplate(card || { id: "", type: "ReviewCard" }, "top")}
        </div>
        <p class="card-note">Your saved Pharmacy Catalog is unchanged. Close this unreadable draft and reopen the workflow.</p>
        <div class="card-bottom-close">${cardCloseButtonTemplate(card || { id: "", type: "ReviewCard" }, "bottom")}</div>
      </article>
    `;
  }
}

function cardCloseButtonTemplate(card, placement) {
  if (card.type === "ExportHubCard" || card.type === "ActivityHubCard") return "";
  const label = `Close ${friendlyCardLabel(card)} card`;
  return `<button class="card-close-button ${placement === "bottom" ? "card-close-button-bottom" : ""}" type="button" data-action="dismiss-card" data-card-id="${card.id}" aria-label="${escapeHtml(label)}">x</button>`;
}

function cardBodyTemplate(card, displayed) {
  if (card.type === "SaleCard") return productionSaleCardBody(card.fields, card.voiceSource ? "Voice sale review" : "Sale review", card);
  if (card.type === "CatalogWorkspaceCard") return catalogWorkspaceTemplate(card);
  if (card.type === "CatalogOnboardingCard") {
    return `
      <div class="catalog-onboarding-prompt">
        <p>${escapeHtml(card.fields?.question || "How would you like to show me your pharmacy?")}</p>
        <span>Choose one option below. MS2.0 will prepare a review card before saving anything.</span>
      </div>
    `;
  }
  if (card.type === "CatalogImportCard" && card.fields?.entry_mode === "paste_input") {
    return `
      <div class="catalog-paste-input">
        ${fieldTemplate(card, "items_text")}
        ${catalogPasteAcquisitionTemplate(card)}
        <p>Paste one medicine per line. Nothing is saved until you review and approve the parsed rows.</p>
      </div>
    `;
  }
  if (card.type === "CatalogImportCard" && card.fields?.entry_mode === "no_changes") {
    return `<div class="catalog-import-no-changes"><p>${escapeHtml(card.fields?.review_feedback || card.validation || "No new medicines found. Nothing was saved.")}</p></div>`;
  }
  if (card.type === "NotificationCard") return notificationCardBodyTemplate(card);
  if (card.type === "CatalogImportCard") {
    return catalogImportTableTemplate(card);
  }
  if (card.type === "CatalogWorkspaceCard") {
    return `
      <div class="card-actions">
        <button data-action="export-catalog-csv">Export CSV</button>
        <button data-action="dismiss-card" data-card-id="${card.id}">Close catalog</button>
      </div>
    `;
  }
  if (MEDICINE_DETAIL_CARD_TYPES.has(card.type)) {
    return medicineDetailTemplate(card, displayed);
  }
  return `
    <div class="field-grid">
      ${displayed.map((field) => fieldTemplate(card, field)).join("")}
    </div>
  `;
}

function productionSaleCardBody(fields = {}, eyebrow = "Sale", card = null) {
  const editable = Boolean(card);
  const activeSlide = Math.max(0, Math.min(2, Number(card?.ui?.activeSlide || 0)));
  const correcting = editable && Boolean(card.ui?.editing);
  const value = (field) => escapeHtml(String(fields[field] ?? ""));
  const fact = (name, label) => `<div class="sale-compact-fact"><span>${label}</span><strong>${value(name) || "Unknown"}</strong></div>`;
  const editField = (name, label, inputMode = "") => saleEditableFieldTemplate(card, name, label, fields[name], inputMode);
  const fast = `${correcting ? `<p class="sale-edit-guidance" role="status">${escapeHtml(card.fields?.voice_feedback || "Correct only what is wrong. Every field uses the shared Catalog Mic.")}</p>
    <div class="production-sale-primary production-sale-edit-grid">
      ${editField("medicine", "Medicine")}${editField("form", "Exact form")}${editField("unit", "Selling unit")}
      ${card.saleIssues?.includes("pack_conversion_unknown") ? editField("pack_conversion", `How many ${pluralOwnerUnit(fields.base_stock_unit)} are in one ${fields.unit || "pack"}?`, "decimal") : ""}
      ${editField("selling_price", "Unit price (KES)", "decimal")}${editField("quantity", "Quantity", "decimal")}${editField("payment", "Payment")}
    </div>` : `<div class="sale-approval-grid">
      ${fact("selling_price", "Unit price")}${fact("quantity", "Quantity")}${fact("expected_total", "Total")}${fact("payment", "Payment")}
    </div><div class="sale-stock-strip"><span>Stock</span><strong>${value("stock_before") || "Unknown"} → ${value("stock_after") || "Unknown"}</strong><small>${value("sale_status") || "Review before recording"}</small></div>`}
    ${editable ? quantityToolbar(card) + paymentToolbar(card) + activeActionsTemplate(card) : ""}`;
  const stock = correcting ? `<div class="production-sale-primary production-sale-edit-grid">
    ${editField("current_stock", "Current stock", "decimal")}${editField("strength", "Strength")}
    ${editField("form", "Form")}${editField("unit", "Requested selling unit")}${editField("cost_price", "Buying price (KES)", "decimal")}
  </div>` : saleDetailList([["Current stock", fields.current_stock], ["Strength", fields.strength], ["Form", fields.form], ["Base unit", fields.base_stock_unit], ["Requested selling unit", fields.unit], ["Buying price", fields.cost_price]]);
  const trace = correcting ? `<div class="production-sale-primary production-sale-edit-grid">
    ${editField("supplier", "Supplier")}${editField("barcode", "Barcode")}${editField("batch", "Batch")}
    ${editField("expiry", "Expiry")}${editField("aliases", "Aliases")}${editField("note", "Note")}
  </div>` : saleDetailList([["Supplier", fields.supplier], ["Barcode", fields.barcode], ["Batch", fields.batch], ["Expiry", fields.expiry], ["Aliases", fields.aliases], ["Notes", fields.note]]);
  return `<section class="production-sale-card-body medicine-review-workspace" data-medicine-workspace="${card?.id || ""}" aria-label="Production Sales Card">
    <p class="card-eyebrow">${escapeHtml(eyebrow)}</p>
    <p class="sale-summary" data-sale-summary="${card?.id || ""}">${escapeHtml(productionSaleSummary(fields))}</p>
    ${card?.fields?.transcript ? `<p class="sale-transcript">Heard: “${escapeHtml(card.fields.transcript)}”</p>` : ""}
    ${editable ? `<div class="medicine-slide-nav" aria-label="Sale review sections">
      <button type="button" class="${activeSlide === 0 ? "selected" : ""}" data-action="show-medicine-slide" data-card-id="${card.id}" data-slide="0">Fast action</button>
      <button type="button" class="${activeSlide === 1 ? "selected" : ""}" data-action="show-medicine-slide" data-card-id="${card.id}" data-slide="1">Stock &amp; details</button>
      <button type="button" class="${activeSlide === 2 ? "selected" : ""}" data-action="show-medicine-slide" data-card-id="${card.id}" data-slide="2">Traceability</button>
    </div><div class="medicine-slide-status"><span data-medicine-slide-indicator="${card.id}">${activeSlide + 1} of 3</span><span>Summary first; details on demand</span></div>
    <div class="medicine-slide-track" data-medicine-carousel="${card.id}" data-initial-slide="${activeSlide}">
      <section class="medicine-slide medicine-slide-fast" aria-label="Fast action">${fast}</section>
      <section class="medicine-slide" aria-label="Stock and details">${stock}</section>
      <section class="medicine-slide" aria-label="Traceability">${trace}</section>
    </div>` : fast}
  </section>`;
}

function notificationCardBodyTemplate(card) {
  return `
    <div class="field-grid notification-details">
      ${["category", "message", "status"].map((field) => fieldTemplate(card, field)).join("")}
    </div>
  `;
}

function pluralOwnerUnit(value) {
  const unit = String(value || "stock unit").trim();
  if (/(s|x|z|ch|sh)$/i.test(unit)) return `${unit}es`;
  if (/[^aeiou]y$/i.test(unit)) return `${unit.slice(0, -1)}ies`;
  return `${unit}s`;
}

function saleDetailList(entries) {
  return `<dl class="sale-detail-list">${entries.map(([label, entry]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(String(entry || "Not recorded"))}</dd></div>`).join("")}</dl>`;
}

function contextualEditableFieldTemplate(card, field, label, value = "", inputMode = "", action = "sale-edit-field-voice", catalog = false) {
  const options = ["form", "unit"].includes(field) ? card.saleOptions?.[`${field}s`] : [];
  const fieldAttribute = catalog ? `data-catalog-edit-field="${field}"` : `data-field="${field}"`;
  const control = options?.length > 1
    ? `<select data-card-id="${card.id}" ${fieldAttribute}><option value="">Choose exact ${field}</option>${options.map((option) => `<option ${String(value) === option ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}</select>`
    : `<input data-card-id="${card.id}" ${fieldAttribute} ${inputMode ? `inputmode="${inputMode}"` : ""} value="${escapeHtml(String(value ?? ""))}">`;
  return `<div class="catalog-edit-field sale-edit-field">
    <div class="catalog-edit-field-heading">
      <label>${escapeHtml(label)}</label>
      <button type="button" data-action="${action}" data-card-id="${card.id}" data-field="${field}" aria-label="Speak ${escapeHtml(label)}" ${state.voice.starting || state.voice.listening ? "disabled" : ""}>Mic</button>
    </div>${control}
  </div>`;
}

function saleEditableFieldTemplate(card, field, label, value = "", inputMode = "") {
  return contextualEditableFieldTemplate(card, field, label, value, inputMode);
}

function catalogWorkspaceTemplate(card) {
  const query = card.fields?.query || "";
  const items = catalogWorkspaceItems(pharmacyBrain.catalog, query);
  return `
    <section class="catalog-workspace" aria-label="Complete pharmacy catalog">
      <div class="catalog-workspace-summary">
        <strong>${pharmacyBrain.catalog.length} medicines</strong>
        <span>Saved in this pharmacy</span>
      </div>
      ${catalogSearchTemplate(card, query, "top")}
      <p class="catalog-result-count">Showing ${items.length} of ${pharmacyBrain.catalog.length}</p>
      ${card.fields?.selected_id ? catalogMedicineEditorTemplate(card) : `<div class="catalog-workspace-list">
        ${items.length ? items.map(catalogWorkspaceItemTemplate).join("") : `<p class="catalog-empty">${pharmacyBrain.catalog.length ? "No medicines match this search." : "No medicines have been saved in this pharmacy yet."}</p>`}
      </div>
      ${catalogSearchTemplate(card, query, "bottom")}
      <p class="catalog-result-count catalog-result-count-bottom">Showing ${items.length} of ${pharmacyBrain.catalog.length}</p>`}
    </section>
  `;
}

function catalogSearchTemplate(card, query, placement) {
  const voiceBusy = state.voice.starting || state.voice.listening;
  return `
    <div class="catalog-search catalog-search-${placement}">
      <label for="catalog-search-${card.id}-${placement}">
      <span>${placement === "bottom" ? "Search catalog again" : "Search catalog"}</span>
      </label>
      <div class="catalog-search-control">
        <input id="catalog-search-${card.id}-${placement}" type="search" data-catalog-search data-catalog-search-placement="${placement}" data-card-id="${card.id}" value="${escapeHtml(query)}" placeholder="Medicine, form, supplier, barcode">
        <button type="button" data-action="catalog-search-voice" data-card-id="${card.id}" data-search-placement="${placement}" aria-label="Search catalog by voice" ${voiceBusy ? "disabled" : ""}>${voiceBusy ? "Listening…" : "Mic"}</button>
      </div>
      ${card.fields?.search_voice_feedback ? `<p class="catalog-search-feedback" role="status">${escapeHtml(card.fields.search_voice_feedback)}</p>` : ""}
    </div>
  `;
}

function catalogWorkspaceItemTemplate(item) {
  const name = item.name || item.medicine || "Medicine";
  const form = item.form || item.forms?.[0] || "";
  const unit = item.unit || item.units?.[0] || "";
  const sellingPrice = item.sellingPrice ?? item.selling_price ?? "";
  const stock = item.stockLeft ?? item.stock ?? item.current_stock ?? "";
  const strength = item.strength || "";
  const details = [
    ["Buying price", item.costPrice ?? item.cost_price],
    ["Supplier", item.supplier],
    ["Barcode", item.barcode],
    ["Batch", item.batches?.[0]?.batch || item.batch],
    ["Expiry", item.batches?.[0]?.expiry || item.expiry],
    ["Shelf", item.shelf || item.location]
  ].filter(([, value]) => value !== "" && value !== null && value !== undefined);
  return `
    <article class="catalog-workspace-item">
      <div class="catalog-item-main">
        <div>
          <strong>${escapeHtml(name)}</strong>
          <span>${escapeHtml([strength, form, unit].filter(Boolean).join(" · ") || "Details not recorded")}</span>
        </div>
        <div class="catalog-item-numbers">
          <span><small>Selling</small>${sellingPrice === "" ? "—" : escapeHtml(String(sellingPrice))}</span>
          <span><small>Stock</small>${stock === "" || stock === null ? "—" : escapeHtml(String(stock))}</span>
        </div>
      </div>
      ${details.length ? `<details><summary>More details</summary><dl>${details.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(String(value))}</dd></div>`).join("")}</dl></details>` : ""}
      <button class="catalog-open-medicine" type="button" data-action="open-catalog-medicine" data-medicine-id="${escapeHtml(catalogItemId(item))}">Open &amp; edit</button>
    </article>
  `;
}

function catalogMedicineEditorTemplate(card) {
  const draft = catalogEditDraft(card);
  const review = reviewCatalogEdit(pharmacyBrain.catalog, card.fields.selected_id, draft);
  const presentation = catalogEditPresentation(review);
  const advanced = new Set(["pack_size", "base_stock_unit", "unit_conversions", "unit_prices", "supplier", "shelf", "barcode", "batch", "expiry", "reorder_level", "aliases"]);
  const fields = (showAdvanced) => CATALOG_EDIT_FIELDS
    .filter((field) => advanced.has(field) === showAdvanced)
    .map((field) => contextualEditableFieldTemplate(
      card, field, fieldLabel(field), draft[field],
      ["stock", "selling_price", "cost_price", "reorder_level"].includes(field) ? "decimal" : "",
      "catalog-edit-field-voice", true
    )).join("");
  return `
    <section class="catalog-medicine-editor" aria-label="Edit ${escapeHtml(draft.name || "medicine")}">
      <button class="catalog-back" type="button" data-action="cancel-catalog-edit" data-card-id="${card.id}">&larr; Back to catalog</button>
      <div class="catalog-editor-heading"><div><small>Medicine Action Card</small><h3>${escapeHtml(draft.name || "Medicine")}</h3></div><span data-catalog-edit-status data-state="${presentation.state}">${presentation.status}</span></div>
      <p data-catalog-edit-description>${presentation.description}</p>
      <div class="catalog-edit-voice">
        <button type="button" data-action="catalog-edit-voice" data-card-id="${card.id}" ${state.voice.starting || state.voice.listening ? "disabled" : ""}>${state.voice.starting || state.voice.listening ? "Listening…" : "Mic"}</button>
        <p role="status">${escapeHtml(card.fields?.voice_feedback || (card.fields?.voice_field ? `${fieldLabel(card.fields.voice_field)} selected. Tap Mic and speak the new value.` : "Tap a field, then Mic, and speak the new value."))}</p>
      </div>
      <div class="catalog-edit-grid">${fields(false)}</div>
      <details class="catalog-advanced-fields"><summary>Packaging, supplier and other details</summary><div class="catalog-edit-grid">${fields(true)}</div></details>
      ${review.error ? `<p class="catalog-edit-warning" role="alert">${escapeHtml(review.error)}</p>` : review.changes?.length ? `<p class="catalog-change-summary">Review: ${review.changes.length} field${review.changes.length === 1 ? "" : "s"} changed — ${review.changes.map(fieldLabel).join(", ")}.</p>` : '<p class="catalog-change-summary">No changes yet.</p>'}
      <div class="catalog-edit-actions">
        <button type="button" data-action="approve-catalog-edit" data-card-id="${card.id}" ${review.valid && review.changes?.length ? "" : "disabled"}>Approve &amp; save</button>
        <button type="button" data-action="start-stock-fix" data-medicine-id="${escapeHtml(card.fields.selected_id)}">Stock fix</button>
        <button type="button" data-action="cancel-catalog-edit" data-card-id="${card.id}">Discard</button>
      </div>
    </section>
  `;
}

function fieldTemplate(card, field) {
  const value = card.fields?.[field] ?? "";
  if (card.type === "ReportCard" && field === "report_text") return `${card.reportSelectionDirty ? '<p class="report-retained-notice" role="status">Showing the last successful report below. Refresh to load the selected period.</p>' : ""}<section class="report-result" aria-label="Generated report"><h4>${card.reportSelectionDirty ? "Last successful report" : "Report"}</h4><pre>${escapeHtml(String(value))}</pre></section>`;
  if (card.type === "ReportCard" && field === "period") return reportPeriodTemplate(card, value);
  const longFields = new Set(["items_text", "choices", "notes", "mapping", "message", "action", "missing_columns", "report_text"]);
  const inputMode = inputModeForField(field);
  const control = longFields.has(field)
    ? `<textarea data-card-id="${card.id}" data-field="${field}" rows="${field === "items_text" ? 8 : 3}">${escapeHtml(String(value))}</textarea>`
    : `<input data-card-id="${card.id}" data-field="${field}" ${inputMode ? `inputmode="${inputMode}"` : ""} value="${escapeHtml(String(value))}">`;
  return `
    <label>
      <span>${escapeHtml(card.type === "RestockCard" && field === "quantity" ? "Stock to add" : card.type === "StockCorrectionCard" && field === "reason" ? "Reason (optional)" : card.type === "ReportCard" && field === "report_date" ? "Displayed Report Date" : card.type === "ReportCard" && field === "generated_at" ? "Last Generated At" : fieldLabel(field))}</span>
      ${control}
    </label>
  `;
}

function reportPeriodTemplate(card, value) {
  const presets = ["Today", "Yesterday", "Last 7 days", "This week", "Last week", "Last 30 days", "This month", "Last month", "Last 3 months", "Last 6 months", "This year", "Custom date", "Custom date range"];
  const text = String(value || "Today");
  const selected = presets.includes(text) ? text : text.includes(" to ") ? "Custom date range" : /^\d{4}-\d{2}-\d{2}$/.test(text) ? "Custom date" : "Today";
  const parts = text.split(" to ");
  return `<div class="report-period-picker"><label><span>Period</span><select data-card-id="${card.id}" data-field="period">${presets.map((option) => `<option ${option === selected ? "selected" : ""}>${option}</option>`).join("")}</select></label>${selected === "Custom date" ? `<label><span>Date</span><input type="date" data-card-id="${card.id}" data-field="custom_start" value="${escapeHtml(String(card.fields?.custom_start || text))}"></label>` : ""}${selected === "Custom date range" ? `<div class="report-date-range"><label><span>Start date</span><input type="date" data-card-id="${card.id}" data-field="custom_start" value="${escapeHtml(String(card.fields?.custom_start || parts[0] || ""))}"></label><label><span>End date</span><input type="date" data-card-id="${card.id}" data-field="custom_end" value="${escapeHtml(String(card.fields?.custom_end || parts[1] || ""))}"></label></div>` : ""}</div>`;
}

function medicineDetailTemplate(card, displayed) {
  const ordered = orderedMedicineFields(displayed);
  const fieldSet = new Set(ordered);
  const restock = card.type === "RestockCard";
  const slideOneFields = (restock
    ? ["medicine", "quantity", "bonus_quantity", "unit"]
    : ["medicine", "selling_price", "quantity"]).filter((field) => fieldSet.has(field));
  const slideTwoFields = (restock
    ? ["pack_size", "strength", "form", "cost_price", "selling_price", "supplier"]
    : ["stock", "current_stock", "strength", "form", "unit", "cost_price", "expiry", "pack_size", "reorder_level"]).filter((field) => fieldSet.has(field));
  const used = new Set([...slideOneFields, ...slideTwoFields, "payment"]);
  const slideThreeFields = (restock
    ? ["batch", "expiry", "barcode", "shelf", "delivery_reference", "note"]
    : ["supplier", "barcode", "batch", "alias", "aliases", "message", "shelf", "category", "reason", "file", "scan_type", "total", "correct_stock"]).filter((field) => fieldSet.has(field) && !used.has(field));
  const remaining = ordered.filter((field) => !used.has(field) && !slideThreeFields.includes(field));
  slideThreeFields.push(...remaining);
  const strength = String(card.fields?.strength || "").trim();
  const activeSlide = Math.max(0, Math.min(2, Number(card.ui?.activeSlide || 0)));
  return `
    <section class="medicine-review-workspace" data-medicine-workspace="${card.id}">
      <div class="medicine-slide-nav" aria-label="Medicine review sections">
        <button type="button" class="${activeSlide === 0 ? "selected" : ""}" data-action="show-medicine-slide" data-card-id="${card.id}" data-slide="0">${card.type === "StockCorrectionCard" ? "Medicine" : "Fast action"}</button>
        <button type="button" class="${activeSlide === 1 ? "selected" : ""}" data-action="show-medicine-slide" data-card-id="${card.id}" data-slide="1">${card.type === "StockCorrectionCard" ? "Stock" : "Stock &amp; details"}</button>
        <button type="button" class="${activeSlide === 2 ? "selected" : ""}" data-action="show-medicine-slide" data-card-id="${card.id}" data-slide="2">${card.type === "StockCorrectionCard" ? "Reason" : "Traceability"}</button>
      </div>
      <div class="medicine-slide-status"><span data-medicine-slide-indicator="${card.id}">${activeSlide + 1} of 3</span><span>${card.type === "StockCorrectionCard" ? stockFixSlideInstruction(activeSlide) : "Swipe or use the section buttons"}</span></div>
      <div class="medicine-slide-track" data-medicine-carousel="${card.id}" data-initial-slide="${activeSlide}">
        <section class="medicine-slide medicine-slide-fast" aria-label="Fast action">
          ${strength ? `<p class="medicine-strength-summary">${escapeHtml(strength)}</p>` : ""}
          <div class="medicine-slide-fields">${slideOneFields.map((field) => fieldTemplate(card, field)).join("")}</div>
          ${fieldSet.has("quantity") ? quantityToolbar(card) : ""}
          ${fieldSet.has("payment") ? paymentToolbar(card) : ""}
          ${card.type === "StockCorrectionCard" ? "" : activeActionsTemplate(card)}
        </section>
        <section class="medicine-slide" aria-label="Stock and medicine details">
          <div class="medicine-slide-fields medicine-slide-fields-compact">${slideTwoFields.length ? slideTwoFields.map((field) => fieldTemplate(card, field)).join("") : '<p class="medicine-empty-slide">No stock details supplied yet.</p>'}</div>
        </section>
        <section class="medicine-slide" aria-label="Traceability and secondary details">
          <div class="medicine-slide-fields medicine-slide-fields-compact">${slideThreeFields.length ? slideThreeFields.map((field) => fieldTemplate(card, field)).join("") : '<p class="medicine-empty-slide">No traceability details supplied yet.</p>'}</div>
        </section>
      </div>
      ${card.type === "StockCorrectionCard" ? activeActionsTemplate(card) : ""}
    </section>
  `;
}

function catalogImportTableTemplate(card) {
  const rows = catalogRowsForCard(card);
  const invoiceMode = card.fields?.import_mode === "invoice_ocr";
  const capabilities = catalogReviewCapabilities(card);
  const columns = invoiceMode ? INVOICE_TABLE_COLUMNS : CATALOG_TABLE_COLUMNS;
  const columnTemplate = columns
    .map((column) => `${column.min}px`)
    .concat(capabilities.reorderable ? ["104px"] : [])
    .join(" ");
  return `
    <div class="catalog-import-editor">
      ${card.fields?.method === "bulk paste" ? catalogPasteAcquisitionTemplate(card) : ""}
      ${invoiceMode ? invoiceSummaryTemplate(card) : ""}
      <div class="catalog-table-wrap" style="--catalog-columns: ${columnTemplate};">
        <table class="catalog-import-table" aria-label="Medicine catalog review">
          <thead>
            <tr>
              ${columns.map((column) => `<th scope="col">${escapeHtml(column.label)}</th>`).join("")}
              ${capabilities.reorderable ? '<th scope="col">Order</th>' : ""}
            </tr>
          </thead>
          <tbody>
            ${rows.map((row, index) => catalogImportRowTemplate(card.id, row, index, rows.length, columns, capabilities)).join("")}
          </tbody>
        </table>
      </div>
      <div class="catalog-mobile-rows" aria-label="Medicine catalog mobile review">
        ${rows.map((row, index) => catalogImportMobileRowTemplate(card.id, row, index, rows.length, columns, capabilities)).join("")}
      </div>
      ${capabilities.addRowAllowed ? `<button class="secondary-action" type="button" data-action="add-catalog-row" data-card-id="${card.id}">Add medicine row</button>` : ""}
      <p>${invoiceMode && card.fields?.import_incomplete === "true"
        ? "Some details may be missing or incorrect. Check every field against the invoice. Approval appears only when required fields and totals are consistent."
        : invoiceMode
          ? "Check every field against the invoice. If repeated scans differ, edit the fields to match the invoice, then approve."
          : "Edit each medicine, then approve. Empty medicine names are ignored."}</p>
    </div>
  `;
}

function catalogPasteAcquisitionTemplate(card) {
  const voiceBusy = state.voice.starting || state.voice.listening;
  return `
    <div class="card-actions catalog-paste-acquisition" aria-label="Add medicines without typing">
      <button type="button" data-action="catalog-paste-voice" data-card-id="${card.id}" ${voiceBusy ? "disabled" : ""}>${voiceBusy ? "Listening…" : "Mic"}</button>
      <button type="button" data-action="catalog-paste-camera" data-card-id="${card.id}">Camera</button>
      <button type="button" data-action="catalog-paste-photo" data-card-id="${card.id}">Photo</button>
    </div>
  `;
}

function invoiceSummaryTemplate(card) {
  return `
    <div class="invoice-summary" aria-label="Invoice details">
      ${["invoice_supplier", "invoice_number", "invoice_date", "invoice_total"]
        .map((field) => fieldTemplate(card, field)).join("")}
    </div>
  `;
}

function catalogImportRowTemplate(cardId, row, index, rowCount, columns = CATALOG_TABLE_COLUMNS, capabilities = {}) {
  return `
    <tr>
      ${columns.map((column) => `
        <td data-label="${escapeHtml(column.label)}">
          <input
            data-card-id="${cardId}"
            data-catalog-row="${index}"
            data-catalog-field="${column.key}"
            ${column.inputMode ? `inputmode="${column.inputMode}"` : ""}
            value="${escapeHtml(String(row[column.key] ?? ""))}">
        </td>
      `).join("")}
      ${capabilities.reorderable ? `<td data-label="Order">${catalogRowOrderControls(cardId, row, index, rowCount)}</td>` : ""}
    </tr>
  `;
}

function catalogRowOrderControls(cardId, row, index, rowCount) {
  const title = row.name || `Medicine ${index + 1}`;
  return `<span class="review-row-order-controls">
    <button type="button" data-action="move-catalog-row" data-card-id="${cardId}" data-row-index="${index}" data-direction="-1" ${index === 0 ? "disabled" : ""} aria-label="Move ${escapeHtml(title)} up">↑</button>
    <button type="button" data-action="move-catalog-row" data-card-id="${cardId}" data-row-index="${index}" data-direction="1" ${index === rowCount - 1 ? "disabled" : ""} aria-label="Move ${escapeHtml(title)} down">↓</button>
  </span>`;
}

function catalogImportMobileRowTemplate(cardId, row, index, rowCount, columns = CATALOG_TABLE_COLUMNS, capabilities = {}) {
  const title = row.name || `Medicine ${index + 1}`;
  return `
    <section class="catalog-mobile-row" aria-label="${escapeHtml(title)}">
      <div class="catalog-mobile-row-title">
        <strong>${escapeHtml(title)}</strong>
        <span>Row ${index + 1}</span>
        ${capabilities.reorderable ? catalogRowOrderControls(cardId, row, index, rowCount) : ""}
      </div>
      <div class="catalog-mobile-fields">
        ${columns.map((column) => `
          <label>
            <span>${escapeHtml(column.label)}</span>
            <input
              data-card-id="${cardId}"
              data-catalog-row="${index}"
              data-catalog-field="${column.key}"
              ${column.inputMode ? `inputmode="${column.inputMode}"` : ""}
              value="${escapeHtml(String(row[column.key] ?? ""))}">
          </label>
        `).join("")}
      </div>
    </section>
  `;
}

function activeActionsTemplate(card) {
  if (card.type === "CatalogWorkspaceCard" || card.type === "ExportHubCard") return "";
  if (card.type === "CatalogOnboardingCard") {
    return `
      <div class="card-actions onboarding-actions">
        <button data-action="start-catalog-invoice" data-card-id="${card.id}">Invoice/photo</button>
        <button data-action="start-catalog-scan" data-card-id="${card.id}">Scan shelves</button>
        <button data-action="start-catalog-paste" data-card-id="${card.id}">Paste list</button>
        <button data-action="start-catalog-file" data-card-id="${card.id}">Upload file</button>
        <button data-action="start-sale-learning" data-card-id="${card.id}">Add while selling</button>
      </div>
    `;
  }
  if (card.type === "CatalogImportCard") {
    if (card.fields?.entry_mode === "paste_input") {
      return `
        <div class="card-actions">
          <button data-action="review-paste-list" data-card-id="${card.id}">Review list</button>
          <button data-action="download-template">Template</button>
          <button data-action="reject-card" data-card-id="${card.id}">Cancel</button>
        </div>
      `;
    }
    if (card.fields?.entry_mode === "no_changes") {
      return `
        <div class="card-actions">
          <button data-action="open-catalog-card">Open catalog</button>
          ${speechControlsTemplate(card)}
          <button data-action="reject-card" data-card-id="${card.id}">Close</button>
        </div>
      `;
    }
    const invoiceMode = card.fields?.import_mode === "invoice_ocr";
    const capabilities = catalogReviewCapabilities(card);
    return `
      <div class="card-actions">
        ${!capabilities.approvalAllowed
          ? '<button data-action="capture-invoice">Scan again</button>'
          : `${invoiceMode ? '<button data-action="capture-invoice">Scan again</button>' : ""}<button data-action="confirm-card" data-card-id="${card.id}">${invoiceMode ? "Approve medicines" : "Approve catalog"}</button>`}
        ${invoiceMode ? "" : '<button data-action="download-template">Template</button>'}
        ${speechControlsTemplate(card)}
        ${capabilities.correctionAllowed ? `<button data-action="correct-card" data-card-id="${card.id}">Correct</button>` : ""}
        <button data-action="reject-card" data-card-id="${card.id}">Cancel</button>
      </div>
    `;
  }
  if (card.type === "NotificationCard") {
    return `
      <div class="card-actions">
        ${card.notificationAction ? `<button class="primary-action" data-action="open-notification-action" data-card-id="${card.id}">${escapeHtml(card.notificationAction.label)}</button>` : ""}
        <button data-action="dismiss-notification" data-notification-id="${notificationIdFromCard(card)}">Done</button>
        ${speechControlsTemplate(card)}
      </div>
    `;
  }
  if (card.type === "ReportCard" || card.type === "DocumentExportCard") {
    return `
      <div class="card-actions">
        ${card.type === "ReportCard" ? `<button data-action="confirm-card" data-card-id="${card.id}" ${card.submitting ? "disabled" : ""}>${card.submitting ? "Generating…" : card.fields?.report_text ? "Refresh report" : "Generate report"}</button>` : `<button data-action="confirm-card" data-card-id="${card.id}">Confirm</button>`}
        ${speechControlsTemplate(card)}
        ${card.type === "ReportCard" ? "" : `<button data-action="correct-card" data-card-id="${card.id}">Correct</button>`}
        <button data-action="reject-card" data-card-id="${card.id}">Cancel</button>
      </div>
    `;
  }
  if (card.type === "StockCorrectionCard") return stockFixActionsTemplate(card);
  const stockFixGuidance = card.type === "StockCorrectionCard" ? stockCorrectionGuidance(card.fields, pharmacyBrain.catalog) : null;
  const confirmationBlocker = stockFixGuidance ? (stockFixGuidance.ready ? "" : stockFixGuidance.message) : medicineReviewBlocker(card);
  return `
    <div class="card-actions">
      <button data-action="confirm-card" data-confirm-card="${card.id}" data-card-id="${card.id}" ${confirmationBlocker ? `disabled title="${escapeHtml(confirmationBlocker)}"` : ""}>${card.type === "RestockCard" ? "Add stock" : "Confirm"}</button>
      ${speechControlsTemplate(card)}
      ${card.type === "StockCorrectionCard" ? `<button data-action="pause-reading">Pause</button><button data-action="resume-reading">Resume</button><button data-action="stop-reading">Stop</button><button data-action="stock-fix-camera" data-card-id="${card.id}">Camera</button><button data-action="stock-fix-photo" data-card-id="${card.id}">Photo</button>` : ""}
      ${card.type === "StockCorrectionCard" && card.learnedSpokenMedicine ? `<button data-action="forget-stock-fix-pronunciation" data-card-id="${card.id}">Forget voice name</button>` : ""}
      <button data-action="correct-card" data-card-id="${card.id}">Correct</button>
      <button data-action="reject-card" data-card-id="${card.id}">Cancel</button>
    </div>
  `;
}

function speechControlsTemplate(card) {
  if (speechControl.cardId !== card.id) return `<button data-action="read-card" data-card-id="${card.id}">Read</button>`;
  return `<button data-action="${speechControl.paused ? "resume-card-reading" : "pause-card-reading"}" data-card-id="${card.id}">${speechControl.paused ? "Resume" : "Pause"}</button><button data-action="stop-card-reading" data-card-id="${card.id}">Stop</button>`;
}

function stockFixActionsTemplate(card) {
  const guidance = stockCorrectionGuidance(card.fields, pharmacyBrain.catalog);
  return `
    <div class="card-actions stock-fix-main-actions">
      <button data-action="confirm-card" data-confirm-card="${card.id}" data-card-id="${card.id}" ${guidance.ready ? "" : `disabled title="${escapeHtml(guidance.message)}"`}>Confirm</button>
      <button data-action="stock-fix-read-control" data-stock-fix-read="${card.id}" data-card-id="${card.id}">Read</button>
      <details class="stock-fix-more-actions">
        <summary>More</summary>
        <div>
          <button data-action="stop-reading" data-card-id="${card.id}">Stop reading</button>
          <button data-action="stock-fix-camera" data-card-id="${card.id}">Camera</button>
          <button data-action="stock-fix-photo" data-card-id="${card.id}">Photo</button>
          <button data-action="stock-fix-file" data-card-id="${card.id}">File</button>
          ${card.learnedSpokenMedicine ? `<button data-action="forget-stock-fix-pronunciation" data-card-id="${card.id}">Forget voice name</button>` : ""}
          <button data-action="reject-card" data-card-id="${card.id}">Cancel</button>
        </div>
      </details>
    </div>
  `;
}

function cardFontControlsTemplate() {
  return `
    <div class="card-font-controls" aria-label="Card text size">
      <button type="button" data-action="decrease-card-font" aria-label="Make card text smaller">-</button>
      <span>${Math.round(state.cardFontScale * 100)}%</span>
      <button type="button" data-action="increase-card-font" aria-label="Make card text bigger">+</button>
    </div>
  `;
}

function paymentToolbar(card) {
  return `
    <div class="button-row" aria-label="Payment options">
      ${paymentOptions().map((payment) => `
        <button data-action="set-payment" data-card-id="${card.id}" data-payment="${payment}" class="${card.fields?.payment === payment ? "selected" : ""}">
          ${paymentLabel(payment)}
        </button>
      `).join("")}
    </div>
  `;
}

function quantityToolbar(card) {
  return `
    <div class="button-row" aria-label="Quantity shortcuts">
      ${quantityBumps().map((amount) => `
        <button data-action="bump-quantity" data-card-id="${card.id}" data-amount="${amount}">
          ${amount > 0 ? "+" : ""}${amount}
        </button>
      `).join("")}
    </div>
  `;
}

function bindEvents() {
  root.querySelector("#commandForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = root.querySelector("#commandInput");
    handleCommand(input.value);
    input.value = "";
  });

  bindActionElements(root);
  root.querySelectorAll("[data-medicine-carousel]").forEach((track) => {
    let frame = 0;
    track.addEventListener("scroll", () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const index = Math.max(0, Math.min(2, Math.round(track.scrollLeft / Math.max(1, track.clientWidth))));
        updateMedicineSlideNavigation(track.dataset.medicineCarousel, index);
      });
    }, { passive: true });
    requestAnimationFrame(() => { track.scrollLeft = track.clientWidth * Number(track.dataset.initialSlide || 0); });
  });

  root.querySelectorAll("[data-field]").forEach((input) => {
    input.addEventListener("focus", () => preserveInlineCardViewport(input));
    input.addEventListener("input", () => updateCardField(input.dataset.cardId, input.dataset.field, input.value));
  });

  root.querySelectorAll("[data-catalog-field]").forEach((input) => {
    input.addEventListener("input", () => updateCatalogImportCell(input.dataset.cardId, input.dataset.catalogRow, input.dataset.catalogField, input.value));
    input.addEventListener("change", () => render());
  });

  root.querySelector("#photoInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file) void addPhotoCards(file, state.pendingScanType || "medicine_photo");
    event.target.value = "";
    state.pendingScanType = "medicine_photo";
  });

  root.querySelector("#cameraInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file && state.pendingScanType === "invoice") {
      void readInvoicePhoto(file);
    } else {
      void addPhotoCards(file || "camera-photo.jpg", state.pendingScanType || "medicine_photo");
    }
    state.pendingScanType = "medicine_photo";
  });

  root.querySelector("#documentInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file) void handleDocumentFile(file);
  });
  root.querySelector("#stockFixFileInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file) void addPhotoCards(file, "stock_fix_photo");
    event.target.value = "";
  });
  root.querySelectorAll("[data-catalog-search]").forEach((input) => input.addEventListener("input", (event) => {
    updateCatalogSearch(event.target.dataset.cardId, event.target.value, event.target);
  }));
  root.querySelectorAll("[data-catalog-edit-field]").forEach((input) => {
    input.addEventListener("input", () => updateCatalogEditDraft(input.dataset.cardId, input.dataset.catalogEditField, input.value));
    input.addEventListener("focus", () => selectCatalogVoiceField(input.dataset.cardId, input.dataset.catalogEditField));
  });
}

function bindActionElements(scope) {
  if (!scope) return;
  scope.onclick = (event) => {
    const actionElement = event.target.closest?.("[data-action]");
    if (!actionElement || !scope.contains(actionElement)) return;
    preserveInlineCardViewport(actionElement);
    handleAction(actionElement.dataset);
  };
}

function preserveInlineCardViewport(element) {
  const card = element?.closest?.(".card-message[data-card-id]");
  if (!card) return;
  if (!["sale-edit-field-voice", "catalog-edit-field-voice", "catalog-edit-voice"].includes(element.dataset.action)) {
    activeVoiceViewportAnchor = null;
  }
  activeCardViewportAnchor = createVoiceViewportAnchor(root, {
    cardId: card.dataset.cardId,
    selector: `.card-message[data-card-id="${CSS.escape(card.dataset.cardId)}"]`
  });
}

function handleAction(dataset) {
  const action = dataset.action;
  if (action === "reuse-command") {
    const input = root.querySelector("#commandInput");
    if (!input) return;
    input.value = dataset.command || "";
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    return;
  }
  if (action === "open-completed-sale") {
    openCompletedSale({
      saleNumber: Number(dataset.saleNumber),
      transactionId: dataset.transactionId || ""
    });
    return;
  }
  if (action === "start-sale-adjustment") {
    startSaleAdjustment(dataset.cardId, dataset.adjustmentType);
    return;
  }
  if (action === "open-sale-adjustment") {
    openSaleAdjustment(dataset.adjustmentId);
    return;
  }
  if (action === "open-adjustment-original") {
    openCompletedSale({ saleNumber: Number(dataset.saleNumber), transactionId: dataset.transactionId || "" });
    return;
  }
  if (action === "bump-sale-adjustment") {
    updateSaleAdjustmentReview(dataset.cardId, { delta: Number(dataset.delta) });
    return;
  }
  if (action === "set-refund-stock") {
    updateSaleAdjustmentReview(dataset.cardId, { restoreStock: dataset.restoreStock === "true" });
    return;
  }
  if (action === "confirm-sale-adjustment") {
    confirmSaleAdjustment(dataset.cardId);
    return;
  }
  if (action === "open-chat") {
    state.ui.screen = "chat";
    state.ui.workspace = dataset.workspace || "operations";
    if (state.ui.workspace === "operations") ensureOnboardingStarted();
    render();
    return;
  }
  if (action === "open-catalog") {
    navigateToCatalogWorkspace();
    render();
    return;
  }
  if (action === "open-activity-history") {
    openActivityHub();
    return;
  }
  if (action === "close-activity-history") {
    collapseActivityHub();
    return;
  }
  if (action === "open-payment-queue") {
    state.ui.screen = "payments";
    render();
    return;
  }
  if (action === "set-completion-mode") {
    transactionEngine.configure({ completionMode: dataset.mode === "request_verify" ? "request_verify" : "always_fast_record" });
    render();
    return;
  }
  if (action === "simulate-payment-result") {
    resolveSimulatedPayment(dataset.transactionId, dataset.status);
    return;
  }
  if (action === "open-catalog-medicine") openCatalogMedicine(dataset.medicineId);
  if (action === "cancel-catalog-edit") cancelCatalogEdit(dataset.cardId);
  if (action === "approve-catalog-edit") approveCatalogEdit(dataset.cardId);
  if (action === "catalog-edit-voice") startCatalogEditVoice(dataset.cardId);
  if (action === "catalog-edit-field-voice") {
    selectCatalogVoiceField(dataset.cardId, dataset.field);
    startCatalogEditVoice(dataset.cardId);
  }
  if (action === "sale-edit-field-voice") startSaleEditFieldVoice(dataset.cardId, dataset.field);
  if (action === "catalog-search-voice") startCatalogSearchVoice(dataset.cardId, dataset.searchPlacement);
  if (action === "back-home") {
    state.ui.screen = "home";
    render();
    return;
  }
  if (action === "focus-chat") root.querySelector("#commandInput")?.focus();
  if (action === "demo-sale") handleCommand("Panadol 2 cash");
  if (action === "start-voice") startVoiceCapture();
  if (action === "take-photo") {
    void openLightweightCamera(dataset.scanType || "medicine_photo");
  }
  if (action === "upload-photo") {
    state.pendingScanType = dataset.scanType || "medicine_photo";
    root.querySelector("#photoInput")?.click();
  }
  if (action === "choose-shelf-photo-method") {
    state.shelfAcquisitionOpen = true;
    render();
    return;
  }
  if (action === "cancel-shelf-photo") {
    state.shelfAcquisitionOpen = false;
    render();
    return;
  }
  if (action === "choose-shelf-photo") {
    state.shelfAcquisitionOpen = false;
    state.pendingScanType = "shelf_photo";
    render();
    root.querySelector("#photoInput")?.click();
    return;
  }
  if (action === "take-shelf-photo") {
    state.shelfAcquisitionOpen = false;
    void openLightweightCamera("shelf_photo");
    return;
  }
  if (action === "upload-document") root.querySelector("#documentInput")?.click();
  if (action === "scan-barcode") {
    void openLightweightCamera("barcode");
  }
  if (action === "capture-invoice") {
    void openLightweightCamera("invoice");
  }
  if (action === "close-camera") closeLightweightCamera();
  if (action === "toggle-camera-light") void toggleCameraLight();
  if (action === "capture-camera-frame") void captureLightweightCameraFrame();
  if (action === "retake-camera-photo") void retakeCameraPhoto();
  if (action === "use-camera-photo") void useCameraPhoto();
  if (action === "demo-onboarding") addOnboardingCard();
  if (action === "start-catalog-invoice") {
    removeCardsByType(["CatalogOnboardingCard"]);
    state.pendingScanType = "invoice";
    root.querySelector("#cameraInput")?.click();
  }
  if (action === "start-catalog-scan") {
    removeCardsByType(["CatalogOnboardingCard"]);
    state.pendingScanType = "shelf_photo";
    root.querySelector("#cameraInput")?.click();
  }
  if (action === "start-catalog-paste") {
    removeCardsByType(["CatalogOnboardingCard"]);
    const existing = state.cards.find((card) => card.type === "CatalogImportCard" && card.fields?.entry_mode === "paste_input" && !String(card.fields?.items_text || "").trim());
    if (existing) {
      render();
      focusCard(existing.id);
    } else {
      addCard(createPasteImportCard());
    }
  }
  if (action === "open-catalog-card") {
    navigateToCatalogWorkspace();
    render();
  }
  if (action === "review-paste-list") reviewPasteList(dataset.cardId);
  if (action === "catalog-paste-voice") startCatalogPasteVoice(dataset.cardId);
  if (action === "catalog-paste-camera") startCatalogPastePhoto(dataset.cardId, true);
  if (action === "catalog-paste-photo") startCatalogPastePhoto(dataset.cardId, false);
  if (action === "add-catalog-row") addCatalogImportRow(dataset.cardId);
  if (action === "move-catalog-row") moveCatalogImportRow(dataset.cardId, dataset.rowIndex, dataset.direction);
  if (action === "start-catalog-file") {
    removeCardsByType(["CatalogOnboardingCard"]);
    root.querySelector("#documentInput")?.click();
  }
  if (action === "start-sale-learning") {
    removeCardsByType(["CatalogOnboardingCard"]);
    addMissingMedicineCard();
  }
  if (action === "export-catalog-csv") exportCatalogCsv();
  if (action === "open-export-hub") openExportHub(dataset.history === "true");
  if (action === "close-export-hub") collapseExportHub();
  if (action === "download-inventory-export") downloadInventoryExport(dataset.format, dataset.cardId);
  if (action === "download-template") downloadBulkPasteTemplate();
  if (action === "read-card") readCardAloud(dataset.cardId);
  if (action === "pause-card-reading") pauseCardReading(dataset.cardId);
  if (action === "resume-card-reading") resumeCardReading(dataset.cardId);
  if (action === "stop-card-reading") stopCardReading(dataset.cardId);
  if (action === "stock-fix-read-control") toggleStockFixReading(dataset.cardId);
  if (action === "pause-reading") pauseStockFixReading();
  if (action === "resume-reading") resumeStockFixReading();
  if (action === "stop-reading") stopStockFixReading();
  if (action === "mark-notifications-read") markNotificationsRead();
  if (action === "dismiss-notification") dismissNotification(dataset.notificationId);
  if (action === "open-notification-action") openNotificationAction(dataset.cardId);
  if (action === "demo-report") addReportCard();
  if (action === "demo-sync") addSyncCard();
  if (action === "demo-stock-correction") addStockCorrectionCard();
  if (action === "stock-fix-camera") startStockFixPhoto(dataset.cardId, true);
  if (action === "stock-fix-photo") startStockFixPhoto(dataset.cardId, false);
  if (action === "stock-fix-file") startStockFixFile(dataset.cardId);
  if (action === "start-stock-fix") startCatalogStockFix(dataset.medicineId);
  if (action === "forget-stock-fix-pronunciation") forgetStockFixPronunciation(dataset.cardId);
  if (action === "refresh-live-status") void refreshLiveStatus();
  if (action === "sync-now") syncNow();
  if (action === "reset-onboarding") resetOnboarding();
  if (action === "decrease-card-font") adjustCardFontScale(-CARD_FONT_SCALE_STEP);
  if (action === "increase-card-font") adjustCardFontScale(CARD_FONT_SCALE_STEP);
  if (action === "confirm-card") confirmCard(dataset.cardId);
  if (action === "correct-card") correctCard(dataset.cardId);
  if (action === "reject-card") rejectCard(dataset.cardId);
  if (action === "dismiss-card") dismissCard(dataset.cardId);
  if (action === "set-payment") setPayment(dataset.cardId, dataset.payment);
  if (action === "bump-quantity") bumpQuantity(dataset.cardId, Number(dataset.amount));
  if (action === "show-medicine-slide") showMedicineSlide(dataset.cardId, Number(dataset.slide));
}

function showMedicineSlide(cardId, slide) {
  const track = root.querySelector(`[data-medicine-carousel="${cardId}"]`);
  if (!track) return;
  const index = Math.max(0, Math.min(2, Number.isFinite(slide) ? slide : 0));
  const card = state.cards.find((item) => item.id === cardId);
  if (card) {
    card.ui = { ...(card.ui || {}), activeSlide: index };
    persistActiveCards();
  }
  track.scrollTo({ left: track.clientWidth * index, behavior: "smooth" });
  updateMedicineSlideNavigation(cardId, index);
}

function updateMedicineSlideNavigation(cardId, index) {
  const workspace = root.querySelector(`[data-medicine-workspace="${cardId}"]`);
  if (!workspace) return;
  workspace.querySelectorAll("[data-slide]").forEach((button) => button.classList.toggle("selected", Number(button.dataset.slide) === index));
  const indicator = workspace.querySelector(`[data-medicine-slide-indicator="${cardId}"]`);
  if (indicator) indicator.textContent = `${index + 1} of 3`;
  const card = state.cards.find((item) => item.id === cardId);
  if (card && Number(card.ui?.activeSlide || 0) !== index) {
    card.ui = { ...(card.ui || {}), activeSlide: index };
    persistActiveCards();
  }
}

function handleCommand(text) {
  state.ui.screen = "chat";
  state.ui.workspace = "operations";
  const trimmed = String(text || "").trim();
  if (!state.onboarding.completed) {
    ensureOnboardingStarted();
    render();
    return;
  }
  if (!trimmed) {
    addFeed("system", "Type a sale, stock question, report request, or paste a medicine list.");
    render();
    return;
  }
  if (routePriorityCommand(trimmed)) return;
  if (isCatalogNavigationIntent(trimmed)) {
    addFeed("owner", trimmed);
    navigateToCatalogWorkspace();
    render();
    return;
  }
  if (looksLikeMedicineList(trimmed)) {
    addFeed("owner", "Pasted medicine list");
    addCard(createPasteImportCard(trimmed.replace(/^list\s*:/i, "").trim()));
    return;
  }
  const stockCheck = resolveStockCheck(trimmed, pharmacyBrain.catalog);
  if (stockCheck.status === "matched") {
    addFeed("owner", trimmed);
    addFeed("system", stockCheckReply(stockCheck.medicine));
    render();
    return;
  }
  if (pharmacyBrain.catalog.length === 0) {
    addFeed("owner", trimmed);
    ensureCatalogOnboardingStarted();
    render();
    return;
  }

  const card = buildCommandCard(trimmed);
  addFeed("owner", trimmed);
  prepareUnknownMedicineFallback(card, trimmed);
  if (canRecordInstantly(card, trimmed)) {
    recordCard(card);
    render();
  } else {
    addCard(card);
  }
}

function routePriorityCommand(text) {
  const direct = parseSaleDirectCommand(text);
  if (!direct) return false;
  addFeed("owner", String(text || "").trim());
  if (direct.action === "open") {
    openCompletedSale({ saleNumber: direct.saleNumber });
    return true;
  }
  if (direct.action === "return") {
    openCompletedSale({ saleNumber: direct.saleNumber }, { adjustmentType: "return" });
    return true;
  }
  addFeed("system", `${direct.action[0].toUpperCase()}${direct.action.slice(1)} by command is not enabled yet. Nothing changed.`);
  render();
  return true;
}

function isCatalogNavigationIntent(text) {
  const normalized = String(text || "").trim().toLowerCase().replace(/\s+/g, " ");
  return ["show me", "show catalog", "show my catalog", "open catalog", "pharmacy catalog"].includes(normalized);
}

function stockCheckReply(medicine) {
  const rawStock = medicine?.stockLeft;
  const unit = medicine?.units?.[0] || "item";
  if (rawStock === null || rawStock === undefined || rawStock === "") {
    return `📦 ${medicine.name}\nStock has not been set yet.`;
  }
  const stock = Number(rawStock);
  if (!Number.isFinite(stock)) return `📦 ${medicine.name}\nStock has not been set yet.`;
  const unitLabel = stock === 1 ? unit : `${unit}s`;
  return `📦 ${medicine.name} stock left: ${stock} ${unitLabel}`;
}

function handleVoiceTranscript(text) {
  state.ui.screen = "chat";
  state.ui.workspace = "operations";
  if (!state.onboarding.completed) {
    ensureOnboardingStarted();
    render();
    return;
  }
  if (routePriorityCommand(text)) return;
  const stockFixCard = state.cards.find((card) => card.type === "StockCorrectionCard");
  if (stockFixCard) {
    handleStockFixVoice(stockFixCard, text);
    return;
  }
  if (isCatalogNavigationIntent(text)) {
    addFeed("owner", String(text || "").trim());
    navigateToCatalogWorkspace();
    render();
    return;
  }
  if (pharmacyBrain.catalog.length === 0) {
    addFeed("owner", text);
    ensureCatalogOnboardingStarted();
    render();
    return;
  }
  const card = buildCommandCard(text);
  addFeed("owner", text);
  prepareUnknownMedicineFallback(card, text);
  removeCardsByPredicate((item) => item.voiceSource === true);
  card.voiceSource = true;
  if (card.type === "RestockCard") {
    card.title = "Check restock";
    card.fields.voice_transcript = String(text || "").trim();
    card.fields.review_feedback = `Heard: “${String(text || "").trim()}”. Check the medicine, stock to add, and unit. Add delivery details only when you have them. Nothing changes until you confirm.`;
    card.validation = card.fields.review_feedback;
  } else if (card.type !== "MedicineMatchCard") {
    card.type = "SaleCard";
    card.title = "Check voice result";
    card.fields = { ...card.fields, transcript: text };
    prepareProductionSaleCard(card, pharmacyBrain.findMedicine(card.fields.medicine));
  } else {
    card.fields.voice_transcript = String(text || "").trim();
    card.fields.review_feedback = `Heard: “${String(text || "").trim()}”. Check every field. Nothing changes until you confirm.`;
    card.validation = card.fields.review_feedback;
  }
  addCard(card);
}

async function startVoiceCapture(onTranscript = null, onStatus = null) {
  if (state.voice.starting || state.voice.listening) return;
  const attempt = ++voiceCaptureAttempt;
  if (navigator.onLine === false) {
    state.voice.status = "Voice needs internet on this phone. You can type while offline.";
    onStatus?.("Voice needs internet on this phone. Connect, then tap Speak medicine again.");
    render();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    state.voice.status = "Microphone capture is unavailable in this browser.";
    onStatus?.("Microphone capture is unavailable in this browser. Try a current version of Chrome.");
    render();
    return;
  }
  state.voice.starting = true;
  state.voice.listening = false;
  state.voice.status = "Requesting microphone permission…";
  onStatus?.("Requesting microphone permission…");
  render();
  const permissionTimer = window.setTimeout(() => {
    if (attempt !== voiceCaptureAttempt || !state.voice.starting) return;
    state.voice.status = "Choose Allow or Block in the browser microphone prompt.";
    onStatus?.(state.voice.status);
    render();
  }, 12000);
  try {
    const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    clearTimeout(permissionTimer);
    if (attempt !== voiceCaptureAttempt) {
      permissionStream.getTracks().forEach((track) => track.stop());
      return;
    }
    permissionStream.getTracks().forEach((track) => track.stop());
  } catch (error) {
    clearTimeout(permissionTimer);
    if (attempt !== voiceCaptureAttempt) return;
    state.voice.starting = false;
    const denied = String(error?.name || "") === "NotAllowedError";
    state.voice.status = denied
      ? "Microphone access was denied. Allow it in browser settings, then tap Speak medicine again."
      : "Microphone could not start. Check this phone's microphone and try again.";
    onStatus?.(state.voice.status);
    render();
    return;
  }
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    state.voice.status = "Voice is not available in this browser. Please type for now.";
    onStatus?.("Voice is unavailable in this browser. Use Chrome with microphone access, then try again.");
    render();
    return;
  }
  const recognition = new SpeechRecognition();
  recognition.lang = "en-KE";
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  let heardResult = false;
  let voiceError = false;
  let audioReady = false;
  let captureTimer = null;
  let startupTimer = null;
  let latestTranscript = "";
  activeRecognition = recognition;
  state.voice.starting = true;
  state.voice.listening = false;
  state.voice.status = "Starting microphone… Please wait.";
  render();
  const markAudioReady = () => {
    if (audioReady) return;
    audioReady = true;
    if (startupTimer) clearTimeout(startupTimer);
    state.voice.starting = false;
    state.voice.listening = true;
    const stockFixCard = state.cards.find((card) => card.type === "StockCorrectionCard");
    if (stockFixCard) state.voice.status = stockFixVoicePrompt(stockFixCard);
    else state.voice.status = "Speak now.";
    onStatus?.("Listening… Say one saved medicine name.");
    render();
    captureTimer = setTimeout(() => {
      if (activeRecognition !== recognition) return;
      state.voice.status = latestTranscript
        ? `Heard: “${latestTranscript}”. Finishing…`
        : "Finishing this listening attempt…";
      render();
      try { recognition.stop(); } catch { /* already stopped */ }
    }, 8000);
  };
  recognition.onaudiostart = markAudioReady;
  recognition.onresult = (event) => {
    let transcript = "";
    let finalTranscript = "";
    for (let index = event.resultIndex || 0; index < (event.results?.length || 0); index += 1) {
      const words = event.results[index]?.[0]?.transcript || "";
      transcript = `${transcript} ${words}`.trim();
      if (event.results[index]?.isFinal) finalTranscript = `${finalTranscript} ${words}`.trim();
    }
    if (transcript) {
      latestTranscript = transcript;
      state.voice.status = `Heard: “${transcript}”${finalTranscript ? "." : "…"}`;
      render();
    }
    if (!finalTranscript) return;
    heardResult = true;
    if (captureTimer) clearTimeout(captureTimer);
    state.voice.starting = false;
    state.voice.listening = false;
    state.voice.status = `Heard: “${finalTranscript}”.`;
    onStatus?.("Processing spoken medicine locally…");
    activeRecognition = null;
    if (finalTranscript.trim()) {
      if (onTranscript) {
        onTranscript(finalTranscript.trim());
      } else {
        const guidedStockFix = state.cards.some((card) => card.type === "StockCorrectionCard");
        handleVoiceTranscript(finalTranscript);
        const continuingCard = state.cards.find((card) => card.type === "StockCorrectionCard");
        if (guidedStockFix && continuingCard && !continuingCard.ui?.reviewedSlides && !continuingCard.ui?.voiceAwaitingManualRetry) {
          announceStockFixNextStep(continuingCard);
        }
      }
    } else {
      render();
    }
  };
  recognition.onspeechend = () => {
    state.voice.status = latestTranscript
      ? `Heard: “${latestTranscript}”. Finishing…`
      : "Speech ended. Finishing…";
    render();
    try { recognition.stop(); } catch { /* already stopped */ }
  };
  recognition.onerror = (event) => {
    if (captureTimer) clearTimeout(captureTimer);
    if (startupTimer) clearTimeout(startupTimer);
    voiceError = true;
    state.voice.starting = false;
    state.voice.listening = false;
    const error = String(event?.error || "");
    state.voice.status = error === "not-allowed" || error === "service-not-allowed"
      ? "Microphone access is off. Allow it in your browser settings, then try again."
      : error === "network"
        ? "Voice could not connect. Check the internet, or type the command."
        : error === "no-speech"
          ? "I did not hear any words. Tap Mic and try again."
          : "Voice stopped before it heard the command. Tap Mic and try again.";
    onStatus?.(state.voice.status);
    activeRecognition = null;
    render();
  };
  recognition.onend = () => {
    if (captureTimer) clearTimeout(captureTimer);
    if (startupTimer) clearTimeout(startupTimer);
    activeRecognition = null;
    state.voice.starting = false;
    state.voice.listening = false;
    const completedStockFixReview = state.cards.find((card) => card.type === "StockCorrectionCard" && card.ui?.voiceReviewCompleted);
    if (!heardResult && !voiceError) state.voice.status = completedStockFixReview
      ? "Review complete. Tap Mic and say Confirm again to apply this stock fix once."
      : "I did not receive a completed transcript. Tap Mic and try once more.";
    if (!heardResult && !voiceError) onStatus?.(state.voice.status);
    if (!heardResult && !voiceError && (state.voice.status === "Speak now." || state.voice.status === "Starting microphone… Please wait.")) {
      state.voice.status = "I did not hear any words. Tap Mic and try again.";
    } else if (state.voice.status === "Speak now." || state.voice.status === "Starting microphone… Please wait.") {
      state.voice.status = "";
    }
    render();
  };
  try {
    recognition.start();
    startupTimer = window.setTimeout(() => {
      if (activeRecognition !== recognition || audioReady) return;
      state.voice.status = "Microphone did not start. Tap Speak medicine to retry.";
      onStatus?.(state.voice.status);
      try { recognition.abort(); } catch { /* already stopped */ }
    }, 12000);
  } catch {
    activeRecognition = null;
    state.voice.starting = false;
    state.voice.listening = false;
    state.voice.status = "Voice could not start. Check the internet and microphone access, or type the command.";
    onStatus?.("Voice could not start. Allow microphone access, check the internet, then try again.");
    render();
  }
}

function stopActiveVoiceCapture() {
  voiceCaptureAttempt += 1;
  const recognition = activeRecognition;
  activeRecognition = null;
  if (recognition) {
    try { recognition.abort(); } catch { /* already stopped */ }
  }
  state.voice.starting = false;
  state.voice.listening = false;
  state.voice.status = "";
}

function buildCommandCard(text) {
  const card = backendAdapters.adapters.commandParserAdapter.toCard(text, pharmacyBrain.catalog);
  card.integration = backendAdapters.prepareBackendAction(card, state.liveBackend);
  card.validation = `${card.validation || ""} ${card.integration.summary}`.trim();
  return card;
}

function canRecordInstantly(card, sourceText) {
  return false;
}

function prepareUnknownMedicineFallback(card, sourceText) {
  if (card.type !== "SaleCard") return card;
  const catalogMatch = pharmacyBrain.findMedicine(card.fields?.medicine);
  if (catalogMatch.status === "matched") return prepareProductionSaleCard(card, catalogMatch);
  const sourceMatch = sourceBrain.lookupMedicine(card.fields?.medicine);
  card.type = "MedicineMatchCard";
  card.title = "Add new medicine";
  card.status = "needs_correction";
  card.confidence = 0.68;
  card.fields = {
    message: "This medicine is not in your pharmacy catalog yet.",
    medicine: sourceMatch.status === "matched" ? sourceMatch.name : card.fields?.medicine || sourceText,
    form: first(sourceMatch.forms),
    unit: first(sourceMatch.units),
    selling_price: sellingPriceFromText(sourceText),
    quantity: card.fields?.quantity || "1",
    payment: card.fields?.payment || "cash",
    stock: "",
    cost_price: "",
    supplier: "",
    batch: "",
    expiry: "",
    alias: ""
  };
  card.validation = "Approve to save this medicine locally before repeat sales.";
  return card;
}

function commandHasExplicitPayment(text) {
  return /(?:^|[\s\d-])(cash|mpesa|m-pesa|credit|mixed)$/i.test(String(text || "").trim());
}

async function resolveVisualTestFixture(fileOrName, findFixture) {
  const fileName = typeof fileOrName === "string" ? fileOrName : fileOrName?.name;
  const filenameMatch = findFixture({ fileName });
  if (filenameMatch || typeof fileOrName?.arrayBuffer !== "function") return filenameMatch;
  if (globalThis.crypto?.subtle) try {
    const digest = await globalThis.crypto.subtle.digest("SHA-256", await fileOrName.arrayBuffer());
    const sha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    const contentMatch = findFixture({ sha256 });
    if (contentMatch) return contentMatch;
  } catch {
    // A visual fingerprint below remains available when byte hashing is unavailable.
  }
  try {
    const bitmap = await createImageBitmap(fileOrName);
    const canvas = document.createElement("canvas");
    canvas.width = 8;
    canvas.height = 8;
    const context = canvas.getContext("2d", { alpha: false, willReadFrequently: true });
    const cropInsets = [0, 0.06, 0.12];
    const luminanceCandidates = cropInsets.map((inset) => {
      const sourceX = Math.round(bitmap.width * inset);
      const sourceY = Math.round(bitmap.height * inset);
      const sourceWidth = Math.max(1, bitmap.width - (sourceX * 2));
      const sourceHeight = Math.max(1, bitmap.height - (sourceY * 2));
      context.clearRect(0, 0, 8, 8);
      context.drawImage(bitmap, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, 8, 8);
      const pixels = context.getImageData(0, 0, 8, 8).data;
      return Array.from({ length: 64 }, (_, index) => {
        const offset = index * 4;
        return (pixels[offset] * 0.299) + (pixels[offset + 1] * 0.587) + (pixels[offset + 2] * 0.114);
      });
    });
    const rotateGrid = (values) => Array.from({ length: 64 }, (_, index) => {
      const row = Math.floor(index / 8);
      const column = index % 8;
      return values[(7 - column) * 8 + row];
    });
    const hashGrid = (values) => {
      const average = values.reduce((sum, value) => sum + value, 0) / values.length;
      const bits = values.map((value) => value >= average ? "1" : "0").join("");
      return Array.from({ length: 16 }, (_, index) =>
        Number.parseInt(bits.slice(index * 4, (index + 1) * 4), 2).toString(16)
      ).join("");
    };
    const perceptualHashes = luminanceCandidates.flatMap((luminance) => {
      const orientations = [luminance];
      for (let index = 0; index < 3; index += 1) orientations.push(rotateGrid(orientations.at(-1)));
      return orientations.map(hashGrid);
    });
    const aspectRatio = bitmap.width / Math.max(1, bitmap.height);
    bitmap.close?.();
    return findFixture({ perceptualHashes, aspectRatio });
  } catch {
    return null;
  }
}

const resolveShelfTestFixture = (fileOrName) => resolveVisualTestFixture(fileOrName, findShelfTestFixture);
const resolveMedicinePhotoTestFixture = (fileOrName) => resolveVisualTestFixture(fileOrName, findMedicinePhotoTestFixture);

async function addPhotoCards(fileOrName, scanType, knownFixture) {
  state.ui.screen = "chat";
  state.ui.workspace = "operations";
  const fileName = typeof fileOrName === "string" ? fileOrName : fileOrName?.name || "camera-photo.jpg";
  if (scanType === "stock_fix_photo") {
    const card = state.cards.find((item) => item.id === state.stockFixPhotoCardId && item.type === "StockCorrectionCard")
      || state.cards.find((item) => item.type === "StockCorrectionCard");
    if (!card) return false;
    if (!(fileOrName instanceof Blob) || !String(fileOrName.type || "").startsWith("image/")) {
      card.validation = "Choose a supported image file. Stock Fix did not start another import workflow.";
      render();
      return false;
    }
    return processStockFixEvidence(card, fileOrName, fileName, pendingStockFixEvidenceSource);
  }
  const shelfFixture = scanType === "shelf_photo"
    ? (knownFixture === undefined ? await resolveShelfTestFixture(fileOrName) : knownFixture)
    : null;
  if (shelfFixture) {
    const recognizedItems = shelfFixture.items.filter((item) => sourceBrain.lookupMedicine(item.name).status === "matched");
    if (recognizedItems.length === shelfFixture.items.length) {
      const targetedPasteCard = state.cards.find((item) =>
        item.id === state.catalogPasteCaptureCardId
        && item.type === "CatalogImportCard"
      );
      if (targetedPasteCard) {
        state.catalogPasteCaptureCardId = "";
        applyCatalogPasteReview(targetedPasteCard, recognizedItems, {
          method: "shelf photo",
          source: fileName,
          feedback: "Read locally from the selected photo. Check every medicine and field. Nothing is saved until approval."
        });
        return true;
      }
      const card = createPasteImportCard(catalogItemsToText(recognizedItems));
      card.title = "Review shelf medicines";
      card.source = fileName;
      card.fields.method = "shelf photo";
      card.fields.scan_type = "shelf_photo";
      card.fields.review_feedback = "Controlled test match. Read from this photo: medicine names, strengths, form, and shelf. Filled from the prepared test record, not read from the photo: stock, buying and selling prices, supplier, batch, and expiry. Barcode was left blank. Check every value. Nothing is saved until approval.";
      card.validation = card.fields.review_feedback;
      addCard(card);
      refreshNotifications();
      return true;
    }
  }
  if (scanType === "shelf_photo") {
    addFeed("assistant", "I could not read this shelf photo clearly. Take it again. Move closer, show the medicine names and shelf label, hold the phone still, and keep bright light off the packs or screen. Nothing has been saved.");
    render();
    return false;
  }
  const medicineFixture = scanType === "medicine_photo"
    ? (knownFixture === undefined ? await resolveMedicinePhotoTestFixture(fileOrName) : knownFixture)
    : null;
  if (medicineFixture) {
    const sourceMatch = sourceBrain.lookupMedicine(medicineFixture.item.name);
    if (sourceMatch.status === "matched") {
      const review = normalizeMedicineReviewRow(medicineFixture.item);
      addCard(createEditableCard({
        type: "VisualScanCard",
        title: "Review medicine photo",
        source: fileName,
        fields: {
          scan_type: "medicine_photo",
          medicine: review.name,
          strength: review.strength,
          form: review.form,
          unit: review.unit,
          pack_size: review.pack_size,
          quantity: "",
          selling_price: "",
          cost_price: "",
          supplier: "",
          barcode: review.barcode,
          batch: review.batch,
          expiry: review.expiry,
          shelf: "",
          category: "",
          review_feedback: "Controlled test match. Seen in this photo: medicine name, strength, capsule form, pack size, barcode, batch, and expiry. Stock, prices, supplier, and shelf were not seen and were left blank. Check every value. Nothing is saved until approval."
        },
        confidence: 0.96,
        status: "ready",
        validation: "Controlled medicine-photo fixture matched locally through Source Brain."
      }));
      refreshNotifications();
      return true;
    }
  }
  if (scanType === "medicine_photo") {
    addFeed("assistant", "I could not read this medicine photo clearly. Take it again. Show the whole medicine pack, keep the words clear, and hold the phone still. Nothing has been saved.");
    render();
    return false;
  }
  const result = runVisualPipeline({ fileName, scanType });
  const visualCard = buildPhotoReviewCard(result);
  addCard(visualCard);
  refreshNotifications();
  return true;
}

async function openLightweightCamera(scanType = "medicine_photo") {
  closeCameraStream();
  clearCapturedCameraPhoto();
  state.camera.open = true;
  state.camera.scanType = scanType;
  state.camera.status = "Opening camera…";
  render();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1920, max: 1920 },
        height: { ideal: 1080, max: 1440 }
      },
      audio: false
    });
    state.camera.stream = stream;
    state.camera.status = "";
    const track = stream.getVideoTracks()[0];
    const capabilities = track?.getCapabilities?.() || {};
    const advanced = [];
    if (capabilities.focusMode?.includes?.("continuous")) advanced.push({ focusMode: "continuous" });
    if (capabilities.exposureMode?.includes?.("continuous")) advanced.push({ exposureMode: "continuous" });
    if (capabilities.whiteBalanceMode?.includes?.("continuous")) advanced.push({ whiteBalanceMode: "continuous" });
    if (advanced.length) await track.applyConstraints({ advanced }).catch(() => {});
    state.camera.lightAvailable = Boolean(capabilities.torch);
    state.camera.lightOn = false;
    const video = root.querySelector("#ms20CameraPreview");
    if (video) {
      video.srcObject = stream;
      await video.play();
    }
    const status = root.querySelector(".camera-status");
    if (status) status.textContent = scanType === "shelf_photo"
      ? "Ready — hold the phone still, then tap Capture."
      : "Ready — hold the phone still, keep bright light off the item, then tap Capture.";
    const actions = root.querySelector(".camera-actions");
    if (actions && state.camera.lightAvailable && !actions.querySelector('[data-action="toggle-camera-light"]')) {
      const lightButton = document.createElement("button");
      lightButton.type = "button";
      lightButton.dataset.action = "toggle-camera-light";
      lightButton.textContent = "Light on";
      lightButton.addEventListener("click", () => void toggleCameraLight());
      actions.insertBefore(lightButton, actions.lastElementChild);
    }
    return true;
  } catch {
    state.camera.status = "Camera did not open. Allow camera access and try again.";
    render();
    return false;
  }
}

function closeLightweightCamera() {
  const finderWasActive = Boolean(activeFinderWindow);
  closeCameraStream();
  clearCapturedCameraPhoto();
  state.camera.open = false;
  state.camera.status = "";
  state.camera.lightAvailable = false;
  state.camera.lightOn = false;
  render();
  if (finderWasActive) postFinderResult("", "barcode_cancelled", "Scanner cancelled. Tap Scan barcode to retry.");
}

function clearCapturedCameraPhoto() {
  if (state.camera.capturedUrl) URL.revokeObjectURL(state.camera.capturedUrl);
  state.camera.capturedFile = null;
  state.camera.capturedUrl = "";
  state.camera.retryRequired = false;
}

async function retakeCameraPhoto() {
  const scanType = state.camera.scanType;
  clearCapturedCameraPhoto();
  await openLightweightCamera(scanType);
}

async function useCameraPhoto() {
  const file = state.camera.capturedFile;
  const scanType = state.camera.scanType;
  if (!file) return;
  state.camera.status = "Processing photo locallyâ€¦";
  render();
  const visualFixture = scanType === "shelf_photo"
    ? await resolveShelfTestFixture(file)
    : scanType === "medicine_photo"
      ? await resolveMedicinePhotoTestFixture(file)
      : undefined;
  if ((scanType === "shelf_photo" || scanType === "medicine_photo") && !visualFixture) {
    state.camera.retryRequired = true;
    state.camera.status = scanType === "shelf_photo"
      ? "I could not read this shelf clearly. Tap Retake. If the phone was sideways, try holding it upright. Move closer, show both medicine names and the shelf label, and hold the phone still. Nothing has been saved."
      : "I could not read this medicine clearly. Tap Retake. If the phone was sideways, try holding it upright. Move closer, show the whole pack, keep the words clear, and hold the phone still. Nothing has been saved.";
    render();
    return;
  }
  await addPhotoCards(file, scanType, visualFixture);
  clearCapturedCameraPhoto();
  state.camera.open = false;
  state.camera.status = "";
  render();
}

async function toggleCameraLight() {
  const track = state.camera.stream?.getVideoTracks?.()[0];
  if (!track || !state.camera.lightAvailable) return;
  const next = !state.camera.lightOn;
  try {
    await track.applyConstraints({ advanced: [{ torch: next }] });
    const applied = track.getSettings?.().torch;
    if (typeof applied === "boolean" && applied !== next) {
      throw new Error("Camera did not apply the light setting");
    }
    state.camera.lightOn = next;
    const button = root.querySelector('[data-action="toggle-camera-light"]');
    if (button) button.textContent = next ? "Light off" : "Light on";
  } catch {
    state.camera.lightAvailable = false;
    root.querySelector('[data-action="toggle-camera-light"]')?.remove();
    state.camera.status = "The camera light does not work on this phone. Use room light and keep bright light off the packs or screen.";
    const status = root.querySelector(".camera-status");
    if (status) status.textContent = state.camera.status;
  }
}

function closeCameraStream() {
  state.camera.stream?.getTracks?.().forEach((track) => track.stop());
  state.camera.stream = null;
}

async function captureLightweightCameraFrame() {
  const video = root.querySelector("#ms20CameraPreview");
  if (!video || !video.videoWidth || !video.videoHeight) {
    state.camera.status = "Camera is still opening. Try Capture again.";
    const status = root.querySelector(".camera-status");
    if (status) status.textContent = state.camera.status;
    return;
  }
  const readingEdge = video.videoWidth > video.videoHeight ? 2400 : 1800;
  const scale = Math.min(1, readingEdge / Math.max(video.videoWidth, video.videoHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
  canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
  const context = canvas.getContext("2d", { alpha: false });
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  const scanType = state.camera.scanType;
  const blob = await new Promise((resolve, reject) => canvas.toBlob(
    (value) => value ? resolve(value) : reject(new Error("I could not capture this photo.")),
    "image/jpeg",
    0.92
  ));
  closeCameraStream();
  const file = new File([blob], `${scanType}-${Date.now()}.jpg`, { type: "image/jpeg" });
  if (scanType !== "shelf_photo" && scanType !== "medicine_photo") {
    state.camera.open = false;
    state.camera.status = "";
    render();
    if (scanType === "invoice") await readInvoicePhoto(file, true);
    else if (scanType === "barcode") await readBarcodeCapture(file);
    else await addPhotoCards(file, scanType);
    return;
  }
  state.camera.capturedFile = file;
  state.camera.capturedUrl = URL.createObjectURL(file);
  state.camera.retryRequired = false;
  state.camera.status = "Check the photo. Retake it, or use it to continue. Nothing has been saved.";
  render();
}

async function readBarcodeCapture(file) {
  let barcode = "";
  if ("BarcodeDetector" in globalThis) {
    try {
      const detector = new globalThis.BarcodeDetector();
      const bitmap = await createImageBitmap(file);
      const results = await detector.detect(bitmap);
      bitmap.close();
      barcode = String(results[0]?.rawValue || "").trim();
    } catch (_error) {
      barcode = "";
    }
  }
  const existing = barcode
    ? pharmacyBrain.catalog.find((item) => String(item.barcode || "").trim() === barcode)
    : null;
  const fixture = existing ? null : findBarcodeTestFixture(barcode);
  const sourceCandidate = fixture ? sourceBrain.lookupMedicine(fixture.name) : null;
  const recognized = existing || (sourceCandidate?.status === "matched" ? fixture : null);
  const review = recognized ? normalizeMedicineReviewRow(recognized) : {};
  if (activeFinderWindow) {
    postFinderResult(
      review.name || barcode,
      barcode ? "barcode" : "barcode_not_read",
      recognized
        ? `Barcode matched ${review.name} in this Pharmacy Catalog.`
        : barcode
          ? "Barcode captured, but it has no match in this Pharmacy Catalog."
          : "No barcode was read. Tap Scan barcode to retry."
    );
    return;
  }
  addCard(createEditableCard({
    type: "VisualScanCard",
    title: barcode ? "Check barcode" : "Barcode needs review",
    source: "Local barcode scanner",
    fields: {
      scan_type: "barcode",
      medicine: review.name || "",
      strength: review.strength || "",
      form: review.form || "",
      unit: review.unit || "",
      pack_size: review.pack_size || "",
      barcode,
      quantity: review.stock ?? "",
      selling_price: review.selling_price ?? "",
      cost_price: review.cost_price ?? "",
      supplier: review.supplier || "",
      batch: review.batch || "",
      expiry: review.expiry || "",
      shelf: review.shelf || ""
    },
    confidence: barcode ? 0.96 : 0.3,
    status: recognized ? "ready" : "needs_correction",
    validation: barcode
      ? existing
        ? "Matched locally to a saved Pharmacy Catalog medicine. Check before confirming."
        : fixture && recognized
          ? "Matched locally to a controlled Source Brain test fixture. Nothing is saved until approval."
          : "Barcode read locally. Add the medicine details before confirming."
      : "No barcode was read. Retake the scan or enter the barcode manually; nothing has been saved."
  }));
}

async function readInvoicePhoto(file, prepared = false) {
  state.ui.screen = "chat";
  state.ui.workspace = "operations";
  state.voice.status = "Reading invoice…";
  render();
  try {
    const upload = prepared ? file : await resizeImageForReading(file);
    const body = new FormData();
    body.append("file", upload, file.name || "invoice.jpg");
    const response = await fetch("/api/ms20/invoice-scan", { method: "POST", body });
    const contentType = response.headers.get("content-type") || "";
    const result = contentType.includes("application/json") ? await response.json() : {};
    if (!response.ok) throw new Error(result.detail || "I could not finish reading this invoice. Please scan it again.");
    if (!Array.isArray(result.items) || result.items.length === 0) {
      addFeed("system", result.message || "I could not find clear medicine rows. Try a clearer photo.");
      state.voice.status = "";
      render();
      return;
    }
    let rows = result.items.map((item) => ({
      name: item.medicine_name || item.name || "",
      form: item.form || "",
      unit: item.unit || "",
      stock: item.quantity ?? "",
      cost_price: item.unit_cost ?? "",
      line_total: item.line_total ?? "",
      selling_price: item.selling_price ?? "",
      supplier: result.supplier_name || "",
      barcode: item.barcode || "",
      batch: item.batch_number || "",
      expiry: item.expiry_date || "",
      source: "local_invoice_ocr"
    }));
    const remembered = mergeRememberedInvoiceReview(rows, result);
    rows = remembered.rows;
    Object.assign(result, remembered.metadata);
    result.complete = invoiceRowsComplete(rows, result.invoice_total);
    const card = createPasteImportCard(catalogItemsToText(rows));
    card.fields.catalog_rows = JSON.stringify(rows);
    card.fields.import_mode = "invoice_ocr";
    card.fields.import_incomplete = result.complete === false ? "true" : "false";
    card.fields.invoice_supplier = result.supplier_name || "";
    card.fields.invoice_number = result.invoice_number || "";
    card.fields.invoice_date = result.invoice_date || "";
    card.fields.invoice_total = result.invoice_total ?? "";
    card.fields.invoice_evidence = JSON.stringify(remembered.evidence);
    card.title = "Check invoice medicines";
    card.source = `${result.supplier_name || "Supplier invoice"}${result.invoice_number ? ` · ${result.invoice_number}` : ""}`;
    card.validation = result.complete === false
      ? "This scan is incomplete and cannot be approved. Check the photo and scan again."
      : "I read this on your device. Check the medicines, then approve.";
    state.voice.status = "";
    if (remembered.matchedCardIds.length) {
      const matchedIds = new Set(remembered.matchedCardIds);
      state.cards = state.cards.filter((item) => !matchedIds.has(item.id));
    }
    addCard(card);
  } catch (error) {
    state.voice.status = "";
    addFeed("system", error?.message || "I could not read this invoice. Try a clearer photo.");
    render();
  }
}

function mergeRememberedInvoiceReview(rows, result) {
  const knownCards = [...state.cards, ...readInvoiceMemoryCards()]
    .filter((card, index, cards) => cards.findIndex((candidate) => candidate.id === card.id) === index);
  const candidates = knownCards.filter((card) => {
    if (card.type !== "CatalogImportCard" || card.fields?.import_mode !== "invoice_ocr") return false;
    const sameNumber = result.invoice_number && card.fields.invoice_number === result.invoice_number;
    const sameSignature = result.supplier_name && result.invoice_date && result.invoice_total
      && card.fields.invoice_supplier === result.supplier_name
      && card.fields.invoice_date === result.invoice_date
      && Number(card.fields.invoice_total) === Number(result.invoice_total);
    return sameNumber || sameSignature;
  });
  const rememberedRows = candidates.flatMap((card) => catalogRowsForCard(card));
  const evidence = mergeInvoiceEvidence(candidates, rows);
  const rememberedMetadata = {
    supplier_name: firstRememberedInvoiceValue(candidates, "invoice_supplier"),
    invoice_number: firstRememberedInvoiceValue(candidates, "invoice_number"),
    invoice_date: firstRememberedInvoiceValue(candidates, "invoice_date"),
    invoice_total: firstRememberedInvoiceValue(candidates, "invoice_total")
  };
  const allRows = [...rows, ...rememberedRows];
  const groups = new Map();
  allRows.forEach((row) => {
    const key = normalizeMedicineKey(row.name);
    if (!key) return;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  });
  const targetTotal = Number(result.invoice_total || rememberedMetadata.invoice_total || 0);
  const numericChoices = [...groups.values()].map((versions) => versions.filter(invoiceRowArithmeticValid).slice(0, 8));
  const exactSet = chooseInvoiceRowsByTotal(numericChoices, targetTotal);
  const chosenByName = new Map((exactSet || []).map((row) => [normalizeMedicineKey(row.name), row]));
  const ownerReviewedRows = candidates
    .filter((card) => card.fields?.invoice_owner_edited === "true")
    .map((card) => catalogRowsForCard(card))
    .find((candidateRows) => invoiceRowsComplete(candidateRows, targetTotal));
  ownerReviewedRows?.forEach((row) => chosenByName.set(normalizeMedicineKey(row.name), row));
  const invoiceMonth = invoiceMonthValue(result.invoice_date || rememberedMetadata.invoice_date);
  const batchAssignments = chooseUniqueInvoiceBatches(evidence, [...groups.keys()]);
  const merged = [...groups.entries()].map(([key, versions]) => {
    const strongest = [...versions].sort((left, right) => invoiceRowEvidenceScore(right) - invoiceRowEvidenceScore(left))[0];
    const combined = { ...(chosenByName.get(key) || strongest) };
    for (const field of ["form", "unit", "selling_price", "batch", "expiry"]) {
      const counts = evidence.rows?.[key]?.fields?.[field];
      const consensus = strongestInvoiceEvidenceValue(counts, (value, count) => {
        if (field === "batch") return batchAssignments.get(key) === value;
        if (field === "expiry") return invoiceExpiryNotBefore(value, invoiceMonth);
        return true;
      });
      if (consensus) combined[field] = consensus;
      else {
        const rememberedValue = rememberedRows.find((row) => normalizeMedicineKey(row.name) === key)?.[field] || "";
        const rememberedUsable = field !== "expiry" || invoiceExpiryNotBefore(rememberedValue, invoiceMonth);
        combined[field] = rememberedUsable ? rememberedValue : "";
      }
    }
    return combined;
  });
  const completeRememberedOrder = ownerReviewedRows || candidates.map((card) => catalogRowsForCard(card))
    .find((candidateRows) => invoiceRowsComplete(candidateRows, targetTotal));
  const currentRowsReconcile = rows.length === groups.size && rows.every(invoiceRowArithmeticValid)
    && (!targetTotal || Math.abs(rows.reduce((sum, row) => sum + Number(row.line_total), 0) - targetTotal) < 0.01);
  const trustedOrder = completeRememberedOrder || (currentRowsReconcile ? rows : null);
  const sourceOrder = new Map((trustedOrder || [...groups.keys()]).map((row, index) => {
    const key = typeof row === "string" ? row : normalizeMedicineKey(row.name);
    return [key, trustedOrder ? index : strongestInvoiceOrder(evidence.rows?.[key]?.positions)];
  }));
  merged.sort((left, right) => (sourceOrder.get(normalizeMedicineKey(left.name)) ?? 999) - (sourceOrder.get(normalizeMedicineKey(right.name)) ?? 999));
  normalizeRememberedBatchDigits(merged);
  return {
    rows: merged,
    evidence,
    matchedCardIds: candidates.map((card) => card.id),
    metadata: {
      supplier_name: rememberedMetadata.supplier_name || result.supplier_name || "",
      invoice_number: rememberedMetadata.invoice_number || result.invoice_number || "",
      invoice_date: rememberedMetadata.invoice_date || result.invoice_date || "",
      invoice_total: rememberedMetadata.invoice_total || result.invoice_total || ""
    }
  };
}

function mergeInvoiceEvidence(cards, observedRows) {
  const evidence = { version: 1, rows: {} };
  cards.forEach((card) => {
    const saved = parseInvoiceEvidence(card.fields?.invoice_evidence);
    Object.entries(saved.rows || {}).forEach(([key, row]) => mergeInvoiceEvidenceRow(evidence, key, row));
    if (!card.fields?.invoice_evidence) addInvoiceObservation(evidence, catalogRowsForCard(card));
  });
  addInvoiceObservation(evidence, observedRows);
  return evidence;
}

function parseInvoiceEvidence(value) {
  try {
    const parsed = JSON.parse(value || "{}");
    return parsed && typeof parsed === "object" ? parsed : { rows: {} };
  } catch {
    return { rows: {} };
  }
}

function mergeInvoiceEvidenceRow(evidence, key, saved) {
  const target = evidence.rows[key] ||= { fields: {}, positions: {} };
  Object.entries(saved.fields || {}).forEach(([field, counts]) => {
    const targetCounts = target.fields[field] ||= {};
    Object.entries(counts || {}).forEach(([value, count]) => { targetCounts[value] = (targetCounts[value] || 0) + Number(count || 0); });
  });
  Object.entries(saved.positions || {}).forEach(([position, count]) => {
    target.positions[position] = (target.positions[position] || 0) + Number(count || 0);
  });
}

function addInvoiceObservation(evidence, rows) {
  rows.forEach((row, position) => {
    const key = normalizeMedicineKey(row.name);
    if (!key) return;
    const target = evidence.rows[key] ||= { fields: {}, positions: {} };
    target.positions[position] = (target.positions[position] || 0) + 1;
    for (const field of ["form", "unit", "selling_price", "batch", "expiry"]) {
      const value = String(row[field] || "").trim();
      if (!value) continue;
      const counts = target.fields[field] ||= {};
      counts[value] = (counts[value] || 0) + 1;
    }
  });
}

function strongestInvoiceEvidenceValue(counts, usable = () => true) {
  const ranked = Object.entries(counts || {}).filter(([value, count]) => usable(value, Number(count || 0)))
    .sort((left, right) => right[1] - left[1]);
  if (!ranked.length) return "";
  if (ranked.length > 1 && ranked[0][1] === ranked[1][1]) return "";
  return ranked[0][0];
}

function chooseUniqueInvoiceBatches(evidence, medicineKeys) {
  const choices = medicineKeys.map((key) => Object.entries(evidence.rows?.[key]?.fields?.batch || {})
    .map(([value, count]) => ({ value, count: Number(count || 0) }))
    .sort((left, right) => right.count - left.count).slice(0, 6));
  let best = { score: -1, values: [] };
  function visit(index, used, values, score) {
    if (index === choices.length) {
      if (score > best.score) best = { score, values: [...values] };
      return;
    }
    for (const choice of choices[index]) {
      if (used.has(choice.value)) continue;
      visit(index + 1, new Set([...used, choice.value]), [...values, choice.value], score + choice.count);
    }
    visit(index + 1, used, [...values, ""], score);
  }
  visit(0, new Set(), [], 0);
  return new Map(medicineKeys.map((key, index) => [key, best.values[index] || ""]));
}

function invoiceMonthValue(value) {
  const parsed = Date.parse(String(value || ""));
  if (!Number.isFinite(parsed)) return 0;
  const date = new Date(parsed);
  return date.getUTCFullYear() * 12 + date.getUTCMonth();
}

function invoiceExpiryNotBefore(value, invoiceMonth) {
  const match = /^(20\d{2})-(0[1-9]|1[0-2])$/.exec(String(value || ""));
  if (!match) return false;
  const expiryMonth = Number(match[1]) * 12 + Number(match[2]) - 1;
  return !invoiceMonth || expiryMonth >= invoiceMonth;
}

function strongestInvoiceOrder(counts) {
  const ranked = Object.entries(counts || {}).sort((left, right) => right[1] - left[1] || Number(left[0]) - Number(right[0]));
  return ranked.length ? Number(ranked[0][0]) : 999;
}

function firstRememberedInvoiceValue(cards, field) {
  return cards.map((card) => card.fields?.[field]).find((value) => ![undefined, null, ""].includes(value)) ?? "";
}

function invoiceRowArithmeticValid(row) {
  return Number(row.stock) > 0 && Number(row.cost_price) >= 0 && Number(row.line_total) > 0
    && Math.abs(Number(row.stock) * Number(row.cost_price) - Number(row.line_total)) < 0.01;
}

function invoiceRowEvidenceScore(row) {
  return ["name", "form", "unit", "stock", "cost_price", "selling_price", "line_total", "batch", "expiry"]
    .filter((field) => ![undefined, null, ""].includes(row[field])).length + (invoiceRowArithmeticValid(row) ? 10 : 0);
}

function invoiceReviewEvidenceScore(rows, targetTotal) {
  const completeFields = rows.reduce((sum, row) => sum + invoiceRowEvidenceScore(row), 0);
  const lineTotal = rows.reduce((sum, row) => sum + (invoiceRowArithmeticValid(row) ? Number(row.line_total) : 0), 0);
  return completeFields + (targetTotal && Math.abs(lineTotal - targetTotal) < 0.01 ? 100 : 0);
}

function chooseInvoiceRowsByTotal(choiceGroups, targetTotal) {
  if (!targetTotal || choiceGroups.some((choices) => choices.length === 0)) return null;
  let best = null;
  function visit(index, selected, total, score) {
    if (index === choiceGroups.length) {
      if (Math.abs(total - targetTotal) < 0.01 && (!best || score > best.score)) best = { rows: [...selected], score };
      return;
    }
    for (const row of choiceGroups[index]) {
      const nextTotal = total + Number(row.line_total);
      if (nextTotal <= targetTotal + 0.01) visit(index + 1, [...selected, row], nextTotal, score + invoiceRowEvidenceScore(row));
    }
  }
  visit(0, [], 0, 0);
  return best?.rows || null;
}

function normalizeMedicineKey(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function normalizeRememberedBatchDigits(rows) {
  const patterned = rows.filter((row) => /^[A-Z0-9]+-[A-Z]\d{2}$/i.test(String(row.batch || ""))).length;
  if (patterned < 2) return;
  rows.forEach((row) => {
    row.batch = String(row.batch || "").replace(/^(.+-[A-Z])[OQ](\d)$/i, (_match, prefix, digit) => `${prefix}0${digit}`);
  });
}

function invoiceRowsComplete(rows, invoiceTotal) {
  if (!rows.length || !rows.every((row) => row.name && row.form && row.unit && Number(row.stock) > 0
    && Number(row.cost_price) >= 0 && row.batch && /^20\d{2}-\d{2}$/.test(row.expiry)
    && Number(row.line_total) > 0 && Math.abs(Number(row.stock) * Number(row.cost_price) - Number(row.line_total)) < 0.01)) return false;
  const linesTotal = rows.reduce((sum, row) => sum + Number(row.line_total), 0);
  return invoiceTotal !== "" && Math.abs(linesTotal - Number(invoiceTotal)) < 0.01;
}

async function resizeImageForReading(file) {
  const bitmap = await createImageBitmap(file);
  const readingEdge = bitmap.width > bitmap.height ? 2400 : 1800;
  const scale = Math.min(1, readingEdge / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  const context = canvas.getContext("2d", { alpha: false });
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve, reject) => canvas.toBlob(
    (blob) => blob ? resolve(blob) : reject(new Error("I could not prepare this photo.")),
    "image/jpeg",
    0.92
  ));
}

async function prepareStockFixImage(file) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  canvas.getContext("2d", { alpha: false }).drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const blob = await new Promise((resolve, reject) => canvas.toBlob(
    (value) => value ? resolve(value) : reject(new Error("I could not prepare this image.")), "image/jpeg", 0.82
  ));
  canvas.width = 1;
  canvas.height = 1;
  return blob;
}

async function processStockFixEvidence(card, file, fileName, evidenceSource) {
  stopStockFixReading();
  activeStockFixScan?.abort();
  const controller = new AbortController();
  activeStockFixScan = controller;
  card.validation = "Reading this medicine locally...";
  render();
  try {
    const prepared = await prepareStockFixImage(file);
    if (controller.signal.aborted) return false;
    const body = new FormData();
    body.append("file", prepared, "stock-fix.jpg");
    const response = await fetch("/api/ms20/stock-fix-scan", { method: "POST", body, signal: controller.signal });
    const ocr = await response.json();
    if (!response.ok) throw new Error(ocr.detail || "I could not read this image.");
    const result = normalizeStockFixEvidence(ocr, pharmacyBrain.catalog, evidenceSource);
    card.fields = hydrateStockFixDraft(card.fields, result);
    card.recognition = result;
    card.source = `Stock fix ${evidenceSource}: ${fileName}`;
    card.photoEvidence = { fileName, localOnly: true, capturedAt: new Date().toISOString(), aiUsed: false };
    card.confidence = result.confidence;
    card.ui = { ...(card.ui || {}), activeSlide: result.canonicalName ? 1 : 0 };
    card.validation = result.canonicalName
      ? `Matched ${result.displayName} locally. Saved stock is authoritative; add corrected stock. Reason is optional.`
      : result.ambiguityChoices.length
        ? `Choose ${result.ambiguityChoices.join(" or ")}.`
        : "I could not safely match this image to one saved medicine. Type or say the medicine name; no stock value was invented.";
    persistActiveCards();
    render();
    focusCard(card.id);
    return Boolean(result.canonicalName);
  } catch (error) {
    if (error?.name !== "AbortError") card.validation = error?.message || "I could not read this image. You can retry now.";
    render();
    return false;
  } finally {
    if (activeStockFixScan === controller) activeStockFixScan = null;
  }
}

function addOnboardingCard() {
  addCard(createOnboardingCard());
}

function createOnboardingCard() {
  return createEditableCard({
    type: "OnboardingCard",
    title: "Set up your pharmacy",
    source: "Setup assistant",
    fields: { pharmacy: "", owner: "", branch: "Main", location: "", payments: "cash, mpesa, credit" },
    confidence: 0.86,
    validation: "Confirmed setup saves to cloud memory."
  });
}

function ensureOnboardingStarted() {
  if (state.onboarding.completed) {
    pruneCatalogOnboardingCards();
    ensureCatalogOnboardingStarted();
    return;
  }
  if (state.onboarding.started) return;
  state.cards.unshift(createOnboardingCard());
  state.onboarding.started = true;
  persistActiveCards();
}

function ensureCatalogOnboardingStarted() {
  if (!state.onboarding.completed) return;
  pruneCatalogOnboardingCards();
  if (catalogHasItems()) return;
  if (state.cards.some((card) => card.type === "CatalogOnboardingCard" || card.type === "CatalogImportCard")) return;
  state.cards.unshift(createCatalogChoiceCard());
  persistActiveCards();
}

function catalogHasItems() {
  return pharmacyBrain.catalog.length > 0 || state.catalog.items.length > 0;
}

function pruneCatalogOnboardingCards() {
  if (!catalogHasItems()) return;
  removeCardsByType(["CatalogOnboardingCard"]);
}

function hydrateResumeState() {
  const catalogItems = readCatalog();
  state.catalog = { items: catalogItems };
  pharmacyBrain.loadCatalog(catalogItems);
  state.onboarding = {
    started: false,
    completed: setupComplete() || catalogItems.length > 0
  };
  if (catalogItems.length > 0 && !setupComplete()) {
    safeLocalStorage()?.setItem(SETUP_KEY, "true");
  }
  state.feed = readFeed();
  state.cards = readActiveCards();
  reconcileResumeState();
}

function reconcileResumeState() {
  state.feed = state.feed.filter((item) => !isLegacyCatalogUpdateFeed(item));
  persistFeed();
  reconcileActivityHubCard();
  const resumedExportCards = state.cards.filter((card) =>
    card.type === "ExportHubCard"
    && (!card.fields?.pharmacy_id || card.fields.pharmacy_id === state.pharmacy.id)
  );
  if (resumedExportCards.length) {
    const keeper = resumedExportCards[0];
    keeper.id = `card-export-hub-${state.pharmacy.id}`;
    keeper.fields = {
      ...keeper.fields,
      pharmacy_id: state.pharmacy.id,
      expanded: false,
      history_open: false,
      history: readExportHistory()
    };
    keeper.fields.last_download = keeper.fields.history[0]?.summary || "Ready to generate an export.";
    state.cards = state.cards.filter((card) =>
      card.type !== "ExportHubCard"
      || card === keeper
      || (card.fields?.pharmacy_id && card.fields.pharmacy_id !== state.pharmacy.id)
    );
  }
  if (state.onboarding.completed) {
    removeCardsByType(["OnboardingCard"]);
  }
  if (catalogHasItems()) {
    removeCardsByType(["CatalogOnboardingCard"]);
  }
  state.cards.forEach((card) => {
    if (card.type === "CatalogImportCard" && card.fields?.import_mode === "invoice_ocr") {
      refreshInvoiceImportCompleteness(card, catalogRowsForCard(card));
    }
  });
  consolidateEmptyPasteDrafts();
  quarantineUnreadableActiveCards();
  state.onboarding.started = state.cards.some((card) => card.type === "OnboardingCard");
  persistFeed();
  persistActiveCards();
}

function quarantineUnreadableActiveCards() {
  const quarantined = [];
  state.cards = state.cards.filter((card) => {
    try {
      cardTemplate(card);
      return true;
    } catch (error) {
      quarantined.push({ card, reason: `${error?.name || "RenderError"}: ${String(error?.message || "Unreadable card").slice(0, 180)}`, quarantined_at: new Date().toISOString() });
      return false;
    }
  });
  if (!quarantined.length) return;
  const storage = safeLocalStorage();
  let previous = [];
  try {
    previous = JSON.parse(storage?.getItem(QUARANTINED_CARDS_KEY) || "[]");
  } catch {
    previous = [];
  }
  storage?.setItem(QUARANTINED_CARDS_KEY, JSON.stringify([...quarantined, ...(Array.isArray(previous) ? previous : [])].slice(0, ACTIVE_CARD_RESUME_LIMIT)));
}

function consolidateEmptyPasteDrafts() {
  state.cards = state.cards.filter((card) => {
    const emptyPasteDraft = card.type === "CatalogImportCard"
      && card.fields?.entry_mode === "paste_input"
      && !String(card.fields?.items_text || "").trim();
    if (!emptyPasteDraft) return true;
    return false;
  });
}

function resetOnboarding() {
  const storage = safeLocalStorage();
  storage?.removeItem(SETUP_KEY);
  storage?.removeItem(CATALOG_KEY);
  storage?.removeItem(NOTIFICATION_KEY);
  storage?.removeItem(FEED_KEY);
  storage?.removeItem(ACTIVE_CARDS_KEY);
  storage?.removeItem(exportHistoryKey());
  state.onboarding.completed = false;
  state.onboarding.started = false;
  state.catalog.items = [];
  state.notifications = [];
  state.feed = [];
  pharmacyBrain.loadCatalog([]);
  state.cards = state.cards.filter((card) => ![
    "OnboardingCard",
    "CatalogOnboardingCard",
    "CatalogImportCard",
    "DocumentExportCard"
  ].includes(card.type));
  persistFeed();
  persistActiveCards();
  ensureOnboardingStarted();
  refreshNotifications();
  render();
}

function addReportCard() {
  addCard(createEditableCard({
    type: "ReportCard",
    title: "Check report",
    source: "Today report",
    fields: {
      period: "Today",
      focus: "Sales, stock, cash, M-Pesa, credit"
    },
    confidence: 0.94,
    validation: "Generate this report from the pharmacy's saved records. Nothing is sent to WhatsApp."
  }));
}

async function generateReport(card) {
  if (navigator.onLine === false) {
    card.validation = "This report needs the live pharmacy records. Reconnect, then tap Generate report again.";
    render();
    return;
  }
  stopCardReading(card.id);
  card.submitting = true;
  card.validation = "Generating report from saved pharmacy records…";
  persistActiveCards();
  render();
  const controller = new AbortController();
  const startedAt = performance.now();
  activeReportRequest?.controller.abort();
  activeReportRequest = { cardId: card.id, controller };
  const slowNoticeId = window.setTimeout(() => {
    if (activeReportRequest?.controller !== controller) return;
    card.validation = "Still reading the saved pharmacy records. Keep this report open; no duplicate request has been sent.";
    render();
  }, 10000);
  const timeoutId = window.setTimeout(() => controller.abort(), 30000);
  try {
    const selectedPeriod = String(card.fields?.period || "Today").trim();
    const reportPeriod = selectedPeriod === "Custom date"
      ? String(card.fields?.custom_start || "")
      : selectedPeriod === "Custom date range"
        ? `${card.fields?.custom_start || ""} to ${card.fields?.custom_end || ""}`
        : selectedPeriod;
    if (!reportPeriod || reportPeriod.startsWith(" to ") || reportPeriod.endsWith(" to ")) throw new Error("Choose the report date or both range dates.");
    const query = new URLSearchParams({ send_whatsapp: "false", refresh: String(Date.now()), period: reportPeriod });
    const response = await fetch(`/reports/daily?${query}`, {
      method: "POST",
      cache: "no-store",
      headers: { "Cache-Control": "no-cache" },
      signal: controller.signal
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || "The report could not be generated right now.");
    const generatedAt = result.generated_at ? new Date(result.generated_at) : new Date();
    card.fields = {
      period: selectedPeriod.startsWith("Custom") ? reportPeriod : selectedPeriod,
      focus: "Sales, stock, cash, M-Pesa, credit",
      report_date: result.start_date === result.end_date ? result.start_date : `${result.start_date} to ${result.end_date}`,
      generated_at: Number.isNaN(generatedAt.getTime()) ? "Just now" : generatedAt.toLocaleString("en-KE", { timeZone: "Africa/Nairobi" }),
      report_text: result.report || "No report details were returned."
    };
    card.title = reportPeriod.toLowerCase() === "today" ? "Today's report" : `${selectedPeriod.startsWith("Custom") ? reportPeriod : selectedPeriod} report`;
    card.reportSelectionDirty = false;
    const elapsedSeconds = Math.max(0.1, (performance.now() - startedAt) / 1000).toFixed(1);
    card.validation = result.source === "saved_historical_sales_and_activity_records"
      ? `Fresh historical report generated in ${elapsedSeconds} seconds from saved sales and activity records. Current stock was not presented as historical stock. Nothing was sent to WhatsApp or saved as a duplicate report.`
      : `Fresh report generated in ${elapsedSeconds} seconds from saved sales, activity and stock records. Nothing was sent to WhatsApp or saved as a duplicate report.`;
  } catch (error) {
    card.validation = error?.name === "AbortError"
      ? "Report refresh exceeded 30 seconds. The last successful report remains below and its date and Generated At are intentionally unchanged; tap Refresh report to try again."
      : error?.message || "The report could not be generated right now.";
  } finally {
    window.clearTimeout(slowNoticeId);
    window.clearTimeout(timeoutId);
    if (activeReportRequest?.controller === controller) activeReportRequest = null;
    card.submitting = false;
    persistActiveCards();
    render();
    focusCard(card.id);
  }
}

function addSyncCard() {
  const status = syncAdapter.status();
  addCard(createEditableCard({
    type: "SyncReviewCard",
    title: "Check sync",
    source: "Offline queue",
    fields: {
      pending: status.pending,
      last_sync: status.lastSync || "Not synced",
      conflict: status.conflict?.reason || "None",
      backend: state.liveBackend?.health?.ok ? "detected" : "not detected",
      sheets: state.liveBackend?.readinessSummary?.sheets ? "connected" : "check",
      baileys: state.liveBackend?.readinessSummary?.baileys ? "confirmed" : "check"
    },
    confidence: 0.9,
    validation: "Queued actions sync with idempotent action ids."
  }));
}

function addStockCorrectionCard() {
  addCard(createEditableCard({
    type: "StockCorrectionCard",
    title: "Check stock correction",
    source: "Manual stock fix",
    fields: { medicine: "", current_stock: "", correct_stock: "", reason: "" },
    confidence: 0.82,
    validation: "Choose a saved medicine and add the corrected stock. Reason is optional. Nothing changes until you confirm."
  }));
}

function addStockCorrectionCardFromMedicine(medicine, source = "Pharmacy Catalog") {
  const currentStock = trustedCatalogStock(medicine) ?? "";
  addCard(createEditableCard({
    type: "StockCorrectionCard",
    title: "Check stock correction",
    source,
    fields: { medicine: medicine?.name || medicine?.medicine || "", current_stock: currentStock, correct_stock: "", reason: "" },
    confidence: 1,
    validation: "Saved medicine and current stock are filled. Add corrected stock; reason is optional."
  }));
}

function startCatalogStockFix(medicineId) {
  const medicine = pharmacyBrain.catalog.find((item) => catalogItemId(item) === String(medicineId));
  if (!medicine) return;
  removeCardsByType(["StockCorrectionCard"]);
  addStockCorrectionCardFromMedicine(medicine);
}

function startStockFixPhoto(cardId, camera) {
  stopStockFixReading();
  pendingStockFixEvidenceSource = camera ? "camera" : "photo";
  state.stockFixPhotoCardId = cardId;
  state.pendingScanType = "stock_fix_photo";
  if (camera) void openLightweightCamera("stock_fix_photo");
  else root.querySelector("#photoInput")?.click();
}

function startStockFixFile(cardId) {
  stopStockFixReading();
  pendingStockFixEvidenceSource = "file";
  state.stockFixPhotoCardId = cardId;
  root.querySelector("#stockFixFileInput")?.click();
}

function refreshStockFixDraftControls(card) {
  const guidance = stockCorrectionGuidance(card.fields, pharmacyBrain.catalog);
  card.validation = guidance.message;
  const button = root.querySelector(`[data-confirm-card="${card.id}"]`);
  if (button) {
    button.disabled = !guidance.ready;
    button.title = guidance.ready ? "" : guidance.message;
  }
  const note = root.querySelector(`[data-card-note="${card.id}"]`);
  if (note) note.textContent = guidance.message;
}

function fillTrustedStockForDraft(card, medicineText) {
  const match = matchMedicine(medicineText, pharmacyBrain.catalog);
  if (match.status !== "matched") return;
  const savedStock = trustedCatalogStock(match.matches[0]);
  if (savedStock === null) return;
  card.fields.current_stock = savedStock;
  const currentInput = root.querySelector(`[data-card-id="${card.id}"][data-field="current_stock"]`);
  if (currentInput) currentInput.value = String(savedStock);
}

function stockFixSlideInstruction(slide) {
  return ["Choose the saved medicine.", "Check current stock.", "Add corrected stock. Reason is optional."][slide] || "Review the stock fix.";
}

function handleStockFixVoice(card, transcript) {
  card.ui = { ...(card.ui || {}), voiceGuided: true };
  card.voiceTranscripts = [...(card.voiceTranscripts || []), transcript].slice(-6);
  const guidedStage = stockFixGuidedStage(card);
  const learnedCanonical = pronunciationMemory.resolve(transcript);
  const spokenInput = learnedCanonical || transcript;
  const result = applyStockCorrectionVoice({ ...card.fields, active_slide: guidedStage }, spokenInput, pharmacyBrain.catalog);
  if (result.intent === "cancel") {
    rejectCard(card.id);
    state.voice.status = "Stock fix cancelled. Nothing changed.";
    return;
  }
  if (result.intent === "read") return readCardAloud(card.id);
  if (result.intent === "confirm") {
    if (requestGuidedStockFixConfirmation(card)) return;
    return confirmCard(card.id);
  }
  if (result.intent === "disambiguate") {
    card.validation = `I heard “${transcript}”. Did you mean ${result.choices.join(" or ")}? Tap Mic, then say one exact medicine name.`;
    card.pendingSpokenMedicine = transcript;
    card.ui = { ...(card.ui || {}), voiceAwaitingManualRetry: true };
  } else if (result.intent === "retry") {
    card.validation = `I heard “${transcript}”. I could not safely match that medicine. Tap Mic, then say the exact saved name, or type it.`;
    card.ui = { ...(card.ui || {}), voiceAwaitingManualRetry: true };
  } else {
    const { active_slide, ...fields } = result.fields;
    card.fields = fields;
    card.ui = { ...(card.ui || {}), voiceAwaitingManualRetry: false };
    if (card.pendingSpokenMedicine && fields.medicine) {
      pronunciationMemory.remember(card.pendingSpokenMedicine, fields.medicine);
      card.learnedSpokenMedicine = card.pendingSpokenMedicine;
      delete card.pendingSpokenMedicine;
    }
    if (guidedStage === 0 && fields.medicine && !learnedCanonical && String(transcript).trim().toLowerCase() !== String(fields.medicine).trim().toLowerCase()) {
      pronunciationMemory.remember(transcript, fields.medicine);
      card.learnedSpokenMedicine = transcript;
    }
    card.ui = {
      ...(card.ui || {}),
      activeSlide: result.slide ?? card.ui?.activeSlide ?? 0,
      reviewedSlides: undefined,
      voiceReviewStarted: false,
      voiceReviewCompleted: false
    };
    card.validation = stockFixVoiceProgressMessage(card, result);
  }
  persistActiveCards();
  render();
  focusCard(card.id);
}

function requestGuidedStockFixConfirmation(card) {
  if (!card?.ui?.voiceGuided || card.ui.voiceReviewCompleted) return false;
  if (card.ui.voiceReviewStarted && stockFixReading?.cardId === card.id) {
    card.validation = "Finish the complete review. MS2.0 will then ask you to say Confirm again to apply it.";
    persistActiveCards();
    render();
    focusCard(card.id);
    return true;
  }
  card.ui = { ...(card.ui || {}), reviewedSlides: [0, 1, 2], voiceReviewStarted: true, voiceReviewCompleted: false };
  card.validation = "First Confirm received. Reviewing Medicine, Stock and Reason now. After the review, say Confirm again to apply once.";
  persistActiveCards();
  render();
  focusCard(card.id);
  cycleStockFixReview(card.id);
  return true;
}

function forgetStockFixPronunciation(cardId) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "StockCorrectionCard");
  if (!card?.learnedSpokenMedicine) return;
  pronunciationMemory.forget(card.learnedSpokenMedicine);
  delete card.learnedSpokenMedicine;
  card.validation = "Saved voice name removed for this pharmacy. Canonical medicine data is unchanged.";
  persistActiveCards();
  render();
  focusCard(card.id);
}

function stockFixVoicePrompt(card) {
  const slide = stockFixGuidedStage(card);
  if (slide === 0) return "Say the medicine name.";
  if (slide === 1) return card.fields?.current_stock === "" ? "Say current and new stock." : `Current stock is ${card.fields.current_stock}. Say the new correct stock.`;
  return "Say a reason, or say Confirm once to review and again after review to apply.";
}

function stockFixGuidedStage(card) {
  if (!String(card?.fields?.medicine || "").trim()) return 0;
  if (card?.fields?.correct_stock === "" || card?.fields?.correct_stock === null || card?.fields?.correct_stock === undefined) return 1;
  return 2;
}

function stockFixVoiceProgressMessage(card, result = {}) {
  const stage = stockFixGuidedStage(card);
  if (stage === 1) {
    if (result.currentAcknowledged) return `Current stock ${card.fields.current_stock} noted. Next, say the new correct stock.`;
    return `${card.fields.medicine} matched in the Pharmacy Catalog. Saved current stock is ${card.fields.current_stock}. Next, say the new correct stock.`;
  }
  if (stage === 2) {
    if (result.review) return "Reason not provided. Say Confirm once to hear the complete review, then say Confirm again after the review to apply this stock fix.";
    return `New correct stock ${card.fields.correct_stock} noted. Reason is optional. Next, say a reason, or say Confirm once to review and again after review to apply.`;
  }
  return "Say the medicine name.";
}

function announceStockFixNextStep(card) {
  const stage = stockFixGuidedStage(card);
  card.ui = { ...(card.ui || {}), activeSlide: stage };
  card.validation = stockFixVoiceProgressMessage(card);
  persistActiveCards();
  render();
  focusCard(card.id);
  const message = card.validation;
  if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
    setTimeout(() => startVoiceCapture(), 650);
    return;
  }
  const utterance = new SpeechSynthesisUtterance(message);
  utterance.lang = "en-KE";
  utterance.onend = () => setTimeout(() => startVoiceCapture(), 350);
  utterance.onerror = () => setTimeout(() => startVoiceCapture(), 350);
  speakUtterance(utterance);
}

function cycleStockFixReview(cardId) {
  readCardAloud(cardId);
}

function addCard(card) {
  activeCardViewportAnchor = null;
  if (card.type === "CatalogImportCard") removeCardsByType(["CatalogOnboardingCard"]);
  state.cards.unshift(card);
  cloudGateway.saveCardHistory(card);
  rememberInvoiceCard(card);
  persistActiveCards();
  render();
  focusCard(card.id);
}

function focusCard(cardId) {
  activeCardViewportAnchor = null;
  const card = Array.from(root.querySelectorAll("[data-card-id]"))
    .find((element) => element.dataset.cardId === String(cardId));
  card?.scrollIntoView({ block: "start", behavior: "smooth" });
}

function addFeed(type, text, metadata = {}) {
  activeCardViewportAnchor = null;
  state.feed.push({ id: `feed-${Date.now()}`, type, text, time: nowLabel(), ...metadata });
  state.feed = state.feed.slice(-FEED_RESUME_LIMIT);
  persistFeed();
}

function openCompletedSale(reference, options = {}) {
  const transaction = completedSaleByReference(transactionEngine.list(), reference);
  if (!transaction) {
    addFeed("system", "This completed sale could not be found in local transaction history. Nothing was changed.");
    render();
    return;
  }
  state.cards = state.cards.filter((card) => !["CompletedSaleDetailCard", "SaleAdjustmentReviewCard", "SaleAdjustmentDetailCard"].includes(card.type));
  const fields = saleDetailFields(transaction);
  const availability = saleAdjustmentEngine.availability(transaction);
  fields.adjustment_available = availability.available;
  fields.adjustment_remaining_quantity = availability.remaining_quantity;
  fields.adjustment_block_message = availability.message;
  const card = createEditableCard({
    type: "CompletedSaleDetailCard",
    title: `Sale ${fields.sale_number}`,
    source: "Local transaction history",
    fields,
    confidence: 1,
    validation: "Original completed sale — adjustments require a separate review."
  });
  state.cards.push(card);
  persistActiveCards();
  if (options.adjustmentType === "return") {
    startSaleAdjustment(card.id, "return");
    return;
  }
  render();
  focusCard(card.id);
}

function startSaleAdjustment(cardId, adjustmentType) {
  const detailCard = state.cards.find((card) => card.id === cardId && card.type === "CompletedSaleDetailCard");
  if (!detailCard) return;
  const transaction = completedSaleByReference(transactionEngine.list(), {
    saleNumber: detailCard.fields?.sale_number,
    transactionId: detailCard.fields?.transaction_id
  });
  const availability = saleAdjustmentEngine.availability(transaction);
  if (!availability.available) {
    detailCard.fields.adjustment_available = false;
    detailCard.fields.adjustment_remaining_quantity = availability.remaining_quantity;
    detailCard.fields.adjustment_block_message = availability.message;
    persistActiveCards();
    render();
    focusCard(detailCard.id);
    return;
  }
  const fields = saleAdjustmentEngine.review(transaction, adjustmentType, 1);
  if (!fields) return;
  const card = createEditableCard({
    type: "SaleAdjustmentReviewCard",
    title: `${String(adjustmentType).replace(/^./, (letter) => letter.toUpperCase())} Sale ${fields.original_sale_number}`,
    source: "Linked completed sale",
    fields,
    confidence: 1,
    validation: "Review only. No stock or finance mutation has occurred."
  });
  state.cards = state.cards.filter((item) => item.id !== detailCard.id && item.type !== "SaleAdjustmentReviewCard");
  state.cards.push(card);
  persistActiveCards();
  render();
  focusCard(card.id);
}

function updateSaleAdjustmentReview(cardId, patch = {}) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "SaleAdjustmentReviewCard");
  if (!card) return;
  const transaction = completedSaleByReference(transactionEngine.list(), {
    saleNumber: card.fields.original_sale_number,
    transactionId: card.fields.original_transaction_id
  });
  const quantity = Math.max(1, Math.min(card.fields.remaining_quantity, Number(card.fields.adjustment_quantity) + Number(patch.delta || 0)));
  const fields = saleAdjustmentEngine.review(transaction, card.fields.adjustment_type, quantity, {
    reviewId: card.fields.review_id,
    restoreStock: patch.restoreStock ?? card.fields.restore_stock
  });
  if (!fields) return;
  card.fields = fields;
  persistActiveCards();
  render();
}

function confirmSaleAdjustment(cardId) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "SaleAdjustmentReviewCard");
  if (!card || card.submitting) return;
  card.submitting = true;
  const result = saleAdjustmentEngine.confirm(card.fields);
  if (result.rejected) {
    card.submitting = false;
    card.validation = "This quantity exceeds the remaining unadjusted quantity.";
    render();
    return;
  }
  const record = result.record;
  if (result.created && Number(record.base_stock_to_restore) > 0) {
    const match = pharmacyBrain.findMedicine(record.medicine);
    if (match.status === "matched") {
      const medicine = match.matches[0];
      const current = Number(medicine.stockLeft);
      if (Number.isFinite(current)) {
        medicine.stockLeft = current + Number(record.base_stock_to_restore);
        state.catalog.items = pharmacyBrain.catalog;
        safeLocalStorage()?.setItem(CATALOG_KEY, JSON.stringify(state.catalog.items));
        void cloudGateway.saveCatalog(state.pharmacy.id, state.catalog.items);
      }
    }
  }
  syncAdapter.queueAction({
    id: `action-${record.id}`,
    type: "SaleAdjustment",
    fields: record,
    localFirst: true,
    aiUsed: false
  });
  state.cards = state.cards.filter((item) => item.id !== cardId);
  addFeed("system", `${adjustmentTypeLabel(record.adjustment_type)} for Sale ${record.original_sale_number}`, {
    adjustmentReference: {
      adjustmentId: record.id,
      type: record.adjustment_type,
      saleNumber: record.original_sale_number,
      recordNumber: record.adjustment_number,
      medicine: record.medicine,
      quantity: record.adjustment_quantity,
      financialAdjustment: record.financial_adjustment,
      stockAddedBack: record.stock_to_restore
    }
  });
  persistActiveCards();
  render();
}

function openSaleAdjustment(adjustmentId) {
  const record = saleAdjustmentEngine.list().find((item) => item.id === adjustmentId);
  if (!record) {
    addFeed("system", "This sale adjustment could not be found locally. Nothing was changed.");
    render();
    return;
  }
  state.cards = state.cards.filter((card) => !["CompletedSaleDetailCard", "SaleAdjustmentReviewCard", "SaleAdjustmentDetailCard"].includes(card.type));
  const card = createEditableCard({
    type: "SaleAdjustmentDetailCard",
    title: `${adjustmentTypeLabel(record.adjustment_type)} for Sale ${record.original_sale_number}`,
    source: "Local adjustment ledger",
    fields: record,
    confidence: 1,
    validation: "Confirmed linked sale adjustment."
  });
  state.cards.push(card);
  persistActiveCards();
  render();
  focusCard(card.id);
}

function adjustmentTypeLabel(type) {
  return String(type || "adjustment").replace(/^./, (letter) => letter.toUpperCase());
}

function adjustmentMoneyResult(reference) {
  const amount = `KES ${reference.financialAdjustment}`;
  if (reference.type === "credit") return `${amount} account credit created`;
  if (reference.type === "refund") return `${amount} refunded`;
  return `${amount} reversed`;
}

function updateCardField(cardId, field, value) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card) return;
  if (card.type === "SaleCard" && field === "unit" && String(card.fields?.unit || "") !== String(value || "")) {
    card.fields.selling_price = "";
    card.fields.pack_conversion = "";
  }
  card.fields[field] = value;
  if (card.type === "SaleCard") {
    prepareProductionSaleCard(card, pharmacyBrain.findMedicine(card.fields?.medicine));
    refreshProductionSaleCardControls(card);
  }
  if (card.type === "ReportCard" && (field === "period" || field === "custom_start" || field === "custom_end")) {
    if (activeReportRequest?.cardId === cardId) activeReportRequest.controller.abort();
    if (field === "period" && !String(value).startsWith("Custom")) {
      delete card.fields.custom_start;
      delete card.fields.custom_end;
    }
    card.reportSelectionDirty = Boolean(card.fields?.report_text);
    const selection = field === "period" ? String(value) : String(card.fields?.period || "Custom period");
    card.title = selection.toLowerCase() === "today" ? "Today's report" : `${selection} report`;
    card.validation = card.reportSelectionDirty
      ? "Period changed. The last successful report remains below; tap Refresh report to load the selected period."
      : "Period selected. Tap Generate report to load it from saved pharmacy records.";
    persistActiveCards();
    render();
    return;
  }
  if (card.type === "StockCorrectionCard") {
    card.ui = { ...(card.ui || {}), reviewedSlides: undefined, voiceReviewStarted: false, voiceReviewCompleted: false };
    if (field === "medicine") fillTrustedStockForDraft(card, value);
    refreshStockFixDraftControls(card);
  }
  if (card.type === "CatalogImportCard" && card.fields?.entry_mode === "paste_input" && field === "items_text") {
    delete card.fields.review_feedback;
    card.validation = "Paste one medicine per line, then review the proposed rows before saving.";
  }
  persistActiveCards();
}

function refreshProductionSaleCardControls(card) {
  const workspace = root.querySelector(`[data-medicine-workspace="${card.id}"]`);
  if (!workspace) return;
  for (const field of PRODUCTION_SALE_REFRESH_FIELDS) {
    const controls = workspace.querySelectorAll(`input[data-card-id="${card.id}"][data-field="${field}"], select[data-card-id="${card.id}"][data-field="${field}"]`);
    controls.forEach((control) => {
      if (document.activeElement !== control) control.value = String(card.fields?.[field] ?? "");
    });
  }
  const summary = workspace.querySelector(`[data-sale-summary="${card.id}"]`);
  if (summary) summary.textContent = productionSaleSummary(card.fields);
  const confirm = workspace.querySelector(`[data-confirm-card="${card.id}"]`);
  if (confirm) {
    const blocker = medicineReviewBlocker(card);
    confirm.disabled = Boolean(blocker);
    confirm.title = blocker || "";
  }
  const note = root.querySelector(`[data-card-note="${card.id}"]`);
  if (note) note.textContent = ownerCardNote(card);
}

function updateCatalogImportCell(cardId, rowIndex, field, value) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card || card.type !== "CatalogImportCard") return;
  const rows = catalogRowsForCard(card);
  const index = Number(rowIndex);
  if (!Number.isInteger(index) || index < 0 || index >= rows.length) return;
  rows[index][field] = value;
  if (card.fields?.import_mode === "invoice_ocr") card.fields.invoice_owner_edited = "true";
  persistCatalogRows(card, rows);
  refreshInvoiceImportCompleteness(card, rows);
  rememberInvoiceCard(card);
  persistActiveCards();
}

function moveCatalogImportRow(cardId, rowIndex, direction) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card || card.type !== "CatalogImportCard") return;
  if (!catalogReviewCapabilities(card).reorderable) return;
  const rows = reorderedCatalogRows(catalogRowsForCard(card), rowIndex, direction);
  persistCatalogRows(card, rows);
  refreshInvoiceImportCompleteness(card, rows);
  rememberInvoiceCard(card);
  persistActiveCards();
  render();
}

function refreshInvoiceImportCompleteness(card, rows) {
  if (card.fields?.import_mode !== "invoice_ocr") return;
  const complete = invoiceRowsComplete(rows, card.fields.invoice_total);
  card.fields.import_incomplete = complete ? "false" : "true";
  card.validation = complete
    ? "Check every field against the invoice. If repeated scans differ, edit the fields to match the invoice, then approve."
    : "Some details may be missing or incorrect. Scan again once if useful; if repeated scans differ, edit every field to match the invoice before saving.";
}

function addCatalogImportRow(cardId) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card || card.type !== "CatalogImportCard") return;
  const rows = catalogRowsForCard(card);
  rows.push(emptyCatalogRow());
  persistCatalogRows(card, rows);
  persistActiveCards();
  render();
}

function reviewPasteList(cardId) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card || card.type !== "CatalogImportCard") return;
  const text = String(card.fields?.items_text || "").trim();
  if (!text) {
    card.validation = "Paste at least one medicine line before review.";
    card.fields.review_feedback = card.validation;
    persistActiveCards();
    render();
    return;
  }
  const parsed = parseBulkMedicineList(text, sourceBrain);
  const { existing, newItems } = prepareCatalogImport(parsed.items, pharmacyBrain.catalog);
  if (newItems.length === 0) {
    card.validation = `No new medicines found. Already in this pharmacy: ${existing.map((item) => item.name).join(", ")}.`;
    card.fields.review_feedback = card.validation;
    persistActiveCards();
    render();
    return;
  }
  applyCatalogPasteReview(card, newItems, {
    existing,
    unclearCount: parsed.unclear.length
  });
}

function applyCatalogPasteReview(card, newItems, {
  existing = [],
  unclearCount = 0,
  method = "bulk paste",
  source = "",
  feedback = ""
} = {}) {
  card.fields.entry_mode = "review";
  card.fields.method = method;
  card.fields.catalog_rows = JSON.stringify(newItems);
  card.fields.items_text = catalogItemsToText(newItems);
  card.fields.existing_medicines_ignored = existing.map((item) => item.name).join(", ");
  if (source) card.source = source;
  card.validation = feedback || [
    `${newItems.length} new medicine(s) ready for review.`,
    existing.length ? `${existing.length} existing medicine(s) were not added again: ${existing.map((item) => item.name).join(", ")}.` : "No existing catalog medicines were repeated.",
    unclearCount ? `${unclearCount} line(s) need correction.` : "Check every field, then approve."
  ].join(" ");
  card.fields.review_feedback = card.validation;
  persistActiveCards();
  refreshNotifications();
  render();
  focusCard(card.id);
}

function startCatalogPasteVoice(cardId) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "CatalogImportCard");
  if (!card) return;
  startVoiceCapture((transcript) => {
    const current = String(card.fields?.items_text || "").trim();
    card.fields.items_text = [current, String(transcript || "").trim()].filter(Boolean).join("\n");
    card.fields.entry_mode = "paste_input";
    card.validation = "Voice added to the medicine list. Check the words, then tap Review list.";
    card.fields.review_feedback = card.validation;
    persistActiveCards();
    render();
    focusCard(card.id);
  });
}

function startCatalogPastePhoto(cardId, camera) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "CatalogImportCard");
  if (!card) return;
  state.catalogPasteCaptureCardId = card.id;
  state.pendingScanType = "shelf_photo";
  if (camera) void openLightweightCamera("shelf_photo");
  else root.querySelector("#photoInput")?.click();
}

function confirmCard(cardId) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card || card.submitting) return;
  if (card.type === "SaleCard") prepareProductionSaleCard(card, pharmacyBrain.findMedicine(card.fields?.medicine));
  if (card.type === "ReportCard") return void generateReport(card);
  if (card.type === "StockCorrectionCard" && requestGuidedStockFixConfirmation(card)) return;
  card.submitting = true;
  const confirmationBlocker = medicineReviewBlocker(card);
  if (confirmationBlocker) {
    card.submitting = false;
    card.validation = confirmationBlocker;
    persistActiveCards();
    render();
    return;
  }
  if (card.type === "StockCorrectionCard") {
    const review = reviewStockCorrection(card.fields, pharmacyBrain.catalog);
    if (!review.ok) {
      card.submitting = false;
      card.validation = review.message;
      persistActiveCards();
      render();
      return;
    }
    card.fields = review.fields;
    completeStockCorrection(card);
    return;
  }
  if (card.type === "CatalogOnboardingCard") {
    removeCard(cardId);
    addCard(createPasteImportCard());
    return;
  }
  if (card.type === "CatalogImportCard") {
    if (card.fields?.import_mode === "invoice_ocr" && card.fields?.import_incomplete === "true") {
      card.validation = "This scan is missing invoice details. Scan the whole invoice again before approving.";
      persistActiveCards();
      render();
      return;
    }
    approveCatalogImport(card);
    removeCard(cardId);
    refreshNotifications();
    render();
    return;
  }
  if (card.type === "VisualScanCard" || card.type === "PhotoReviewCard" || card.type === "InvoiceCard") {
    saveCatalogFromReviewCard(card);
  }
  if (card.type === "MedicineMatchCard" && card.fields?.medicine) {
    saveCatalogItems([medicineRecordFromFields(card.fields, { source: "sale_time_learning" })]);
  }
  if (card.type === "SaleCard") saveApprovedSalePackFacts(card);
  if (card.type === "OnboardingCard") {
    state.onboarding.completed = true;
    safeLocalStorage()?.setItem(SETUP_KEY, "true");
  }
  recordCard(card);
  removeCard(cardId);
  pruneCatalogOnboardingCards();
  if (card.type === "OnboardingCard") ensureCatalogOnboardingStarted();
  refreshNotifications();
  render();
}

function approveCatalogImport(card) {
  const text = card.fields?.items_text || "";
  const parsed = text.includes("|") ? { items: parseCatalogText(text), unclear: [] } : parseBulkMedicineList(text, sourceBrain);
  const saved = saveCatalogItems(parsed.items);
  pruneCatalogOnboardingCards();
  const summary = buildCatalogSavedSummary(saved, parsed.unclear || []);
  addFeed("system", `Catalog saved. ${summary}`);
  addCard(buildDocumentCard({
    title: "Catalog export ready",
    document: "Pharmacy medicine catalog",
    format: "CSV",
    itemCount: pharmacyBrain.catalog.length
  }));
  showCatalogWorkspace();
}

function showCatalogWorkspace() {
  state.cards = state.cards.filter((card) => card.type !== "CatalogWorkspaceCard");
  state.cards.unshift(createCatalogWorkspaceCard(pharmacyBrain.catalog.length));
  persistActiveCards();
}

function navigateToCatalogWorkspace() {
  state.ui.screen = "chat";
  state.ui.workspace = "operations";
  showCatalogWorkspace();
}

function catalogEditDraft(card) {
  try {
    return JSON.parse(card.fields?.edit_draft || "{}");
  } catch {
    return {};
  }
}

function openCatalogMedicine(medicineId) {
  const card = state.cards.find((item) => item.type === "CatalogWorkspaceCard");
  const medicine = pharmacyBrain.catalog.find((item) => catalogItemId(item) === String(medicineId));
  if (!card || !medicine) return;
  card.fields.selected_id = catalogItemId(medicine);
  card.fields.edit_draft = JSON.stringify(createCatalogEditDraft(medicine));
  card.fields.voice_field = "";
  card.fields.voice_feedback = "";
  persistActiveCards();
  render();
}

function updateCatalogEditDraft(cardId, field, value) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "CatalogWorkspaceCard");
  if (!card || !CATALOG_EDIT_FIELDS.includes(field)) return;
  const draft = catalogEditDraft(card);
  draft[field] = value;
  card.fields.edit_draft = JSON.stringify(draft);
  persistActiveCards();
  refreshCatalogEditReviewDom(card, draft);
}

function refreshCatalogEditReviewDom(card, draft = catalogEditDraft(card)) {
  const warning = root.querySelector(".catalog-edit-warning, .catalog-change-summary");
  const review = reviewCatalogEdit(pharmacyBrain.catalog, card.fields.selected_id, draft);
  const presentation = catalogEditPresentation(review);
  const status = root.querySelector("[data-catalog-edit-status]");
  if (status) {
    status.textContent = presentation.status;
    status.dataset.state = presentation.state;
  }
  const description = root.querySelector("[data-catalog-edit-description]");
  if (description) description.textContent = presentation.description;
  if (warning) {
    warning.className = review.error ? "catalog-edit-warning" : "catalog-change-summary";
    warning.textContent = review.error || (review.changes.length ? `Review: ${review.changes.length} field${review.changes.length === 1 ? "" : "s"} changed — ${review.changes.map(fieldLabel).join(", ")}.` : "No changes yet.");
  }
  const approve = root.querySelector('[data-action="approve-catalog-edit"]');
  if (approve) approve.disabled = !review.valid || !review.changes?.length;
}

function refreshContextualFieldVoiceDom() {
  const anchor = activeVoiceViewportAnchor;
  if (!anchor || state.ui.screen !== "chat") return false;
  const target = root.querySelector(anchor.selector);
  const card = state.cards.find((item) => item.id === anchor.cardId);
  if (!target || !card) return false;

  if (card.type === "SaleCard") {
    const nextValue = String(card.fields?.[anchor.field] ?? "");
    if (target.value !== nextValue) target.value = nextValue;
    refreshProductionSaleCardControls(card);
    const feedback = root.querySelector(".sale-edit-guidance");
    if (feedback) feedback.textContent = state.voice.status || card.fields.voice_feedback || `${fieldLabel(anchor.field)} selected. Speak the new value.`;
    const busy = state.voice.starting || state.voice.listening;
    root.querySelectorAll('[data-action="sale-edit-field-voice"]').forEach((button) => { button.disabled = busy; });
    const composerVoice = root.querySelector('[data-action="start-voice"]');
    if (composerVoice) {
      composerVoice.disabled = busy;
      composerVoice.classList.toggle("listening", busy);
      composerVoice.textContent = state.voice.starting ? "Wait" : state.voice.listening ? "Speak" : "Mic";
    }
    restoreVoiceViewportAnchor(root, anchor, window, { restoreFocus: false });
    return true;
  }
  if (card.type !== "CatalogWorkspaceCard" || !card.fields?.selected_id) return false;

  const draft = catalogEditDraft(card);
  const nextValue = String(draft[anchor.field] ?? "");
  if (target.value !== nextValue) target.value = nextValue;
  refreshCatalogEditReviewDom(card, draft);

  const busy = state.voice.starting || state.voice.listening;
  root.querySelectorAll('[data-action="catalog-edit-field-voice"], [data-action="catalog-edit-voice"]').forEach((button) => {
    button.disabled = busy;
    if (button.dataset.action === "catalog-edit-voice") button.textContent = busy ? "Listeningâ€¦" : "Mic";
  });
  const localStatus = root.querySelector(".catalog-edit-voice [role='status']");
  if (localStatus) {
    localStatus.textContent = state.voice.status
      || card.fields.voice_feedback
      || `${fieldLabel(anchor.field)} selected. Tap Mic and speak the new value.`;
  }

  const composerVoice = root.querySelector('[data-action="start-voice"]');
  if (composerVoice) {
    composerVoice.disabled = busy;
    composerVoice.classList.toggle("listening", busy);
    composerVoice.textContent = state.voice.starting ? "Wait" : state.voice.listening ? "Speak" : "Mic";
    composerVoice.setAttribute("aria-label", state.voice.starting ? "Starting microphone" : state.voice.listening ? "Speak now" : "Use voice");
  }

  restoreVoiceViewportAnchor(root, anchor, window, { restoreFocus: false });
  return true;
}

function startCatalogSearchVoice(cardId, placement = "top") {
  const card = state.cards.find((item) => item.id === cardId && item.type === "CatalogWorkspaceCard");
  if (!card) return;
  startVoiceCapture(
    (transcript) => {
      const result = applyCatalogSearchVoice(transcript);
      card.fields.search_voice_feedback = result.feedback;
      if (result.applied) card.fields.query = result.query;
      persistActiveCards();
      render();
      if (result.applied) {
        requestAnimationFrame(() => {
          const input = root.querySelector(`[data-catalog-search-placement="${placement}"][data-card-id="${cardId}"]`);
          input?.focus();
          input?.setSelectionRange?.(result.query.length, result.query.length);
        });
      }
    },
    (message) => {
      card.fields.search_voice_feedback = message;
      persistActiveCards();
    }
  );
}

function selectCatalogVoiceField(cardId, field) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "CatalogWorkspaceCard");
  if (!card || !CATALOG_EDIT_FIELDS.includes(field)) return;
  card.fields.voice_field = field;
  card.fields.voice_feedback = "";
  persistActiveCards();
}

function startCatalogEditVoice(cardId) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "CatalogWorkspaceCard");
  if (!card?.fields?.selected_id) return;
  if (card.fields.voice_field) {
    activeVoiceViewportAnchor = createVoiceViewportAnchor(root, {
      cardId,
      field: card.fields.voice_field
    });
  }
  startVoiceCapture(
    (transcript) => {
      const result = applyCatalogEditVoice(catalogEditDraft(card), transcript, card.fields.voice_field);
      card.fields.voice_feedback = result.feedback;
      if (result.applied) {
        card.fields.voice_field = result.field;
        card.fields.edit_draft = JSON.stringify(result.draft);
      }
      persistActiveCards();
      render();
    },
    (message) => {
      card.fields.voice_feedback = message;
      persistActiveCards();
    }
  );
}

function startSaleEditFieldVoice(cardId, field) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "SaleCard");
  if (!card || !PRODUCTION_SALE_EDITABLE_FIELDS.includes(field)) return;
  card.fields.voice_field = field;
  card.fields.voice_feedback = `${fieldLabel(field)} selected. Speak the new value.`;
  activeVoiceViewportAnchor = createVoiceViewportAnchor(root, {
    cardId,
    field,
    selector: `input[data-card-id="${CSS.escape(cardId)}"][data-field="${CSS.escape(field)}"], select[data-card-id="${CSS.escape(cardId)}"][data-field="${CSS.escape(field)}"]`
  });
  persistActiveCards();
  startVoiceCapture(
    (transcript) => {
      const mappedField = { medicine: "name", current_stock: "stock", quantity: "stock", pack_conversion: "stock" }[field] || field;
      let value = String(transcript || "").trim();
      if (["quantity", "pack_conversion", "selling_price", "current_stock", "cost_price"].includes(field)) {
        const normalized = applyCatalogEditVoice({ [mappedField]: card.fields[field] }, transcript, mappedField);
        if (!normalized.applied) {
          card.fields.voice_feedback = normalized.feedback;
          persistActiveCards();
          render();
          return;
        }
        value = normalized.value;
      } else if (field === "payment") {
        const payment = value.toLowerCase().replaceAll("-", "").replace(/\s+/g, "");
        value = payment === "mpesa" ? "mpesa" : payment;
      }
      updateCardField(card.id, field, value);
      card.fields.voice_feedback = `Heard “${transcript}”. ${fieldLabel(field)} updated. Review before confirming.`;
      persistActiveCards();
      render();
    },
    (message) => {
      card.fields.voice_feedback = message;
      persistActiveCards();
    }
  );
}

function cancelCatalogEdit(cardId) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "CatalogWorkspaceCard");
  if (!card) return;
  activeVoiceViewportAnchor = null;
  card.fields.selected_id = "";
  card.fields.edit_draft = "";
  card.fields.voice_field = "";
  card.fields.voice_feedback = "";
  persistActiveCards();
  render();
}

function approveCatalogEdit(cardId) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "CatalogWorkspaceCard");
  if (!card) return;
  activeVoiceViewportAnchor = null;
  const result = applyApprovedCatalogEdit(pharmacyBrain.catalog, card.fields.selected_id, catalogEditDraft(card));
  if (!result.valid || !result.changes?.length) return;
  pharmacyBrain.loadCatalog(result.catalog);
  state.catalog.items = pharmacyBrain.catalog;
  safeLocalStorage()?.setItem(CATALOG_KEY, JSON.stringify(state.catalog.items));
  void cloudGateway.saveCatalog(state.pharmacy.id, state.catalog.items);
  recordCatalogActivity({
    medicine: result.updated.name,
    changes: result.changes,
    source: card.fields.voice_feedback ? "voice" : "manual",
    timestamp: result.updated.updatedAt
  });
  card.fields.selected_id = "";
  card.fields.edit_draft = "";
  card.fields.voice_field = "";
  card.fields.voice_feedback = "";
  card.fields.item_count = String(pharmacyBrain.catalog.length);
  persistActiveCards();
  refreshNotifications();
  render();
}

function activityHistoryKey() {
  return `${ACTIVITY_HISTORY_KEY_PREFIX}:${state.pharmacy.id}`;
}

function readActivityHistory() {
  try {
    const history = JSON.parse(safeLocalStorage()?.getItem(activityHistoryKey()) || "[]");
    return Array.isArray(history)
      ? history.filter((item) => item?.pharmacyId === state.pharmacy.id && item?.outcome === "saved").slice(0, 100)
      : [];
  } catch {
    return [];
  }
}

function persistActivityHistory(history) {
  safeLocalStorage()?.setItem(activityHistoryKey(), JSON.stringify(history.slice(0, 100)));
}

function recordCatalogActivity({ medicine, changes, source, timestamp }) {
  const entry = createCatalogActivityEntry({
    pharmacyId: state.pharmacy.id,
    medicine,
    changes,
    source,
    timestamp
  });
  const history = appendActivity(readActivityHistory(), entry);
  persistActivityHistory(history);
  const card = ensureActivityHubCard();
  card.fields.history = history;
  card.fields.expanded = false;
  persistActiveCards();
}

function reconcileActivityHubCard() {
  const matching = state.cards.filter((card) =>
    card.type === "ActivityHubCard"
    && (!card.fields?.pharmacy_id || card.fields.pharmacy_id === state.pharmacy.id)
  );
  if (!matching.length && !readActivityHistory().length) return;
  const keeper = matching[0] || {
    id: `card-activity-hub-${state.pharmacy.id}`,
    type: "ActivityHubCard",
    title: "Activity",
    source: "Local approved operations",
    confidence: 1,
    status: "ready",
    aiRequired: false,
    fields: {}
  };
  keeper.id = `card-activity-hub-${state.pharmacy.id}`;
  keeper.fields = {
    ...keeper.fields,
    pharmacy_id: state.pharmacy.id,
    expanded: false,
    history: readActivityHistory()
  };
  state.cards = state.cards.filter((card) =>
    card.type !== "ActivityHubCard"
    || card === keeper
    || (card.fields?.pharmacy_id && card.fields.pharmacy_id !== state.pharmacy.id)
  );
  if (!state.cards.includes(keeper)) state.cards.unshift(keeper);
}

function ensureActivityHubCard() {
  reconcileActivityHubCard();
  let card = state.cards.find((item) =>
    item.type === "ActivityHubCard" && item.fields?.pharmacy_id === state.pharmacy.id
  );
  if (!card) {
    card = {
      id: `card-activity-hub-${state.pharmacy.id}`,
      type: "ActivityHubCard",
      title: "Activity",
      source: "Local approved operations",
      confidence: 1,
      status: "ready",
      aiRequired: false,
      fields: { pharmacy_id: state.pharmacy.id, expanded: false, history: readActivityHistory() },
      validation: "Local deterministic audit history. Notifications and sales remain separate."
    };
    state.cards.unshift(card);
  }
  return card;
}

function openActivityHub() {
  const card = ensureActivityHubCard();
  card.fields.history = readActivityHistory();
  card.fields.expanded = true;
  persistActiveCards();
  render();
  focusCard(card.id);
}

function collapseActivityHub() {
  const card = ensureActivityHubCard();
  card.fields.expanded = false;
  persistActiveCards();
  render();
  focusCard(card.id);
}

function activityHubCardTemplate(card) {
  const history = Array.isArray(card.fields?.history) ? card.fields.history : [];
  const latest = history[0];
  if (card.fields?.expanded === true) {
    const rows = history.length
      ? history.map((item) => `<li class="activity-history-item"><div><strong>${escapeHtml(item.medicine)}</strong><span>${escapeHtml(item.kenyaTime)} Africa/Nairobi</span></div><p>${escapeHtml(item.summary)}</p><small>${escapeHtml(item.eventType.replaceAll("_", " "))} · ${escapeHtml(item.source)} · ${escapeHtml(item.outcome)}</small></li>`).join("")
      : "<li>No saved activity yet.</li>";
    return `<article class="card-message ready activity-hub-card activity-hub-expanded" data-card-id="${card.id}">
      <div class="card-top"><span class="card-heading"><span class="card-type">Local audit</span><strong>Activity History</strong></span><button class="card-close-button" type="button" data-action="close-activity-history" aria-label="Collapse Activity History">x</button></div>
      <p>Approved Catalog changes are recorded here without adding permanent chat messages.</p>
      <ol class="activity-history">${rows}</ol>
      <p class="activity-hub-assurance">Local · Pharmacy-isolated · Refresh-safe · Zero AI · Notifications separate</p>
    </article>`;
  }
  return `<article class="card-message ready activity-hub-card activity-status-card" data-card-id="${card.id}" data-pharmacy-id="${escapeHtml(state.pharmacy.id)}">
    <div><span class="card-type">Latest Catalog activity</span><strong>${escapeHtml(latest?.summary || "No saved activity yet.")}</strong>${latest ? `<small>${escapeHtml(latest.kenyaTime)} Africa/Nairobi</small>` : ""}<p>${history.length} recent approved update${history.length === 1 ? "" : "s"}.</p></div>
    <button type="button" data-action="open-activity-history">View Activity History</button>
  </article>`;
}

function isLegacyCatalogUpdateFeed(item) {
  return item?.type === "system"
    && /^[^.\n]+ updated in the Pharmacy Catalog\.$/.test(String(item.text || ""));
}

function updateCatalogSearch(cardId, value, sourceInput) {
  const card = state.cards.find((item) => item.id === cardId && item.type === "CatalogWorkspaceCard");
  if (!card) return;
  card.fields.query = value;
  persistActiveCards();
  const list = root.querySelector(".catalog-workspace-list");
  const counts = root.querySelectorAll(".catalog-result-count");
  const items = catalogWorkspaceItems(pharmacyBrain.catalog, value);
  if (list) {
    list.innerHTML = items.length ? items.map(catalogWorkspaceItemTemplate).join("") : '<p class="catalog-empty">No medicines match this search.</p>';
  }
  root.querySelectorAll("[data-catalog-search]").forEach((input) => {
    if (input !== sourceInput) input.value = value;
  });
  counts.forEach((count) => { count.textContent = `Showing ${items.length} of ${pharmacyBrain.catalog.length}`; });
}

function saveCatalogFromReviewCard(card) {
  const fields = card.fields || {};
  if (!fields.medicine) return;
  saveCatalogItems([medicineRecordFromFields(fields, {
    source: card.type === "InvoiceCard" ? "invoice_review" : "scan_review"
  })]);
  pharmacyBrain.saveVisualMemory({
    cardId: card.id,
    medicine: fields.medicine,
    barcode: fields.barcode || "",
    batch: fields.batch || "",
    expiry: fields.expiry || "",
    savedAt: new Date().toISOString()
  });
}

function saveCatalogItems(items = []) {
  const saved = [];
  for (const item of items) {
    if (!item?.name) continue;
    saved.push(pharmacyBrain.upsertCatalogItem(item));
  }
  state.catalog.items = pharmacyBrain.catalog;
  safeLocalStorage()?.setItem(CATALOG_KEY, JSON.stringify(state.catalog.items));
  safeLocalStorage()?.setItem(SETUP_KEY, "true");
  state.onboarding.completed = true;
  void cloudGateway.saveCatalog(state.pharmacy.id, state.catalog.items);
  pruneCatalogOnboardingCards();
  refreshNotifications();
  return saved;
}

async function handleDocumentFile(file) {
  const name = file.name || "upload";
  const lower = name.toLowerCase();
  state.ui.screen = "chat";
  state.ui.workspace = "operations";
  if (file.type.startsWith("image/") || lower.endsWith(".pdf")) {
    void addPhotoCards(file, "invoice");
    return;
  }
  if (lower.endsWith(".xlsx")) {
    try {
      const text = await readXlsxInventory(file);
      const parsed = parseDelimitedInventory(text, sourceBrain);
      addCard(createFileImportReviewCard(parsed, name, "Excel", pharmacyBrain.catalog));
    } catch (error) {
      addFeed("system", `I could not read this Excel file. ${error?.message || "Save it as XLSX or CSV, then try again."} Nothing was saved.`);
    }
    return;
  }
  if (lower.endsWith(".xls")) {
    addFeed("system", "I could not read this older Excel file. Save it as XLSX or CSV, then try again. Nothing was saved.");
    return;
  }
  const text = await file.text();
  if (lower.endsWith(".csv") || lower.endsWith(".tsv") || text.includes(",")) {
    const parsed = parseDelimitedInventory(text, sourceBrain);
    addCard(createFileImportReviewCard(parsed, name, lower.endsWith(".tsv") ? "TSV" : "CSV", pharmacyBrain.catalog));
    return;
  }
  addCard(createPasteImportCard(text));
}

function createFileImportReviewCard(parsed, fileName, fileType, catalog = []) {
  const prepared = prepareCatalogImport(parsed.items, catalog);
  const itemCount = prepared.newItems.length;
  const unclearCount = parsed.unclear.length;
  const unclearNote = unclearCount
    ? ` ${unclearCount} row(s) could not be read and were not added.`
    : "";
  if (!prepared.hasNewItems) {
    const existingList = prepared.existingNames.join(", ") || "the medicines in this file";
    const feedback = `No new medicines found in ${fileType} file ${fileName}. Already in this pharmacy: ${existingList}. Nothing was saved.`;
    const card = createPasteImportCard("", {
      source: fileName,
      method: `${fileType.toLowerCase()} file`,
      reviewFeedback: feedback
    });
    card.fields.entry_mode = "no_changes";
    card.fields.existing_medicines_ignored = prepared.existingNames.join(", ");
    card.validation = feedback;
    card.status = "ready";
    return card;
  }
  const existingNote = prepared.existingNames.length
    ? ` ${prepared.existingNames.length} existing medicine(s) were not added again: ${prepared.existingNames.join(", ")}.`
    : "";
  return createPasteImportCard(catalogItemsToText(prepared.newItems), {
    source: fileName,
    method: `${fileType.toLowerCase()} file`,
    reviewFeedback: `Read ${itemCount} new medicine(s) from ${fileType} file ${fileName}.${existingNote}${unclearNote} Check every value. Nothing is saved until approval.`
  });
}

function addMissingMedicineCard() {
  addCard(createEditableCard({
    type: "MedicineMatchCard",
    title: "Add missing medicine",
    source: "Sale-time fallback",
    fields: {
      message: "Use this only for a medicine that is missing during a sale.",
      medicine: "",
      quantity: "1",
      payment: "cash",
      choice: "Add and record sale",
      alias: ""
    },
    confidence: 0.7,
    status: "needs_correction",
    validation: "Approved missing medicines save to this pharmacy before repeat sales."
  }));
}

function exportCatalogCsv() {
  downloadInventoryExport("csv");
}

function ensureExportHubCard() {
  const matching = state.cards.filter((card) => card.type === "ExportHubCard" && card.fields?.pharmacy_id === state.pharmacy.id);
  const card = matching[0] || {
    id: `card-export-hub-${state.pharmacy.id}`, type: "ExportHubCard", title: "Export Hub",
    source: "Canonical Pharmacy Catalog", confidence: 1, status: "ready", aiRequired: false,
    fields: { pharmacy_id: state.pharmacy.id, item_count: String(pharmacyBrain.catalog.length), expanded: false, history_open: false },
    validation: "Downloads are generated locally from this pharmacy's canonical records with zero AI formatting."
  };
  state.cards = state.cards.filter((item) => item.type !== "ExportHubCard" || item === card);
  if (!state.cards.includes(card)) state.cards.unshift(card);
  const history = readExportHistory();
  card.fields.history = history;
  card.fields.item_count = String(pharmacyBrain.catalog.length);
  card.fields.last_download = history[0]?.summary || "Ready to generate an export.";
  persistActiveCards();
  return card;
}

function openExportHub(openHistory = false) {
  const card = ensureExportHubCard();
  card.fields.expanded = true;
  card.fields.history_open = openHistory;
  persistActiveCards();
  render();
  focusCard(card.id);
}

function collapseExportHub() {
  const card = ensureExportHubCard();
  card.fields.expanded = false;
  card.fields.history_open = false;
  persistActiveCards();
  render();
  focusCard(card.id);
}

function exportHubCardTemplate(card) {
  if (card.fields?.expanded === true) {
    return `<article class="card-message ready export-hub-card export-hub-card-expanded" data-card-id="${card.id}">
      <div class="card-top"><span class="card-heading"><span class="card-type">Documents</span><strong>Export Hub</strong></span><button class="card-close-button" type="button" data-action="close-export-hub" aria-label="Collapse Export Hub">x</button></div>
      ${exportHubTemplate(card)}
    </article>`;
  }
  const latest = Array.isArray(card.fields?.history) ? card.fields.history[0] : null;
  const format = latest ? exportFormat(latest.format) : null;
  return `<article class="card-message ready export-hub-card export-hub-status-card" data-card-id="${card.id}" data-pharmacy-id="${escapeHtml(state.pharmacy.id)}">
    <div class="export-status-copy"><span class="card-type">Latest export</span><strong>${escapeHtml(latest?.summary || "Ready to generate an export.")}</strong>${latest ? `<small>${escapeHtml(latest.generatedKenya)}</small>` : ""}<p>${escapeHtml(latest ? format?.nextAction || latest.openGuidance : "Open Export Hub to choose a format.")}</p></div>
    <div class="export-status-actions"><button type="button" data-action="open-export-hub">Open Export Hub</button>${latest ? '<button type="button" data-action="open-export-hub" data-history="true">View Export History</button>' : ""}</div>
  </article>`;
}

function exportHubTemplate(card) {
  const formatButton = (format) => `<button type="button" data-action="download-inventory-export" data-format="${format.id}" data-card-id="${card.id}" aria-label="${escapeHtml(format.accessibilityLabel)}"><strong>${format.label}</strong><span>${format.cardHelp}</span><small>Open with ${escapeHtml(format.recommendedApplication)}.</small></button>`;
  const polishedFormats = EXPORT_FORMATS.filter((format) => format.group === "polished");
  const dataFormats = EXPORT_FORMATS.filter((format) => format.group === "data");
  const history = Array.isArray(card.fields?.history) ? card.fields.history : [];
  const historyRows = history.length ? history.map((item) => `<li class="export-history-item">
    <div><strong>${escapeHtml(item.format.toUpperCase())} · ${escapeHtml(item.status)}</strong><span>${escapeHtml(item.generatedKenya)} · ${escapeHtml(String(item.medicineCount))} medicines</span></div>
    <p>${escapeHtml(item.purpose)}</p>
    <small>${escapeHtml(item.filename)} · ${escapeHtml(item.openGuidance)}</small>
    <button type="button" data-action="download-inventory-export" data-format="${escapeHtml(item.format)}" data-card-id="${card.id}">${escapeHtml(exportFormat(item.format)?.regenerationWording || "Generate again")}</button>
  </li>`).join("") : "<li>No exports generated yet.</li>";
  return `<section class="export-hub" aria-label="Export Hub">
    <div class="export-hub-summary"><strong>${pharmacyBrain.catalog.length} medicines</strong><span>${escapeHtml(state.pharmacy.name)} · ${escapeHtml(state.pharmacy.branch || "Main")}</span></div>
    <p>Choose Excel for calculations and reconciliation, PDF for read-only sharing and phone viewing, Word for corrections and working notes, Presentation for owner or management decisions, Print for a physical register, and CSV for system-to-system data exchange.</p>
    <div class="export-format-section">
      <h3>Polished owner copies</h3>
      <div class="export-format-grid">${polishedFormats.map(formatButton).join("")}</div>
    </div>
    <div class="export-format-section export-data-section">
      <h3>Technical data transfer</h3>
      <p>CSV preserves the records for other systems, but it cannot carry colours, fonts, spacing or page design.</p>
      <div class="export-format-grid">${dataFormats.map(formatButton).join("")}</div>
    </div>
    <p class="export-hub-status" aria-live="polite">${escapeHtml(card.fields?.last_download || "None yet")}</p>
    <details class="export-history"${card.fields?.history_open ? " open" : ""}><summary>Export history (${history.length})</summary><p class="export-history-help">Files stay in your device Downloads. History keeps metadata only.</p><ol>${historyRows}</ol></details>
    <p class="export-hub-assurance">Generated locally · Pharmacy-isolated · Canonical data · Zero AI formatting</p>
  </section>`;
}

function downloadInventoryExport(format, cardId = "") {
  const model = buildCanonicalInventoryExport({ pharmacy: state.pharmacy, items: pharmacyBrain.catalog });
  const builders = { csv: buildInventoryCsv, xlsx: buildInventoryXlsx, pdf: buildInventoryPdf, docx: buildInventoryDocx, pptx: buildInventoryPptx };
  const metadata = exportFormat(format);
  const targetCardId = cardId || ensureExportHubCard().id;
  if (format === "print") {
    const bridgeId = globalThis.crypto?.randomUUID?.() || `finder-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    state.printPreview = { model, bridgeId, query: "", message: "", exportCardId: targetCardId };
    recordExportEvent(targetCardId, exportHistoryRecord({ model, format, status: "print_view_ready" }));
    return;
  }
  const builder = builders[format];
  if (!metadata || !builder) {
    return recordExportEvent(targetCardId, exportHistoryRecord({ model, format: format || "unknown", status: "unavailable" }));
  }
  const filename = exportFilename(model, metadata.extension);
  try {
    const contents = builder(model);
    if (format === "pptx") validateInventoryPptxPackage(contents);
    downloadBlobFile({ filename, contents, mime: metadata.mime });
    recordExportEvent(targetCardId, exportHistoryRecord({ model, format, status: "completed", filename }));
  } catch (error) {
    console.error(`MS2.0 ${format.toUpperCase()} export failed`, error);
    recordExportEvent(targetCardId, exportHistoryRecord({ model, format, status: "failed", filename }));
  }
}

function exportHistoryKey() {
  return `${EXPORT_HISTORY_KEY_PREFIX}:${state.pharmacy.id}`;
}

function readExportHistory() {
  try {
    const history = JSON.parse(safeLocalStorage()?.getItem(exportHistoryKey()) || "[]");
    return Array.isArray(history) ? history.slice(0, EXPORT_HISTORY_LIMIT).map((item) => ({
      ...item,
      summary: exportCompletionSummary(item.format, item.status, item.medicineCount)
    })) : [];
  } catch {
    return [];
  }
}

function exportHistoryRecord({ model, format, status, filename = "" }) {
  const definition = exportFormat(format);
  const recordStatus = status || "completed";
  return {
    id: `${state.pharmacy.id}:${format}:${model.generatedIso}`,
    version: "ms20.export-history.v1",
    format,
    filename,
    pharmacyId: state.pharmacy.id,
    pharmacyName: state.pharmacy.name,
    generatedIso: model.generatedIso,
    generatedKenya: `${model.generatedKenya} Africa/Nairobi`,
    medicineCount: model.rows.length,
    purpose: definition?.purpose || "Requested export workflow.",
    historyDescription: definition?.historyDescription || "Requested export workflow.",
    recommendedApplication: definition?.recommendedApplication || "Compatible application",
    openGuidance: definition?.nextAction || "Try generating this export again.",
    status: recordStatus,
    extension: definition?.extension || "",
    summary: exportCompletionSummary(format, recordStatus, model.rows.length)
  };
}

function recordExportEvent(cardId, record) {
  const previous = readExportHistory();
  const history = [record, ...previous.filter((item) => item.id !== record.id)].slice(0, EXPORT_HISTORY_LIMIT);
  safeLocalStorage()?.setItem(exportHistoryKey(), JSON.stringify(history));
  const card = state.cards.find((item) => item.id === cardId) || ensureExportHubCard();
  if (card) {
    card.fields.history = history;
    card.fields.last_download = record.summary;
    card.fields.expanded = false;
    card.fields.history_open = false;
    persistActiveCards();
  }
  render();
}

function downloadBulkPasteTemplate() {
  downloadTextFile({
    filename: "ms20-bulk-paste-template.txt",
    contents: buildBulkPasteTemplate()
  });
}

function readCardAloud(cardId) {
  const card = state.cards.find((item) => item.id === cardId) || activeNotificationCards().find((item) => item.id === cardId);
  if (!card || !window.speechSynthesis) return;
  if (card.type === "StockCorrectionCard") return startStockFixReading(card);
  if (card.type === "ReportCard") return readReportAloud(card);
  const fields = Object.entries(card.fields || {}).map(([key, value]) => `${key.replaceAll("_", " ")} ${value}`).join(". ");
  startCardReading(card.id, `${card.title}. ${fields}`);
}

function readReportAloud(card) {
  const report = String(card.fields?.report_text || "").trim();
  if (!report) {
    card.validation = "Generate the report before using Read.";
    persistActiveCards();
    render();
    return;
  }
  startCardReading(card.id, report
    .replaceAll("KES", "Kenyan shillings")
    .replaceAll("Ksh", "Kenyan shillings")
    .replaceAll("M-Pesa", "M Pesa"));
}

function startStockFixReading(card) {
  stopStockFixReading();
  const sequence = ++stockFixReadingSequence;
  stockFixReading = {
    sequence,
    cardId: card.id,
    index: 0,
    paused: false,
    segments: [
      `Medicine: ${card.fields?.medicine || "not set"}.`,
      `Current stock: ${card.fields?.current_stock === "" ? "not set" : card.fields?.current_stock}.`,
      `Correct stock: ${card.fields?.correct_stock === "" ? "not set" : card.fields?.correct_stock}. Reason: ${card.fields?.reason || "not provided"}. Complete review finished. When listening resumes, say Confirm again to apply this stock fix once.`
    ]
  };
  updateStockFixReadButton(card.id, "Pause");
  speakStockFixSegment(sequence);
}

function toggleStockFixReading(cardId) {
  if (stockFixReading?.cardId === cardId) {
    if (stockFixReading.paused) resumeStockFixReading();
    else pauseStockFixReading();
    return;
  }
  readCardAloud(cardId);
}

function updateStockFixReadButton(cardId, label) {
  const button = root.querySelector(`[data-stock-fix-read="${cardId}"]`);
  if (button) button.textContent = label;
}

function speakStockFixSegment(sequence) {
  const reading = stockFixReading;
  if (!reading || reading.sequence !== sequence || reading.paused || reading.index >= reading.segments.length) return;
  const utterance = new SpeechSynthesisUtterance(reading.segments[reading.index]);
  utterance.lang = "en-KE";
  utterance.onstart = () => {
    if (stockFixReading?.sequence === sequence) showMedicineSlide(reading.cardId, reading.index);
  };
  utterance.onend = () => {
    if (stockFixReading?.sequence !== sequence || stockFixReading.paused) return;
    stockFixReading.index += 1;
    if (stockFixReading.index < stockFixReading.segments.length) speakStockFixSegment(sequence);
    else {
      updateStockFixReadButton(reading.cardId, "Read");
      const reviewedCard = state.cards.find((card) => card.id === reading.cardId && card.ui?.voiceGuided);
      stockFixReading = null;
      if (reviewedCard?.ui?.voiceReviewStarted) {
        reviewedCard.ui = { ...reviewedCard.ui, voiceReviewCompleted: true };
        reviewedCard.validation = "Complete review finished. Say Confirm to apply this stock fix once.";
        persistActiveCards();
        render();
        focusCard(reviewedCard.id);
      }
      if (reviewedCard) setTimeout(() => startVoiceCapture(), 350);
    }
  };
  utterance.onerror = () => {
    if (stockFixReading?.sequence === sequence && !stockFixReading.paused) {
      const interruptedCard = state.cards.find((card) => card.id === reading.cardId && card.ui?.voiceReviewStarted);
      if (interruptedCard) {
        interruptedCard.ui = { ...interruptedCard.ui, voiceReviewStarted: false, voiceReviewCompleted: false };
        interruptedCard.validation = "The complete review did not finish. Say Confirm to start it again; nothing was applied.";
        persistActiveCards();
        render();
        focusCard(interruptedCard.id);
      }
      updateStockFixReadButton(reading.cardId, "Read");
      stockFixReading = null;
    }
  };
  speakUtterance(utterance);
}

function speakUtterance(utterance) {
  const synthesis = window.speechSynthesis;
  if (!synthesis) return;
  if (synthesis.speaking || synthesis.pending) {
    synthesis.cancel();
    window.setTimeout(() => synthesis.speak(utterance), 60);
    return;
  }
  synthesis.speak(utterance);
}

function startCardReading(cardId, text) {
  stopCardReading(speechControl.cardId);
  const segments = String(text || "").split(/\n+|(?<=[.!?])\s+/).map((part) => part.trim()).filter(Boolean);
  if (!segments.length) return;
  speechControl = { cardId, paused: false, segments, index: 0 };
  render();
  speakCurrentCardSegment();
}

function speakCurrentCardSegment() {
  const session = speechControl;
  if (!session.cardId || session.paused || session.index >= session.segments.length) {
    if (session.cardId && session.index >= session.segments.length) {
      speechControl = { cardId: "", paused: false, segments: [], index: 0 };
      render();
    }
    return;
  }
  const utterance = new SpeechSynthesisUtterance(session.segments[session.index]);
  const runId = ++speechRunId;
  utterance.lang = "en-KE";
  utterance.onend = () => {
    if (speechControl !== session || session.paused || runId !== speechRunId) return;
    session.index += 1;
    speakCurrentCardSegment();
  };
  utterance.onerror = () => {
    if (speechControl !== session || session.paused || runId !== speechRunId) return;
    speechControl = { cardId: "", paused: false, segments: [], index: 0 };
    render();
  };
  window.speechSynthesis.speak(utterance);
}

function pauseCardReading(cardId) {
  if (speechControl.cardId !== cardId) return;
  speechControl.paused = true;
  speechRunId += 1;
  window.speechSynthesis?.cancel();
  render();
}

function resumeCardReading(cardId) {
  if (speechControl.cardId !== cardId || !speechControl.paused) return;
  speechControl.paused = false;
  render();
  speakCurrentCardSegment();
}

function stopCardReading(cardId) {
  if (speechControl.cardId !== cardId) return;
  speechControl = { cardId: "", paused: false, segments: [], index: 0 };
  speechRunId += 1;
  window.speechSynthesis?.cancel();
  render();
}

function warmSpeechSynthesis() {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.getVoices();
}

function pauseStockFixReading() {
  if (!stockFixReading) return;
  stockFixReading.paused = true;
  updateStockFixReadButton(stockFixReading.cardId, "Resume");
  window.speechSynthesis?.cancel();
}

function resumeStockFixReading() {
  if (!stockFixReading?.paused) return;
  stockFixReading.paused = false;
  updateStockFixReadButton(stockFixReading.cardId, "Pause");
  speakStockFixSegment(stockFixReading.sequence);
}

function stopStockFixReading() {
  if (stockFixReading?.cardId) updateStockFixReadButton(stockFixReading.cardId, "Read");
  stockFixReading = null;
  stockFixReadingSequence += 1;
  window.speechSynthesis?.cancel();
}

function recordCard(card) {
  const backend = backendAdapters.prepareBackendAction(card, state.liveBackend);
  card.integration = backend;
  const saleCard = card.type === "SaleCard" || card.type === "MedicineMatchCard";
  const paymentMethod = String(card.fields?.payment || "cash").replace("-", "").toLowerCase();
  const requestVerify = transactionEngine.settings().completionMode === "request_verify" && paymentMethod !== "cash";
  const transactionResult = saleCard
    ? transactionEngine.start({
      id: `transaction-${card.id}`,
      kind: "sale",
      amount: saleTransactionAmount(card),
      paymentMethod,
      mode: requestVerify ? "request_verify" : "fast_record",
      adapter: requestVerify ? "simulator" : paymentMethod === "cash" ? "cash" : "manual",
      reference: card.id,
      metadata: {
        medicine: card.fields?.medicine || "",
        quantity: Number(card.fields?.quantity || 0),
        sellingPrice: Number(card.fields?.selling_price || 0),
        expectedTotal: Number(card.fields?.expected_total || 0),
        strength: card.fields?.strength || "",
        form: card.fields?.form || "",
        unit: card.fields?.unit || "",
        baseStockUnit: card.fields?.base_stock_unit || "",
        packConversion: Number(card.fields?.pack_conversion || 0),
        baseStockDeduction: Number(card.fields?.stock_deduction || card.fields?.quantity || 0),
        stockBefore: Number(card.fields?.stock_before),
        stockAfter: Number(card.fields?.stock_after),
        pharmacyId: state.pharmacy.id,
        branchId: state.pharmacy.branch,
        merchantAccountId: requestVerify ? "simulator-pharmacy-merchant" : "manual-record",
        paymentRequestId: `request-${card.id}`
      }
    })
    : null;
  if (transactionResult?.transaction?.status === "completed") {
    card.fields.sale_number = transactionResult.transaction.saleNumber;
    card.fields.transaction_id = transactionResult.transaction.permanentId;
    card.fields.transaction_amount = transactionResult.transaction.amount;
  }
  const action = {
    id: `action-${card.id}`,
    type: card.type,
    fields: card.fields,
    backend,
    transaction: transactionResult?.transaction || null,
    localFirst: true,
    aiUsed: false
  };
  const result = syncAdapter.queueAction(action);
  if (result.added && saleCard && transactionResult?.transaction?.status === "completed") {
    applyLocalSaleStock(card);
    updateTodayTotals(card);
  }
  if (result.added && card.type === "RestockCard") {
    applyLocalRestockStock(card);
  }
  const reply = result.duplicate ? "Already saved." : transactionResult?.transaction?.status === "pending"
    ? `Today's ${transactionResult.transaction.saleLabel} is waiting for simulated ${paymentLabel(paymentMethod)} confirmation. You can keep serving. Open Payment Queue to finish it.`
    : savedReplyFor(card);
  const completedSale = transactionResult?.transaction?.status === "completed" ? transactionResult.transaction : null;
  addFeed("system", reply, completedSale ? {
    saleReference: {
      saleNumber: completedSale.saleNumber,
      transactionId: completedSale.permanentId || completedSale.id
    }
  } : {});
}

function completeStockCorrection(card) {
  const backend = backendAdapters.prepareBackendAction(card, state.liveBackend);
  const action = {
    id: `action-${card.id}`,
    type: card.type,
    fields: { ...card.fields },
    backend,
    localFirst: true,
    aiUsed: false
  };
  const result = executeStockCorrection({
    action,
    catalog: pharmacyBrain.catalog,
    online: navigator.onLine !== false,
    queue,
    storage: safeLocalStorage(),
    persistCatalog: persistCorrectedCatalog,
    replaceCatalog: replaceCorrectedCatalog
  });
  removeCard(card.id);
  if (result.status === "completed") {
    void cloudGateway.saveAction(result.action);
    addFeed("system", result.duplicate ? "Stock was already updated." : `Stock updated.\n${card.fields.medicine}: ${card.fields.current_stock} → ${card.fields.correct_stock}.`);
  } else if (result.status === "pending") {
    addFeed("system", `No internet. Stock fix saved and will update automatically when connection returns.\n${card.fields.medicine}: ${card.fields.current_stock} → ${card.fields.correct_stock}.`);
  } else {
    addFeed("system", result.message || "Stock could not be updated. Please review and try again.");
  }
  refreshNotifications();
  render();
}

function persistCorrectedCatalog(items) {
  const storage = safeLocalStorage();
  if (!storage) return false;
  storage.setItem(CATALOG_KEY, JSON.stringify(items));
  return true;
}

function replaceCorrectedCatalog(items) {
  pharmacyBrain.loadCatalog(items);
  state.catalog.items = pharmacyBrain.catalog;
  void cloudGateway.saveCatalog(state.pharmacy.id, state.catalog.items);
}

function syncPendingStockCorrections() {
  if (navigator.onLine === false) return;
  const results = replayPendingStockCorrections({
    getCatalog: () => pharmacyBrain.catalog,
    online: true,
    queue,
    storage: safeLocalStorage(),
    persistCatalog: persistCorrectedCatalog,
    replaceCatalog: replaceCorrectedCatalog
  });
  for (const result of results.filter((item) => item.status === "completed" && !item.duplicate)) {
    void cloudGateway.saveAction(result.action);
    addFeed("system", `Stock updated.\n${result.action.fields.medicine}: ${result.action.fields.current_stock} → ${result.action.fields.correct_stock}.`);
  }
}

function resolveSimulatedPayment(transactionId, status) {
  return processTransactionProviderEvent(transactionId, {
    key: `owner-simulator-${transactionId}-${status}`,
    status,
    reason: status === "confirmed" ? "simulated_owner_confirmation" : "simulated_owner_failure",
    source: "simulator"
  });
}

function processTransactionProviderEvent(transactionId, event) {
  const result = transactionEngine.providerEvent(transactionId, event);
  if (result.updated && event.status === "confirmed") {
    applyConfirmedPendingSale(result.transaction);
    addFeed("system", `${result.transaction.saleLabel}\n✅ ${result.transaction.metadata?.medicine} x${result.transaction.metadata?.quantity} recorded · ${paymentLabel(result.transaction.paymentMethod)}\nStock left: ${result.transaction.metadata?.stockLeft ?? "—"}`, {
      saleReference: {
        saleNumber: result.transaction.saleNumber,
        transactionId: result.transaction.permanentId || result.transaction.id
      }
    });
    const remaining = transactionEngine.pending();
    if (remaining.length) addFeed("system", `${result.transaction.saleLabel} completed. ${remaining.length} payment${remaining.length === 1 ? " is" : "s are"} still waiting. You can keep serving.`);
  } else if (result.updated && ["failed", "cancelled"].includes(event.status)) {
    addTransactionNotification(result.transaction, event.status);
  }
  state.ui.screen = "payments";
  render();
  return result;
}

function addTransactionNotification(transaction, status) {
  const notification = buildTransactionNotification({ transaction, status });
  state.notifications = [notification, ...(state.notifications || []).filter((item) => item.id !== notification.id)];
  safeLocalStorage()?.setItem(NOTIFICATION_KEY, JSON.stringify(state.notifications));
}

function applyConfirmedPendingSale(transaction) {
  if (transaction.metadata?.stockApplied) return;
  const card = { type: "SaleCard", fields: {
    medicine: transaction.metadata?.medicine || "",
    quantity: Number(transaction.metadata?.quantity || 0),
    payment: transaction.paymentMethod,
    selling_price: Number(transaction.metadata?.sellingPrice || 0),
    expected_total: Number(transaction.metadata?.expectedTotal || transaction.amount || 0),
    strength: transaction.metadata?.strength || "",
    form: transaction.metadata?.form || "",
    unit: transaction.metadata?.unit || "",
    stock_before: transaction.metadata?.stockBefore ?? "",
    stock_after: transaction.metadata?.stockAfter ?? "",
    sale_number: transaction.saleNumber,
    transaction_id: transaction.permanentId
  }};
  applyLocalSaleStock(card);
  updateTodayTotals(card);
  transaction.metadata = { ...transaction.metadata, stockApplied: true, stockLeft: card.fields.stockLeft };
  const transactions = transactionEngine.list();
  const index = transactions.findIndex((item) => item.id === transaction.id);
  if (index >= 0) {
    transactions[index] = transaction;
    transactionEngine.save(transactions);
  }
}

function saleTransactionAmount(card) {
  const quantity = Number(card.fields?.quantity || 0);
  const enteredPrice = Number(card.fields?.selling_price);
  if (Number.isFinite(enteredPrice) && enteredPrice > 0) return quantity * enteredPrice;
  const match = pharmacyBrain.findMedicine(card.fields?.medicine);
  const savedPrice = Number(match.matches?.[0]?.sellingPrice ?? match.matches?.[0]?.selling_price);
  return Number.isFinite(savedPrice) && savedPrice > 0 ? quantity * savedPrice : 0;
}

function applyLocalSaleStock(card) {
  if (card.type === "MedicineMatchCard") return;
  const match = pharmacyBrain.findMedicine(card.fields?.medicine);
  if (match.status !== "matched") return;
  const medicine = match.matches[0];
  card.fields.medicine = medicine.name;
  if (medicine.stockLeft === null || medicine.stockLeft === undefined || medicine.stockLeft === "") {
    card.fields.stockLeft = null;
    return;
  }
  const currentStock = Number(medicine.stockLeft);
  const deduction = Number(card.fields?.stock_deduction || card.fields?.quantity || 0);
  if (!Number.isFinite(currentStock) || !Number.isFinite(deduction)) {
    card.fields.stockLeft = null;
    return;
  }
  const remaining = Math.max(0, currentStock - deduction);
  medicine.stockLeft = remaining;
  card.fields.stockLeft = remaining;
  state.catalog.items = pharmacyBrain.catalog;
  safeLocalStorage()?.setItem(CATALOG_KEY, JSON.stringify(state.catalog.items));
  void cloudGateway.saveCatalog(state.pharmacy.id, state.catalog.items);
}

function saveApprovedSalePackFacts(card) {
  const match = pharmacyBrain.findMedicine(card.fields?.medicine);
  if (match.status !== "matched") return;
  const medicine = match.matches[0];
  const unit = String(card.fields?.unit || "").trim();
  const baseUnit = String(card.fields?.base_stock_unit || "").trim();
  if (!unit || !baseUnit || unit === baseUnit) return;
  const conversion = Number(card.fields?.pack_conversion);
  const price = Number(card.fields?.selling_price);
  if (!Number.isFinite(conversion) || conversion <= 0 || !Number.isFinite(price) || price <= 0) return;
  medicine.baseStockUnit = baseUnit;
  medicine.units = [...new Set([...(medicine.units || []), baseUnit, unit])];
  medicine.unitConversions = { ...(medicine.unitConversions || {}), [baseUnit]: 1, [unit]: conversion };
  medicine.unitPrices = { ...(medicine.unitPrices || {}), [unit]: price };
  state.catalog.items = pharmacyBrain.catalog;
  safeLocalStorage()?.setItem(CATALOG_KEY, JSON.stringify(state.catalog.items));
  void cloudGateway.saveCatalog(state.pharmacy.id, state.catalog.items);
}

function applyLocalRestockStock(card) {
  const quantity = Number(card.fields?.quantity || 0);
  const bonusQuantity = Number(card.fields?.bonus_quantity || 0);
  if (!Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(bonusQuantity) || bonusQuantity < 0) return;
  const match = pharmacyBrain.findMedicine(card.fields?.medicine);
  if (match.status !== "matched") return;
  const medicine = pharmacyBrain.upsertCatalogItem(medicineRecordFromFields(card.fields, {
    source: "restock_review",
    quantityIsStock: false
  }));
  card.fields.medicine = medicine.name;
  const currentStock = medicine.stockLeft === null || medicine.stockLeft === undefined || medicine.stockLeft === ""
    ? 0
    : Number(medicine.stockLeft);
  if (!Number.isFinite(currentStock)) return;
  const stockLeft = currentStock + quantity + bonusQuantity;
  medicine.stockLeft = stockLeft;
  card.fields.stockLeft = stockLeft;
  state.catalog.items = pharmacyBrain.catalog;
  safeLocalStorage()?.setItem(CATALOG_KEY, JSON.stringify(state.catalog.items));
  void cloudGateway.saveCatalog(state.pharmacy.id, state.catalog.items);
}

function updateTodayTotals(card) {
  const amount = Number(card.fields.quantity || 0);
  state.today.sales += amount;
  if (card.fields.payment === "mpesa") state.today.mpesa += amount;
  else if (card.fields.payment === "credit") state.today.credit += amount;
  else state.today.cash += amount;
}

function correctCard(cardId) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card) return;
  card.status = "needs_correction";
  card.ui = { ...(card.ui || {}), editing: true, activeSlide: 0 };
  card.validation = "Edit the fields, then confirm.";
  persistActiveCards();
  render();
}

function rejectCard(cardId) {
  const card = state.cards.find((item) => item.id === cardId);
  removeCard(cardId);
  if (card?.type === "OnboardingCard") state.onboarding.started = false;
  refreshNotifications();
  render();
}

function dismissCard(cardId) {
  const notificationCard = activeNotificationCards().find((item) => item.id === cardId);
  if (notificationCard) {
    dismissNotification(notificationIdFromCard(notificationCard));
    return;
  }
  const card = state.cards.find((item) => item.id === cardId);
  removeCard(cardId);
  if (card?.type === "OnboardingCard") state.onboarding.started = false;
  refreshNotifications();
  render();
}

function adjustCardFontScale(delta) {
  const next = clampCardFontScale(state.cardFontScale + delta);
  if (next === state.cardFontScale) return;
  state.cardFontScale = next;
  safeLocalStorage()?.setItem(CARD_FONT_SCALE_KEY, String(next));
  render();
}

function removeCard(cardId) {
  stopCardReading(cardId);
  const index = state.cards.findIndex((item) => item.id === cardId);
  if (index >= 0) {
    state.cards.splice(index, 1);
    persistActiveCards();
  }
}

function removeCardsByType(types) {
  const before = state.cards.length;
  state.cards = state.cards.filter((card) => !types.includes(card.type));
  if (state.cards.length !== before) persistActiveCards();
}

function removeCardsByPredicate(predicate) {
  const before = state.cards.length;
  state.cards = state.cards.filter((card) => !predicate(card));
  if (state.cards.length !== before) persistActiveCards();
}

function setPayment(cardId, payment) {
  updateCardField(cardId, "payment", payment);
  render();
}

function bumpQuantity(cardId, amount) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card) return;
  const current = Number(card.fields.quantity || 0);
  card.fields.quantity = Math.max(0, current + amount);
  if (card.type === "SaleCard") prepareProductionSaleCard(card, pharmacyBrain.findMedicine(card.fields?.medicine));
  persistActiveCards();
  render();
}

async function syncNow() {
  syncPendingStockCorrections();
  const result = await syncAdapter.syncPending({ excludeTypes: ["StockCorrectionCard"] });
  state.sync.lastSync = result.lastSync || "Not synced";
  addFeed("system", `Synced ${result.synced.length} saved item(s).`);
  render();
}

async function refreshLiveStatus({ silent = false } = {}) {
  const snapshot = await backendAdapters.getLiveStatus();
  state.liveBackend = snapshot;
  if (!silent) {
    addFeed("system", "System check complete.");
  }
  render();
  return snapshot;
}

function refreshNotifications() {
  const generated = buildDeterministicNotifications({
    catalog: pharmacyBrain.catalog,
    pendingCards: state.cards,
    catalogRequired: state.onboarding.completed
  });
  state.notifications = mergeNotifications(state.notifications || [], generated);
  safeLocalStorage()?.setItem(NOTIFICATION_KEY, JSON.stringify(state.notifications));
}

function activeNotificationCards() {
  return (state.notifications || [])
    .filter((item) => item.status !== "dismissed" && item.status !== "complete")
    .map(notificationToCard);
}

function unreadNotifications() {
  return (state.notifications || []).filter((item) => item.status === "unread").length;
}

function latestNotificationPreview() {
  const latest = (state.notifications || []).find((item) => item.status !== "dismissed" && item.status !== "complete");
  return latest ? latest.title : "No urgent alerts.";
}

function onboardingStatusText() {
  if (!state.onboarding.completed) return "Setup needed";
  if (pharmacyBrain.catalog.length === 0) return "Catalog needed";
  return "Ready";
}

function markNotificationsRead() {
  state.notifications = (state.notifications || []).map((item) => ({ ...item, status: item.status === "unread" ? "read" : item.status }));
  safeLocalStorage()?.setItem(NOTIFICATION_KEY, JSON.stringify(state.notifications));
  render();
}

function dismissNotification(notificationId) {
  state.notifications = (state.notifications || []).map((item) => (
    item.id === notificationId ? { ...item, status: "complete", completedAt: new Date().toISOString() } : item
  ));
  safeLocalStorage()?.setItem(NOTIFICATION_KEY, JSON.stringify(state.notifications));
  render();
}

function notificationIdFromCard(card) {
  return String(card.id || "").replace(/^card-notification-/, "");
}

function openNotificationAction(cardId) {
  const notificationCard = activeNotificationCards().find((item) => item.id === cardId);
  const targetCardId = notificationCard?.notificationAction?.targetCardId;
  if (String(targetCardId || "").startsWith("payment:")) {
    state.ui.screen = "payments";
    render();
    return;
  }
  if (!targetCardId || !state.cards.some((item) => item.id === targetCardId)) return;
  state.ui.screen = "chat";
  state.ui.workspace = "operations";
  render();
  focusCard(targetCardId);
}

function friendlyCardLabel(card) {
  const labels = {
    SaleCard: "Sale",
    InvoiceCard: "Invoice",
    RestockCard: "Restock",
    OnboardingCard: "Setup",
    StockCorrectionCard: "Stock fix",
    ReportCard: "Report",
    PhotoReviewCard: "Photo",
    MedicineMatchCard: "Medicine check",
    VisualScanCard: "Scan",
    CatalogOnboardingCard: "Onboarding",
    CatalogImportCard: "Catalog",
    CatalogWorkspaceCard: "Catalog",
    ImportMappingCard: "Import",
    NotificationCard: "Notification",
    DocumentExportCard: "Document",
    SyncReviewCard: "Sync"
  };
  return labels[card.type] || "Review";
}

function ownerCardNote(card) {
  if (card.voiceSource && card.fields?.review_feedback) {
    return String(card.fields.review_feedback).trim();
  }
  if ((card.type === "VisualScanCard" || card.type === "PhotoReviewCard") && card.fields?.review_feedback) {
    return String(card.fields.review_feedback).trim();
  }
  if (card.type === "CatalogImportCard" && card.fields?.import_incomplete === "true") return "This scan is incomplete. Scan again before saving anything.";
  if (card.type === "CatalogImportCard") {
    const feedback = String(card.fields?.review_feedback || "").trim();
    if (feedback) return feedback;
    const retainedFeedback = String(card.validation || "").trim();
    if (/^\d+ new medicine\(s\) ready for review\./.test(retainedFeedback)) return retainedFeedback;
  }
  if (card.type === "CatalogImportCard" && card.fields?.entry_mode === "paste_input") {
    const retainedFeedback = String(card.validation || "").trim();
    if (/^(No new medicines found|Paste at least one medicine line)/.test(retainedFeedback)) return retainedFeedback;
  }
  if (card.type === "CatalogImportCard") return "Review the list, edit if needed, then approve.";
  if (card.type === "CatalogWorkspaceCard") return "This view uses the complete saved Pharmacy Catalog.";
  if (card.type === "ExportHubCard") return "Choose Excel for analysis, PDF for read-only sharing, Word for corrections, Presentation for decisions, Print for paper, or CSV for another system. No confirmation is required.";
  if (card.type === "StockCorrectionCard") {
    if (card.photoEvidence && !String(card.fields?.medicine || "").trim() && card.validation) return card.validation;
    if (card.ui?.voiceGuided && card.validation) return card.validation;
    return stockCorrectionGuidance(card.fields, pharmacyBrain.catalog).message;
  }
  const confirmationBlocker = medicineReviewBlocker(card);
  if (confirmationBlocker) return confirmationBlocker;
  if (card.status === "needs_correction") return "Edit anything that looks wrong, then confirm.";
  if (card.type === "SaleCard") return "Complete the sale details, then confirm.";
  if (card.type === "InvoiceCard") return "Check the invoice before saving.";
  if (card.type === "VisualScanCard" && card.fields?.scan_type === "barcode") return card.validation || "Check the barcode details before saving.";
  if (card.type === "PhotoReviewCard" || card.type === "VisualScanCard") return "Check the photo details before saving.";
  if (card.type === "CatalogOnboardingCard") return "Choose the easiest way to add medicines.";
  if (card.type === "ImportMappingCard") return "Map the columns once, then MS2.0 can reuse the pattern.";
  if (card.type === "NotificationCard") return "Generated locally from pharmacy records.";
  if (card.type === "DocumentExportCard") return "Download or print when ready.";
  if (card.type === "ReportCard") return card.validation || "Generate the report from saved pharmacy records.";
  if (card.type === "SyncReviewCard") return "Review saved work before syncing.";
  return "Check the details, then confirm.";
}

function savedReplyFor(card) {
  if (card.type === "SaleCard") {
    const medicine = card.fields?.medicine || "Sale";
    const quantity = card.fields?.quantity || "1";
    const payment = paymentLabel(String(card.fields?.payment || "cash").toLowerCase());
    const lines = [
      card.fields?.sale_number ? `Sale ${card.fields.sale_number}` : "",
      `✅ ${medicine} x${quantity} recorded • ${payment}`
    ].filter(Boolean);
    const stockLine = stockReplyLine(card);
    if (stockLine) lines.push(stockLine);
    return lines.join("\n");
  }
  if (card.type === "MedicineMatchCard") {
    const medicine = card.fields?.medicine || "Medicine";
    const quantity = card.fields?.quantity || "1";
    const payment = paymentLabel(String(card.fields?.payment || "cash").toLowerCase());
    return `${medicine} added.\nSale recorded.\n${medicine} x${quantity}\nPayment: ${payment}`;
  }
  if (card.type === "StockCorrectionCard") return `Stock updated.\n${card.fields?.medicine}: ${card.fields?.current_stock} → ${card.fields?.correct_stock}.`;
  if (card.type === "RestockCard") {
    const medicine = card.fields?.medicine || "Medicine";
    const quantity = card.fields?.quantity || "0";
    const bonusQuantity = Number(card.fields?.bonus_quantity || 0);
    const unit = card.fields?.unit || "item";
    const totalAdded = Number(quantity) + bonusQuantity;
    const lines = [`✅ ${medicine} +${totalAdded} ${unit}${totalAdded === 1 ? "" : "s"} added`];
    if (bonusQuantity > 0) lines.push(`${quantity} bought + ${bonusQuantity} bonus`);
    const stockLine = stockReplyLine(card);
    if (stockLine) lines.push(stockLine);
    return lines.join("\n");
  }
  if (card.type === "OnboardingCard") return "Setup saved.";
  if (card.type === "CatalogImportCard") return "Catalog saved.";
  if (card.type === "VisualScanCard" || card.type === "PhotoReviewCard") return "Medicine details saved.";
  if (card.type === "InvoiceCard") return "Invoice review saved.";
  if (card.type === "ReportCard") return "Report request saved.";
  return "Saved.";
}

function setupComplete() {
  return safeLocalStorage()?.getItem(SETUP_KEY) === "true";
}

function readCatalog() {
  try {
    return JSON.parse(safeLocalStorage()?.getItem(CATALOG_KEY) || "[]");
  } catch {
    return [];
  }
}

function readFeed() {
  try {
    const feed = JSON.parse(safeLocalStorage()?.getItem(FEED_KEY) || "[]");
    if (!Array.isArray(feed)) return [];
    return feed.filter(isDurableFeedItem).slice(-FEED_RESUME_LIMIT);
  } catch {
    return [];
  }
}

function persistFeed() {
  const feed = (state.feed || []).filter(isDurableFeedItem).slice(-FEED_RESUME_LIMIT);
  safeLocalStorage()?.setItem(FEED_KEY, JSON.stringify(feed));
}

function isDurableFeedItem(item) {
  return item
    && typeof item.id === "string"
    && ["system", "owner"].includes(item.type)
    && typeof item.text === "string"
    && typeof item.time === "string";
}

function readActiveCards() {
  try {
    const cards = JSON.parse(safeLocalStorage()?.getItem(ACTIVE_CARDS_KEY) || "[]");
    if (!Array.isArray(cards)) return [];
    return cards.filter(isDurableCard).slice(0, ACTIVE_CARD_RESUME_LIMIT).map(resumeDurableCard);
  } catch {
    return [];
  }
}

function resumeDurableCard(card) {
  const resumed = { ...card, submitting: false };
  if (resumed.type === "ReportCard") {
    resumed.fields = {
      ...resumed.fields,
      generated_at: resumed.fields?.generated_at || "Not refreshed yet"
    };
    if (String(resumed.validation || "").startsWith("Generating today")) {
      resumed.validation = "The previous refresh was interrupted. Your saved report is unchanged; tap Refresh report to try again.";
    }
  }
  return resumed;
}

function persistActiveCards() {
  const cards = (state.cards || []).filter(isDurableCard).slice(0, ACTIVE_CARD_RESUME_LIMIT);
  safeLocalStorage()?.setItem(ACTIVE_CARDS_KEY, JSON.stringify(cards));
}

function readInvoiceMemoryCards() {
  try {
    const cards = JSON.parse(safeLocalStorage()?.getItem(INVOICE_MEMORY_KEY) || "[]");
    return Array.isArray(cards) ? cards.filter(isDurableCard).slice(0, 8) : [];
  } catch {
    return [];
  }
}

function rememberInvoiceCard(card) {
  if (card?.type !== "CatalogImportCard" || card.fields?.import_mode !== "invoice_ocr") return;
  const cards = [card, ...readInvoiceMemoryCards().filter((item) => item.id !== card.id)].slice(0, 8);
  safeLocalStorage()?.setItem(INVOICE_MEMORY_KEY, JSON.stringify(cards));
}

function isDurableCard(card) {
  return card
    && DURABLE_CARD_TYPES.has(card.type)
    && typeof card.id === "string"
    && typeof card.title === "string"
    && card.fields
    && typeof card.fields === "object";
}

function readNotifications() {
  try {
    return JSON.parse(safeLocalStorage()?.getItem(NOTIFICATION_KEY) || "[]");
  } catch {
    return [];
  }
}

function looksLikeMedicineList(text) {
  const lines = String(text || "").split(/\r?\n/).filter((line) => line.trim());
  if (lines.length >= 2) return true;
  return /^list\s*:/i.test(String(text || ""));
}

function catalogRowsForCard(card) {
  const cached = readCachedCatalogRows(card);
  if (cached.length) return cached;
  const text = card.fields?.items_text || "";
  const parsed = String(text).includes("|")
    ? parseCatalogText(text)
    : parseBulkMedicineList(text, sourceBrain).items;
  const rows = parsed.map(normalizeCatalogRow).filter((row) => row.name);
  return rows.length ? rows : [emptyCatalogRow()];
}

function readCachedCatalogRows(card) {
  try {
    const rows = JSON.parse(card.fields?.catalog_rows || "[]");
    return Array.isArray(rows) ? rows.map(normalizeCatalogRow) : [];
  } catch {
    return [];
  }
}

function persistCatalogRows(card, rows) {
  const cleanRows = rows.map(normalizeCatalogRow);
  card.fields.catalog_rows = JSON.stringify(cleanRows);
  card.fields.items_text = catalogItemsToText(cleanRows.filter((row) => row.name));
}

function normalizeCatalogRow(row = {}) {
  return normalizeMedicineReviewRow(row);
}

function emptyCatalogRow() {
  return normalizeCatalogRow({});
}

function orderedMedicineFields(fields) {
  const available = new Set(fields);
  const ordered = MEDICINE_DETAIL_FIELD_ORDER.filter((field) => available.has(field));
  const rest = fields.filter((field) => !ordered.includes(field));
  return [...ordered, ...rest];
}

function fieldLabel(field) {
  return medicineFieldLabel(field) || FIELD_LABELS[field] || field.replaceAll("_", " ");
}

function inputModeForField(field) {
  if (["quantity", "bonus_quantity", "stock", "current_stock", "correct_stock", "stockLeft"].includes(field)) return "numeric";
  if (["selling_price", "cost_price", "line_total", "invoice_total", "total"].includes(field)) return "decimal";
  return "";
}

function readCardFontScale() {
  const stored = Number(safeLocalStorage()?.getItem(CARD_FONT_SCALE_KEY));
  if (!Number.isFinite(stored)) return 1;
  return clampCardFontScale(stored);
}

function clampCardFontScale(value) {
  const clamped = Math.min(CARD_FONT_SCALE_MAX, Math.max(CARD_FONT_SCALE_MIN, value));
  return Math.round(clamped * 100) / 100;
}

function safeLocalStorage() {
  try {
    return window.localStorage || null;
  } catch {
    return null;
  }
}

function stockReplyLine(card) {
  const rawStock = card.fields?.stockLeft;
  if (rawStock === null || rawStock === undefined || rawStock === "") return "Stock left: not set";
  const stockLeft = Number(rawStock);
  return Number.isFinite(stockLeft) ? `Stock left: ${stockLeft}` : "Stock left: not set";
}

function greetingText() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning.";
  if (hour < 17) return "Good afternoon.";
  return "Good evening.";
}

function paymentLabel(payment) {
  if (payment === "mpesa") return "M-Pesa";
  return payment.charAt(0).toUpperCase() + payment.slice(1);
}

function sellingPriceFromText(text) {
  const withoutPayment = String(text || "").replace(/\b(cash|mpesa|m-pesa|credit|mixed)\b/ig, "").trim();
  const numbers = withoutPayment.match(/\d+(?:\.\d+)?/g) || [];
  return numbers.length > 1 ? numbers.at(-1) : "";
}

function first(values = []) {
  return Array.isArray(values) ? values[0] || "" : "";
}

function scrollChatToBottom() {
  const chatBody = root.querySelector("#chatBody");
  if (chatBody) chatBody.scrollTop = chatBody.scrollHeight;
}

function shouldAutoProbeBackend() {
  if (typeof window === "undefined") return false;
  if (window.__MS20_AUTO_PROBE_BACKEND__ === true) return true;
  const { pathname, port } = window.location;
  return port === "5000" || pathname === "/main-app" || pathname.startsWith("/main-app/");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function hideReplitBadge() {
  const patterns = /made with replit|build for free|replit/i;
  document.querySelectorAll("iframe, a, button, div, span").forEach((element) => {
    if (element.id === "app" || element.classList.contains("chat-app")) return;
    const text = element.textContent || "";
    const ownText = Array.from(element.childNodes)
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent || "")
      .join(" ");
    const attrs = [
      element.getAttribute("aria-label"),
      element.getAttribute("title"),
      element.getAttribute("src"),
      element.getAttribute("href"),
      element.id,
      element.className
    ].join(" ");
    const directMatch = patterns.test(`${ownText} ${attrs}`);
    const shortTextMatch = text.trim().length <= 90 && patterns.test(text);
    const outsideAppMatch = !element.closest("#app") && patterns.test(`${text} ${attrs}`);
    if (directMatch || shortTextMatch || outsideAppMatch) {
      element.style.setProperty("display", "none", "important");
    }
  });
}

function postFinderResult(query, source, message = "") {
  const target = activeFinderWindow;
  activeFinderWindow = null;
  if (!target || target.closed) return;
  target.postMessage({ type: "ms20:finder-result", query: String(query || "").trim(), source, message }, window.location.origin);
}

function handleFinderRequest(data, reply) {
  const send = (query = "", source = "", message = "") => reply({
    type: "ms20:finder-result", query: String(query || "").trim(), source, message
  });
  if (data.action === "close") {
    stopActiveVoiceCapture();
    closeCameraStream();
    state.printPreview = null;
    render();
    return;
  }
  if (data.action === "voice") {
    send("", "shared_voice_capture", "Starting microphone in MS2.0…");
    window.focus();
    startVoiceCapture(
      (transcript) => {
        const localMatch = matchMedicine(transcript, pharmacyBrain.catalog);
        const matched = localMatch.status === "matched" ? localMatch.matches[0] : null;
        send(
          matched?.name || transcript,
          "shared_voice_capture",
          matched
            ? `Matched ${matched.name} in this Pharmacy Catalog.`
            : `Heard “${transcript}”, but no single local medicine matched. Tap Speak medicine to retry.`
        );
      },
      (message) => send("", "shared_voice_capture", message)
    );
    return;
  }
  if (data.action === "barcode") {
    send("", "shared_barcode_capture", "Opening the shared scanner in MS2.0…");
    window.focus();
    activeFinderWindow = { closed: false, postMessage: (payload) => reply({ ...payload, bridgeId: data.bridgeId || "" }) };
    void openLightweightCamera("barcode").then((opened) => {
      if (!opened) send(
        "", "barcode_camera_unavailable",
        "Camera could not open. Allow camera access in browser settings, then try again."
      );
    });
  }
}

window.__ms20FinderRequest = (data) => {
  if (!state.printPreview || data?.bridgeId !== state.printPreview.bridgeId) return;
  handleFinderRequest(data, (payload) => {
    if (!state.printPreview) return;
    if (payload.query) state.printPreview.query = payload.query;
    if (payload.message !== undefined) state.printPreview.message = payload.message;
    if (!state.camera.open) render();
  });
};

window.__ms20PrintStatus = (data) => {
  if (!state.printPreview || data?.bridgeId !== state.printPreview.bridgeId) return;
  if (data.status !== "print_dialog_opened" && data.status !== "print_preparation_failed") return;
  recordExportEvent(
    state.printPreview.exportCardId,
    exportHistoryRecord({ model: state.printPreview.model, format: "print", status: data.status })
  );
};

window.addEventListener("online", () => { syncPendingStockCorrections(); render(); });
window.addEventListener("offline", render);

void sourceBrain.lookupMedicine("demo");
void aiFallback.enabled;

syncPendingStockCorrections();
warmSpeechSynthesis();
window.speechSynthesis?.addEventListener?.("voiceschanged", warmSpeechSynthesis, { once: true });
render();
window.setInterval(hideReplitBadge, 1500);
if (shouldAutoProbeBackend()) {
  void refreshLiveStatus({ silent: true });
}
