import { demoState, nowLabel } from "./data/demoState.js";
import { CloudMemoryGateway } from "./services/cloudGateway.js";
import { OfflineQueue } from "./services/offlineQueue.js";
import { SyncAdapter } from "./services/syncAdapter.js";
import { BackendAdapterRegistry } from "./services/backendAdapters.js";
import { PharmacyBrain, SourceBrain, AIFallbackAdapter } from "./services/brainAdapters.js";
import { runVisualPipeline, buildPhotoReviewCard } from "./services/visualPipeline.js";
import {
  createCatalogChoiceCard,
  createPasteImportCard,
  parseBulkMedicineList,
  parseCatalogText,
  parseDelimitedInventory,
  catalogItemsToText,
  buildImportSummary,
  buildCatalogSavedSummary
} from "./services/catalogOnboarding.js";
import { buildDeterministicNotifications, mergeNotifications, notificationToCard } from "./services/notificationCenter.js";
import { buildCatalogCsv, buildBulkPasteTemplate, buildDocumentCard, downloadTextFile } from "./services/documentGenerator.js";
import { cardFieldsFor, createEditableCard, paymentOptions, quantityBumps } from "./cards/editableCards.js";
import { resolveStockCheck } from "./services/localIntelligence.js";
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
const pharmacyBrain = new PharmacyBrain({ pharmacyId: state.pharmacy.id });
const sourceBrain = new SourceBrain();
const aiFallback = new AIFallbackAdapter();
const SETUP_KEY = "ms20-main-app:onboarding-complete";
const CARD_FONT_SCALE_KEY = "ms20-main-app:card-font-scale";
const CATALOG_KEY = "ms20-main-app:pharmacy-catalog";
const NOTIFICATION_KEY = "ms20-main-app:notifications";
const FEED_KEY = "ms20-main-app:conversation-feed";
const ACTIVE_CARDS_KEY = "ms20-main-app:active-cards";
const FEED_RESUME_LIMIT = 40;
const ACTIVE_CARD_RESUME_LIMIT = 12;
const CARD_FONT_SCALE_MIN = 0.85;
const CARD_FONT_SCALE_MAX = 1.25;
const CARD_FONT_SCALE_STEP = 0.1;
const CATALOG_TABLE_COLUMNS = [
  { key: "name", label: "Medicine", min: 180 },
  { key: "form", label: "Form", min: 110 },
  { key: "unit", label: "Unit", min: 110 },
  { key: "stock", label: "Quantity", min: 100, inputMode: "numeric" },
  { key: "cost_price", label: "Buying price", min: 120, inputMode: "decimal" },
  { key: "selling_price", label: "Selling price", min: 120, inputMode: "decimal" },
  { key: "supplier", label: "Supplier", min: 130 },
  { key: "batch", label: "Batch", min: 110 },
  { key: "expiry", label: "Expiry", min: 120 }
];
const INVOICE_TABLE_COLUMNS = [
  ...CATALOG_TABLE_COLUMNS.filter((column) => !["selling_price", "supplier", "barcode"].includes(column.key)),
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
const DURABLE_CARD_TYPES = new Set([
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
  "DocumentExportCard",
  "SyncReviewCard"
]);
const MEDICINE_DETAIL_FIELD_ORDER = [
  "medicine",
  "form",
  "unit",
  "pack_size",
  "quantity",
  "stock",
  "current_stock",
  "correct_stock",
  "cost_price",
  "selling_price",
  "supplier",
  "barcode",
  "batch",
  "expiry",
  "shelf",
  "category",
  "reason",
  "alias",
  "file",
  "scan_type",
  "total",
  "payment"
];
const FIELD_LABELS = {
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
  transcript: "Transcript",
  backend_route: "Backend route"
};
let activeRecognition = null;

state.ui = { screen: "home", workspace: "operations" };
state.voice = { listening: false, status: "" };
state.camera = { open: false, scanType: "medicine_photo", stream: null, status: "", lightAvailable: false, lightOn: false };
state.pendingScanType = "medicine_photo";
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

function render() {
  state.sync.online = navigator.onLine;
  state.sync.pending = queue.pendingCount();
  root.innerHTML = `
    <main class="chat-app" style="--card-font-scale: ${state.cardFontScale};">
      ${state.ui.screen === "chat" ? chatScreenTemplate() : chatHomeTemplate()}
      ${cameraOverlayTemplate()}
    </main>
  `;
  bindEvents();
  hideReplitBadge();
  scrollChatToBottom();
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
    </section>
  `;
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
        ${adminMenuTemplate()}
      </header>
      <section class="chat-body" id="chatBody" aria-label="Messages">
        <div class="message-list">
          ${chatMessageTemplates()}
          ${isNotifications ? "" : state.cards.map(cardTemplate).join("")}
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
    return [intro].map(feedItemTemplate).join("") + cards.map(cardTemplate).join("");
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
  return `
    <article class="message-bubble ${item.type}" aria-label="MS2.0 message">
      <p>${escapeHtml(item.text)}</p>
      <span>MS2.0 / ${escapeHtml(item.time)}</span>
    </article>
  `;
}

function composerTemplate() {
  return `
    <footer class="chat-composer" aria-label="Message composer">
      <details class="attach-menu">
        <summary aria-label="Open quick actions">+</summary>
        <div class="attach-sheet">
          <button type="button" data-action="take-photo">Camera</button>
          <button type="button" data-action="upload-photo">Photo library</button>
          <button type="button" data-action="upload-document">File</button>
          <button type="button" data-action="capture-invoice">Invoice</button>
          <button type="button" data-action="demo-barcode">Scan barcode</button>
          <button type="button" data-action="start-catalog-paste">Paste list</button>
          <button type="button" data-action="demo-stock-correction">Stock fix</button>
          <button type="button" data-action="demo-report">Report</button>
          <button type="button" data-action="export-catalog-csv">Export CSV</button>
          <button type="button" data-action="demo-onboarding">Setup</button>
        </div>
      </details>
      <form class="message-form" id="commandForm">
        <input id="commandInput" type="text" autocomplete="off" inputmode="text" placeholder="Message MS2.0">
        <button class="icon-button ${state.voice.listening ? "listening" : ""}" type="button" data-action="start-voice" aria-label="Use voice">
          ${state.voice.listening ? "Stop" : "Mic"}
        </button>
        <button class="send-button" type="submit">Send</button>
      </form>
      ${state.voice.status ? `<p class="composer-hint">${escapeHtml(state.voice.status)}</p>` : ""}
      <input id="photoInput" class="hidden-input" type="file" accept="image/*">
      <input id="cameraInput" class="hidden-input" type="file" accept="image/*" capture="environment">
      <input id="documentInput" class="hidden-input" type="file" accept=".csv,.txt,.tsv,.xls,.xlsx,.pdf,image/*,text/csv,text/plain">
    </footer>
  `;
}

function cameraOverlayTemplate() {
  if (!state.camera.open) return "";
  return `
    <section class="camera-overlay" aria-label="MS2.0 camera">
      <div class="camera-panel">
        <h2>${state.camera.scanType === "invoice" ? "Photograph invoice" : "Photograph medicine"}</h2>
        <p>Keep the whole item clear inside the frame.</p>
        <video id="ms20CameraPreview" autoplay muted playsinline></video>
        <p class="camera-status" aria-live="polite">${escapeHtml(state.camera.status)}</p>
        <div class="camera-actions">
          <button type="button" data-action="close-camera">Cancel</button>
          ${state.camera.lightAvailable ? `<button type="button" data-action="toggle-camera-light">${state.camera.lightOn ? "Light off" : "Light on"}</button>` : ""}
          <button class="primary-action" type="button" data-action="capture-camera-frame">Capture</button>
        </div>
      </div>
    </section>
  `;
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
  const fields = cardFieldsFor(card.type);
  const displayed = fields.length ? fields : Object.keys(card.fields || {});
  return `
    <article class="card-message ${card.status}" data-card-id="${card.id}">
      <div class="card-top">
        <span class="card-heading">
          <span class="card-type">${escapeHtml(friendlyCardLabel(card))}</span>
          <strong>${escapeHtml(card.title)}</strong>
        </span>
        <span class="card-top-actions">
          ${cardFontControlsTemplate()}
          <button class="card-close-button" type="button" data-action="dismiss-card" data-card-id="${card.id}" aria-label="Close ${escapeHtml(friendlyCardLabel(card))} card">x</button>
        </span>
      </div>
      ${cardBodyTemplate(card, displayed)}
      ${(card.type === "SaleCard" || card.type === "VoiceReviewCard") ? paymentToolbar(card) : ""}
      ${(card.type === "SaleCard" || card.type === "RestockCard") ? quantityToolbar(card) : ""}
      <p class="card-note">${escapeHtml(ownerCardNote(card))}</p>
      ${activeActionsTemplate(card)}
      <details class="card-technical">
        <summary>Details</summary>
        ${card.source ? `<p>From: ${escapeHtml(card.source)}</p>` : ""}
        <p>Type: ${escapeHtml(card.type)}. Confidence: ${Math.round((card.confidence || 0) * 100)}%.</p>
        ${card.parser ? `<p>Parser: ${escapeHtml(card.parser)}</p>` : ""}
        ${card.integration ? `<p>${escapeHtml(card.integration.summary)}</p>` : ""}
        ${card.validation ? `<p>${escapeHtml(card.validation)}</p>` : ""}
      </details>
    </article>
  `;
}

function cardBodyTemplate(card, displayed) {
  if (card.type === "CatalogOnboardingCard") {
    return `
      <div class="catalog-onboarding-prompt">
        <p>${escapeHtml(card.fields?.question || "How would you like to show me your pharmacy?")}</p>
        <span>Choose one option below. MS2.0 will prepare a review card before saving anything.</span>
      </div>
    `;
  }
  if (card.type === "CatalogImportCard") {
    return catalogImportTableTemplate(card);
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

function fieldTemplate(card, field) {
  const value = card.fields?.[field] ?? "";
  const longFields = new Set(["items_text", "choices", "notes", "mapping", "message", "action", "missing_columns"]);
  const inputMode = inputModeForField(field);
  const control = longFields.has(field)
    ? `<textarea data-card-id="${card.id}" data-field="${field}" rows="${field === "items_text" ? 8 : 3}">${escapeHtml(String(value))}</textarea>`
    : `<input data-card-id="${card.id}" data-field="${field}" ${inputMode ? `inputmode="${inputMode}"` : ""} value="${escapeHtml(String(value))}">`;
  return `
    <label>
      <span>${escapeHtml(fieldLabel(field))}</span>
      ${control}
    </label>
  `;
}

function medicineDetailTemplate(card, displayed) {
  const ordered = orderedMedicineFields(displayed);
  return `
    <div class="medicine-detail-grid">
      ${ordered.map((field) => fieldTemplate(card, field)).join("")}
    </div>
  `;
}

function catalogImportTableTemplate(card) {
  const rows = catalogRowsForCard(card);
  const invoiceMode = card.fields?.import_mode === "invoice_ocr";
  const columns = invoiceMode ? INVOICE_TABLE_COLUMNS : CATALOG_TABLE_COLUMNS;
  const columnTemplate = columns
    .map((column) => `${column.min}px`)
    .join(" ");
  return `
    <div class="catalog-import-editor">
      ${invoiceMode ? invoiceSummaryTemplate(card) : ""}
      <div class="catalog-table-wrap" style="--catalog-columns: ${columnTemplate};">
        <table class="catalog-import-table" aria-label="Medicine catalog review">
          <thead>
            <tr>
              ${columns.map((column) => `<th scope="col">${escapeHtml(column.label)}</th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${rows.map((row, index) => catalogImportRowTemplate(card.id, row, index, columns)).join("")}
          </tbody>
        </table>
      </div>
      <div class="catalog-mobile-rows" aria-label="Medicine catalog mobile review">
        ${rows.map((row, index) => catalogImportMobileRowTemplate(card.id, row, index, columns)).join("")}
      </div>
      ${invoiceMode && card.fields?.import_incomplete === "true" ? "" : `<button class="secondary-action" type="button" data-action="add-catalog-row" data-card-id="${card.id}">Add medicine row</button>`}
      <p>${invoiceMode && card.fields?.import_incomplete === "true"
        ? "Some details are missing. Scan again before approving."
        : "Edit each medicine, then approve. Empty medicine names are ignored."}</p>
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

function catalogImportRowTemplate(cardId, row, index, columns = CATALOG_TABLE_COLUMNS) {
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
    </tr>
  `;
}

function catalogImportMobileRowTemplate(cardId, row, index, columns = CATALOG_TABLE_COLUMNS) {
  const title = row.name || `Medicine ${index + 1}`;
  return `
    <section class="catalog-mobile-row" aria-label="${escapeHtml(title)}">
      <div class="catalog-mobile-row-title">
        <strong>${escapeHtml(title)}</strong>
        <span>Row ${index + 1}</span>
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
    const invoiceMode = card.fields?.import_mode === "invoice_ocr";
    const incompleteInvoice = invoiceMode && card.fields?.import_incomplete === "true";
    return `
      <div class="card-actions">
        ${incompleteInvoice
          ? '<button data-action="capture-invoice">Scan again</button>'
          : `<button data-action="confirm-card" data-card-id="${card.id}">${invoiceMode ? "Approve medicines" : "Approve catalog"}</button>`}
        ${invoiceMode ? "" : '<button data-action="download-template">Template</button>'}
        <button data-action="read-card" data-card-id="${card.id}">Read</button>
        ${incompleteInvoice ? "" : `<button data-action="correct-card" data-card-id="${card.id}">Correct</button>`}
        <button data-action="reject-card" data-card-id="${card.id}">Cancel</button>
      </div>
    `;
  }
  if (card.type === "NotificationCard") {
    return `
      <div class="card-actions">
        <button data-action="dismiss-notification" data-notification-id="${notificationIdFromCard(card)}">Done</button>
        <button data-action="read-card" data-card-id="${card.id}">Read</button>
      </div>
    `;
  }
  if (card.type === "ReportCard" || card.type === "DocumentExportCard") {
    return `
      <div class="card-actions">
        <button data-action="confirm-card" data-card-id="${card.id}">Confirm</button>
        <button data-action="read-card" data-card-id="${card.id}">Read</button>
        <button data-action="export-catalog-csv">Download CSV</button>
        <button data-action="correct-card" data-card-id="${card.id}">Correct</button>
        <button data-action="reject-card" data-card-id="${card.id}">Cancel</button>
      </div>
    `;
  }
  return `
    <div class="card-actions">
      <button data-action="confirm-card" data-card-id="${card.id}">Confirm</button>
      <button data-action="correct-card" data-card-id="${card.id}">Correct</button>
      <button data-action="reject-card" data-card-id="${card.id}">Cancel</button>
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

  root.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => handleAction(button.dataset));
  });

  root.querySelectorAll("[data-field]").forEach((input) => {
    input.addEventListener("input", () => updateCardField(input.dataset.cardId, input.dataset.field, input.value));
  });

  root.querySelectorAll("[data-catalog-field]").forEach((input) => {
    input.addEventListener("input", () => updateCatalogImportCell(input.dataset.cardId, input.dataset.catalogRow, input.dataset.catalogField, input.value));
  });

  root.querySelector("#photoInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    addPhotoCards(file?.name || "camera-photo.jpg", state.pendingScanType || "medicine_photo");
    state.pendingScanType = "medicine_photo";
  });

  root.querySelector("#cameraInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file && state.pendingScanType === "invoice") {
      void readInvoicePhoto(file);
    } else {
      addPhotoCards(file?.name || "camera-photo.jpg", state.pendingScanType || "medicine_photo");
    }
    state.pendingScanType = "medicine_photo";
  });

  root.querySelector("#documentInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file) void handleDocumentFile(file);
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
  if (action === "open-chat") {
    state.ui.screen = "chat";
    state.ui.workspace = dataset.workspace || "operations";
    if (state.ui.workspace === "operations") ensureOnboardingStarted();
    render();
    return;
  }
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
  if (action === "upload-document") root.querySelector("#documentInput")?.click();
  if (action === "demo-barcode") addBarcodeCard();
  if (action === "capture-invoice") {
    void openLightweightCamera("invoice");
  }
  if (action === "close-camera") closeLightweightCamera();
  if (action === "toggle-camera-light") void toggleCameraLight();
  if (action === "capture-camera-frame") void captureLightweightCameraFrame();
  if (action === "demo-onboarding") addOnboardingCard();
  if (action === "start-catalog-invoice") {
    removeCardsByType(["CatalogOnboardingCard"]);
    state.pendingScanType = "invoice";
    root.querySelector("#cameraInput")?.click();
  }
  if (action === "start-catalog-scan") {
    removeCardsByType(["CatalogOnboardingCard"]);
    state.pendingScanType = "medicine_photo";
    root.querySelector("#cameraInput")?.click();
  }
  if (action === "start-catalog-paste") {
    removeCardsByType(["CatalogOnboardingCard"]);
    addCard(createPasteImportCard());
  }
  if (action === "add-catalog-row") addCatalogImportRow(dataset.cardId);
  if (action === "start-catalog-file") {
    removeCardsByType(["CatalogOnboardingCard"]);
    root.querySelector("#documentInput")?.click();
  }
  if (action === "start-sale-learning") {
    removeCardsByType(["CatalogOnboardingCard"]);
    addMissingMedicineCard();
  }
  if (action === "export-catalog-csv") exportCatalogCsv();
  if (action === "download-template") downloadBulkPasteTemplate();
  if (action === "read-card") readCardAloud(dataset.cardId);
  if (action === "mark-notifications-read") markNotificationsRead();
  if (action === "dismiss-notification") dismissNotification(dataset.notificationId);
  if (action === "demo-report") addReportCard();
  if (action === "demo-sync") addSyncCard();
  if (action === "demo-stock-correction") addStockCorrectionCard();
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
  if (pharmacyBrain.catalog.length === 0) {
    addFeed("owner", text);
    ensureCatalogOnboardingStarted();
    render();
    return;
  }
  const card = buildCommandCard(text);
  addFeed("owner", text);
  prepareUnknownMedicineFallback(card, text);
  if (canRecordInstantly(card, text)) {
    recordCard(card);
    render();
  } else {
    if (card.type !== "MedicineMatchCard") {
      card.type = "VoiceReviewCard";
      card.title = "Check voice result";
      card.fields = {
        transcript: text,
        medicine: card.fields?.medicine || "",
        quantity: card.fields?.quantity || "",
        payment: card.fields?.payment || ""
      };
    }
    addCard(card);
  }
}

function startVoiceCapture() {
  if (state.voice.listening && activeRecognition) {
    activeRecognition.stop();
    activeRecognition = null;
    state.voice.listening = false;
    state.voice.status = "";
    render();
    return;
  }
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    state.voice.status = "Voice is not available in this browser. Please type for now.";
    render();
    return;
  }
  const recognition = new SpeechRecognition();
  recognition.lang = "en-KE";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  activeRecognition = recognition;
  state.voice.listening = true;
  state.voice.status = "Listening...";
  render();
  recognition.onresult = (event) => {
    const transcript = event.results?.[0]?.[0]?.transcript || "";
    state.voice.listening = false;
    state.voice.status = "";
    activeRecognition = null;
    if (transcript.trim()) {
      handleVoiceTranscript(transcript);
    } else {
      render();
    }
  };
  recognition.onerror = () => {
    state.voice.listening = false;
    state.voice.status = "Voice did not start. Check microphone permission.";
    activeRecognition = null;
    render();
  };
  recognition.onend = () => {
    if (state.voice.listening) {
      state.voice.listening = false;
      state.voice.status = "";
      activeRecognition = null;
      render();
    }
  };
  try {
    recognition.start();
  } catch {
    activeRecognition = null;
    state.voice.listening = false;
    state.voice.status = "Voice did not start. Check microphone permission.";
    render();
  }
}

function buildCommandCard(text) {
  const card = backendAdapters.adapters.commandParserAdapter.toCard(text, pharmacyBrain.catalog);
  card.integration = backendAdapters.prepareBackendAction(card, state.liveBackend);
  card.validation = `${card.validation || ""} ${card.integration.summary}`.trim();
  return card;
}

function canRecordInstantly(card, sourceText) {
  if (card.type !== "SaleCard") return false;
  if (!commandHasExplicitPayment(sourceText)) return false;
  if (String(card.fields?.medicine || "").trim().length < 3) return false;
  if (!Number.isFinite(Number(card.fields?.quantity)) || Number(card.fields.quantity) <= 0) return false;
  if (pharmacyBrain.findMedicine(card.fields.medicine).status !== "matched") return false;
  return ["cash", "mpesa", "credit", "mixed"].includes(String(card.fields?.payment || "").toLowerCase());
}

function prepareUnknownMedicineFallback(card, sourceText) {
  if (card.type !== "SaleCard") return card;
  if (pharmacyBrain.findMedicine(card.fields?.medicine).status === "matched") return card;
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

function addPhotoCards(fileName, scanType) {
  state.ui.screen = "chat";
  state.ui.workspace = "operations";
  const result = runVisualPipeline({ fileName, scanType });
  const visualCard = buildPhotoReviewCard(result);
  addCard(visualCard);
  refreshNotifications();
}

async function openLightweightCamera(scanType = "medicine_photo") {
  closeCameraStream();
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
    if (status) status.textContent = "Ready — avoid reflections, hold still, then tap Capture.";
    const actions = root.querySelector(".camera-actions");
    if (actions && state.camera.lightAvailable && !actions.querySelector('[data-action="toggle-camera-light"]')) {
      const lightButton = document.createElement("button");
      lightButton.type = "button";
      lightButton.dataset.action = "toggle-camera-light";
      lightButton.textContent = "Light on";
      lightButton.addEventListener("click", () => void toggleCameraLight());
      actions.insertBefore(lightButton, actions.lastElementChild);
    }
  } catch {
    state.camera.status = "Camera did not open. Allow camera access and try again.";
    render();
  }
}

function closeLightweightCamera() {
  closeCameraStream();
  state.camera.open = false;
  state.camera.status = "";
  state.camera.lightAvailable = false;
  state.camera.lightOn = false;
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
    state.camera.status = "Camera light is not available on this phone. Use room light and avoid reflections.";
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
  const scale = Math.min(1, 1800 / Math.max(video.videoWidth, video.videoHeight));
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
  state.camera.open = false;
  state.camera.status = "";
  render();
  const file = new File([blob], `${scanType}-${Date.now()}.jpg`, { type: "image/jpeg" });
  if (scanType === "invoice") await readInvoicePhoto(file);
  else addPhotoCards(file.name, scanType);
}

async function readInvoicePhoto(file) {
  state.ui.screen = "chat";
  state.ui.workspace = "operations";
  state.voice.status = "Reading invoice…";
  render();
  try {
    const upload = await resizeImageForReading(file);
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
      selling_price: "",
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
    card.title = "Check invoice medicines";
    card.source = `${result.supplier_name || "Supplier invoice"}${result.invoice_number ? ` · ${result.invoice_number}` : ""}`;
    card.validation = result.complete === false
      ? "This scan is incomplete and cannot be approved. Check the photo and scan again."
      : "I read this on your device. Check the medicines, then approve.";
    state.voice.status = "";
    addCard(card);
  } catch (error) {
    state.voice.status = "";
    addFeed("system", error?.message || "I could not read this invoice. Try a clearer photo.");
    render();
  }
}

function mergeRememberedInvoiceReview(rows, result) {
  const candidates = state.cards.filter((card) => {
    if (card.type !== "CatalogImportCard" || card.fields?.import_mode !== "invoice_ocr") return false;
    const sameNumber = result.invoice_number && card.fields.invoice_number === result.invoice_number;
    const sameSignature = result.supplier_name && result.invoice_date && result.invoice_total
      && card.fields.invoice_supplier === result.supplier_name
      && card.fields.invoice_date === result.invoice_date
      && Number(card.fields.invoice_total) === Number(result.invoice_total);
    return sameNumber || sameSignature;
  });
  const rememberedRows = candidates.flatMap((card) => catalogRowsForCard(card));
  const allRows = [...rows, ...rememberedRows];
  const groups = new Map();
  allRows.forEach((row) => {
    const key = normalizeMedicineKey(row.name);
    if (!key) return;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  });
  const targetTotal = Number(result.invoice_total || candidates[0]?.fields?.invoice_total || 0);
  const numericChoices = [...groups.values()].map((versions) => versions.filter(invoiceRowArithmeticValid).slice(0, 8));
  const exactSet = chooseInvoiceRowsByTotal(numericChoices, targetTotal);
  const chosenByName = new Map((exactSet || []).map((row) => [normalizeMedicineKey(row.name), row]));
  const merged = [...groups.entries()].map(([key, versions]) => {
    const strongest = [...versions].sort((left, right) => invoiceRowEvidenceScore(right) - invoiceRowEvidenceScore(left))[0];
    const combined = { ...(chosenByName.get(key) || strongest) };
    for (const field of ["form", "unit", "batch", "expiry"]) {
      if ([undefined, null, ""].includes(combined[field])) {
        combined[field] = versions.find((item) => ![undefined, null, ""].includes(item[field]))?.[field] || "";
      }
    }
    return combined;
  });
  const orderSource = candidates.map((card) => catalogRowsForCard(card)).sort((left, right) => right.length - left.length)[0] || rows;
  const sourceOrder = new Map(orderSource.map((row, index) => [normalizeMedicineKey(row.name), index]));
  merged.sort((left, right) => (sourceOrder.get(normalizeMedicineKey(left.name)) ?? 999) - (sourceOrder.get(normalizeMedicineKey(right.name)) ?? 999));
  normalizeRememberedBatchDigits(merged);
  const priorCard = candidates[0];
  return {
    rows: merged,
    metadata: {
      supplier_name: result.supplier_name || priorCard?.fields?.invoice_supplier || "",
      invoice_number: result.invoice_number || priorCard?.fields?.invoice_number || "",
      invoice_date: result.invoice_date || priorCard?.fields?.invoice_date || "",
      invoice_total: result.invoice_total ?? priorCard?.fields?.invoice_total ?? ""
    }
  };
}

function invoiceRowArithmeticValid(row) {
  return Number(row.stock) > 0 && Number(row.cost_price) >= 0 && Number(row.line_total) > 0
    && Math.abs(Number(row.stock) * Number(row.cost_price) - Number(row.line_total)) < 0.01;
}

function invoiceRowEvidenceScore(row) {
  return ["name", "form", "unit", "stock", "cost_price", "line_total", "batch", "expiry"]
    .filter((field) => ![undefined, null, ""].includes(row[field])).length + (invoiceRowArithmeticValid(row) ? 10 : 0);
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
  const scale = Math.min(1, 1800 / Math.max(bitmap.width, bitmap.height));
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

function addBarcodeCard() {
  addCard(createEditableCard({
    type: "VisualScanCard",
    title: "Check scan",
    source: "Barcode scanner placeholder",
    fields: { scan_type: "barcode", medicine: "", form: "", unit: "", pack_size: "", category: "" },
    confidence: 0.62,
    validation: "Barcode scans stay zero-token for known catalog items."
  }));
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
  if (state.onboarding.completed) {
    removeCardsByType(["OnboardingCard"]);
  }
  if (catalogHasItems()) {
    removeCardsByType(["CatalogOnboardingCard"]);
  }
  state.onboarding.started = state.cards.some((card) => card.type === "OnboardingCard");
  persistFeed();
  persistActiveCards();
}

function resetOnboarding() {
  const storage = safeLocalStorage();
  storage?.removeItem(SETUP_KEY);
  storage?.removeItem(CATALOG_KEY);
  storage?.removeItem(NOTIFICATION_KEY);
  storage?.removeItem(FEED_KEY);
  storage?.removeItem(ACTIVE_CARDS_KEY);
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
  const routes = backendAdapters.endpointLinks();
  addCard(createEditableCard({
    type: "ReportCard",
    title: "Check report",
    source: "Today report",
    fields: {
      period: "Today",
      focus: "Sales, stock, cash, M-Pesa, credit",
      backend_route: routes.dailyReport || "/reports/daily?send_whatsapp=false"
    },
    confidence: 0.94,
    validation: "Reports use corrected ledger totals through the live report route when backend sync is enabled."
  }));
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
    validation: "Stock corrections require owner confirmation and audit trail."
  }));
}

function addCard(card) {
  if (card.type === "CatalogImportCard") removeCardsByType(["CatalogOnboardingCard"]);
  state.cards.unshift(card);
  cloudGateway.saveCardHistory(card);
  persistActiveCards();
  render();
}

function addFeed(type, text) {
  state.feed.push({ id: `feed-${Date.now()}`, type, text, time: nowLabel() });
  state.feed = state.feed.slice(-FEED_RESUME_LIMIT);
  persistFeed();
}

function updateCardField(cardId, field, value) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card) return;
  card.fields[field] = value;
  persistActiveCards();
}

function updateCatalogImportCell(cardId, rowIndex, field, value) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card || card.type !== "CatalogImportCard") return;
  const rows = catalogRowsForCard(card);
  const index = Number(rowIndex);
  if (!Number.isInteger(index) || index < 0 || index >= rows.length) return;
  rows[index][field] = value;
  persistCatalogRows(card, rows);
  persistActiveCards();
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

function confirmCard(cardId) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card) return;
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
    saveCatalogItems([{
      name: card.fields.medicine,
      form: card.fields.form,
      unit: card.fields.unit,
      selling_price: card.fields.selling_price,
      stock: card.fields.stock,
      cost_price: card.fields.cost_price,
      supplier: card.fields.supplier,
      batch: card.fields.batch,
      expiry: card.fields.expiry,
      aliases: card.fields.alias ? [card.fields.alias] : [],
      source: "sale_time_learning"
    }]);
  }
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
}

function saveCatalogFromReviewCard(card) {
  const fields = card.fields || {};
  if (!fields.medicine) return;
  saveCatalogItems([{
    name: fields.medicine,
    form: fields.form,
    unit: fields.unit,
    pack_size: fields.pack_size,
    selling_price: fields.selling_price,
    cost_price: fields.cost_price,
    stock: fields.quantity || fields.stock || "",
    supplier: fields.supplier,
    barcode: fields.barcode,
    batch: fields.batch,
    expiry: fields.expiry,
    shelf: fields.shelf,
    source: card.type === "InvoiceCard" ? "invoice_review" : "scan_review"
  }]);
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
    addPhotoCards(name, "invoice");
    return;
  }
  if (lower.endsWith(".xls") || lower.endsWith(".xlsx")) {
    addCard(createEditableCard({
      type: "ImportMappingCard",
      title: "Map Excel import",
      source: name,
      fields: {
        file: name,
        mapping: "Export this file as CSV for the current zero-token import path.",
        missing_columns: "Excel binary parsing adapter is reserved.",
        notes: "CSV/text import is supported now. Excel mapping will use the same catalog review card after adapter wiring."
      },
      confidence: 0.62,
      status: "needs_correction",
      validation: "No AI or backend call was used."
    }));
    return;
  }
  const text = await file.text();
  if (lower.endsWith(".csv") || lower.endsWith(".tsv") || text.includes(",")) {
    const parsed = parseDelimitedInventory(text, sourceBrain);
    addCard(createPasteImportCard(catalogItemsToText(parsed.items)));
    return;
  }
  addCard(createPasteImportCard(text));
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
  const csv = buildCatalogCsv(pharmacyBrain.catalog);
  downloadTextFile({
    filename: "ms20-pharmacy-catalog.csv",
    contents: csv,
    mime: "text/csv;charset=utf-8"
  });
  addFeed("system", "Catalog CSV downloaded.");
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
  const fields = Object.entries(card.fields || {}).map(([key, value]) => `${key.replaceAll("_", " ")} ${value}`).join(". ");
  const utterance = new SpeechSynthesisUtterance(`${card.title}. ${fields}`);
  utterance.lang = "en-KE";
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

function recordCard(card) {
  const backend = backendAdapters.prepareBackendAction(card, state.liveBackend);
  card.integration = backend;
  const action = {
    id: `action-${card.id}`,
    type: card.type,
    fields: card.fields,
    backend,
    localFirst: true,
    aiUsed: false
  };
  const result = syncAdapter.queueAction(action);
  if (result.added && (card.type === "SaleCard" || card.type === "VoiceReviewCard" || card.type === "MedicineMatchCard")) {
    applyLocalSaleStock(card);
    updateTodayTotals(card);
  }
  if (result.added && card.type === "RestockCard") {
    applyLocalRestockStock(card);
  }
  addFeed("system", result.duplicate ? "Already saved." : savedReplyFor(card));
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
  const quantity = Number(card.fields?.quantity || 0);
  if (!Number.isFinite(currentStock) || !Number.isFinite(quantity)) {
    card.fields.stockLeft = null;
    return;
  }
  const remaining = Math.max(0, currentStock - quantity);
  medicine.stockLeft = remaining;
  card.fields.stockLeft = remaining;
  state.catalog.items = pharmacyBrain.catalog;
  safeLocalStorage()?.setItem(CATALOG_KEY, JSON.stringify(state.catalog.items));
  void cloudGateway.saveCatalog(state.pharmacy.id, state.catalog.items);
}

function applyLocalRestockStock(card) {
  const match = pharmacyBrain.findMedicine(card.fields?.medicine);
  if (match.status !== "matched") return;
  const medicine = match.matches[0];
  const quantity = Number(card.fields?.quantity || 0);
  card.fields.medicine = medicine.name;
  if (!Number.isFinite(quantity) || quantity <= 0) return;
  const currentStock = medicine.stockLeft === null || medicine.stockLeft === undefined || medicine.stockLeft === ""
    ? 0
    : Number(medicine.stockLeft);
  if (!Number.isFinite(currentStock)) return;
  const stockLeft = currentStock + quantity;
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

function setPayment(cardId, payment) {
  updateCardField(cardId, "payment", payment);
  render();
}

function bumpQuantity(cardId, amount) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card) return;
  const current = Number(card.fields.quantity || 0);
  card.fields.quantity = Math.max(0, current + amount);
  persistActiveCards();
  render();
}

async function syncNow() {
  const result = await syncAdapter.syncPending();
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

function friendlyCardLabel(card) {
  const labels = {
    SaleCard: "Sale",
    InvoiceCard: "Invoice",
    RestockCard: "Restock",
    OnboardingCard: "Setup",
    StockCorrectionCard: "Stock fix",
    ReportCard: "Report",
    VoiceReviewCard: "Voice",
    PhotoReviewCard: "Photo",
    MedicineMatchCard: "Medicine check",
    VisualScanCard: "Scan",
    CatalogOnboardingCard: "Onboarding",
    CatalogImportCard: "Catalog",
    ImportMappingCard: "Import",
    NotificationCard: "Notification",
    DocumentExportCard: "Document",
    SyncReviewCard: "Sync"
  };
  return labels[card.type] || "Review";
}

function ownerCardNote(card) {
  if (card.type === "CatalogImportCard" && card.fields?.import_incomplete === "true") return "This scan is incomplete. Scan again before saving anything.";
  if (card.type === "CatalogImportCard") return "Review the list, edit if needed, then approve.";
  if (card.status === "needs_correction") return "Edit anything that looks wrong, then confirm.";
  if (card.type === "SaleCard") return "Complete the sale details, then confirm.";
  if (card.type === "VoiceReviewCard") return "Check the voice result, then confirm.";
  if (card.type === "InvoiceCard") return "Check the invoice before saving.";
  if (card.type === "PhotoReviewCard" || card.type === "VisualScanCard") return "Check the photo details before saving.";
  if (card.type === "CatalogOnboardingCard") return "Choose the easiest way to add medicines.";
  if (card.type === "ImportMappingCard") return "Map the columns once, then MS2.0 can reuse the pattern.";
  if (card.type === "NotificationCard") return "Generated locally from pharmacy records.";
  if (card.type === "DocumentExportCard") return "Download or print when ready.";
  if (card.type === "ReportCard") return "Check the report request before saving.";
  if (card.type === "SyncReviewCard") return "Review saved work before syncing.";
  return "Check the details, then confirm.";
}

function savedReplyFor(card) {
  if (card.type === "SaleCard" || card.type === "VoiceReviewCard") {
    const medicine = card.fields?.medicine || "Sale";
    const quantity = card.fields?.quantity || "1";
    const payment = paymentLabel(String(card.fields?.payment || "cash").toLowerCase());
    const lines = [`✅ ${medicine} x${quantity} recorded • ${payment}`];
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
  if (card.type === "StockCorrectionCard") return "Stock correction saved.";
  if (card.type === "RestockCard") {
    const medicine = card.fields?.medicine || "Medicine";
    const quantity = card.fields?.quantity || "0";
    const unit = card.fields?.unit || "item";
    const lines = [`✅ ${medicine} +${quantity} ${unit}${Number(quantity) === 1 ? "" : "s"} added`];
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
    return cards.filter(isDurableCard).slice(0, ACTIVE_CARD_RESUME_LIMIT);
  } catch {
    return [];
  }
}

function persistActiveCards() {
  const cards = (state.cards || []).filter(isDurableCard).slice(0, ACTIVE_CARD_RESUME_LIMIT);
  safeLocalStorage()?.setItem(ACTIVE_CARDS_KEY, JSON.stringify(cards));
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
  return {
    name: row.name || row.medicine || "",
    form: row.form || first(row.forms),
    unit: row.unit || first(row.units) || row.form || "",
    stock: row.stock ?? row.current_stock ?? row.quantity ?? row.stockLeft ?? "",
    cost_price: row.cost_price ?? row.costPrice ?? "",
    line_total: row.line_total ?? row.lineTotal ?? "",
    selling_price: row.selling_price ?? row.sellingPrice ?? "",
    supplier: row.supplier || "",
    batch: row.batch || first(row.batches)?.batch || "",
    expiry: row.expiry || first(row.batches)?.expiry || "",
    barcode: row.barcode || "",
    source: row.source || "owner_review"
  };
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
  return FIELD_LABELS[field] || field.replaceAll("_", " ");
}

function inputModeForField(field) {
  if (["quantity", "stock", "current_stock", "correct_stock", "stockLeft"].includes(field)) return "numeric";
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

window.addEventListener("online", render);
window.addEventListener("offline", render);

void sourceBrain.lookupMedicine("demo");
void aiFallback.enabled;

render();
window.setInterval(hideReplitBadge, 1500);
if (shouldAutoProbeBackend()) {
  void refreshLiveStatus({ silent: true });
}
