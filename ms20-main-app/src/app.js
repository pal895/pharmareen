import { demoState, nowLabel } from "./data/demoState.js";
import { CloudMemoryGateway } from "./services/cloudGateway.js";
import { OfflineQueue } from "./services/offlineQueue.js";
import { SyncAdapter } from "./services/syncAdapter.js";
import { BackendAdapterRegistry } from "./services/backendAdapters.js";
import { PharmacyBrain, SourceBrain, AIFallbackAdapter } from "./services/brainAdapters.js";
import { runVisualPipeline, buildPhotoReviewCard } from "./services/visualPipeline.js";
import { cardFieldsFor, createEditableCard, paymentOptions, quantityBumps } from "./cards/editableCards.js";
import { listRouteSlots, resolveOfflineSlot } from "./routes/routeRegistry.js";
import { TokenPolicy, CloudMemoryContract } from "./contracts/integrationContracts.js";

const state = structuredClone(demoState);
const cloudGateway = new CloudMemoryGateway();
const queue = new OfflineQueue();
const syncAdapter = new SyncAdapter({ queue, cloudGateway });
const backendAdapters = new BackendAdapterRegistry();
const pharmacyBrain = new PharmacyBrain({ pharmacyId: state.pharmacy.id });
const sourceBrain = new SourceBrain();
const aiFallback = new AIFallbackAdapter();

state.liveBackend = {
  baseUrl: backendAdapters.liveBackendGateway.baseUrl,
  health: { ok: false, status: 0 },
  readinessSummary: { status: "not_checked", sheets: false, baileys: false, offline: false, blocked: [] },
  routes: backendAdapters.endpointLinks(),
  writeMode: "safe_queue_only",
  tokenImpact: "zero_openai_api_tokens"
};

const root = document.querySelector("#app");

function render() {
  state.sync.online = navigator.onLine;
  state.sync.pending = queue.pendingCount();
  root.innerHTML = `
    <aside class="side-nav" aria-label="Main navigation">
      <div class="brand-mark">MS2.0</div>
      <button class="nav-button active" data-action="focus-chat">Action</button>
      <button class="nav-button" data-action="demo-onboarding">Setup</button>
      <button class="nav-button" data-action="demo-report">Reports</button>
      <button class="nav-button" data-action="demo-sync">Sync</button>
    </aside>
    <main class="workspace">
      ${dashboardTemplate()}
      <section class="work-grid">
        ${actionFeedTemplate()}
        ${cardWorkspaceTemplate()}
      </section>
    </main>
  `;
  bindEvents();
}

function dashboardTemplate() {
  const onlineText = state.sync.online ? "Online" : "Offline";
  const offlineSlot = resolveOfflineSlot(state.liveBackend);
  const live = state.liveBackend || {};
  const readiness = live.readinessSummary || {};
  return `
    <section class="dashboard" aria-label="Dashboard">
      <div>
        <p class="eyebrow">Pharmacy workspace</p>
        <h1>${escapeHtml(state.pharmacy.name)}</h1>
        <p class="muted">Cloud memory is the source of truth. This device is cache and queue only.</p>
      </div>
      <div class="status-strip">
        <span class="status-pill ${state.sync.online ? "ok" : "warn"}">${onlineText}</span>
        <span class="status-pill ${live.health?.ok ? "ok" : "warn"}">Backend: ${live.health?.ok ? "OK" : "Check"}</span>
        <span class="status-pill ${readiness.sheets ? "ok" : "warn"}">Sheets: ${readiness.sheets ? "OK" : "Check"}</span>
        <span class="status-pill ${readiness.baileys ? "ok" : "warn"}">Baileys: ${readiness.baileys ? "OK" : "Check"}</span>
        <span class="status-pill">Cloud: ${cloudGateway.status().mode}</span>
        <span class="status-pill">Queue: ${state.sync.pending}</span>
      </div>
      <div class="metric-row">
        <div class="metric"><span>Today</span><strong>KES ${state.today.sales}</strong></div>
        <div class="metric"><span>Cash</span><strong>${state.today.cash}</strong></div>
        <div class="metric"><span>M-Pesa</span><strong>${state.today.mpesa}</strong></div>
        <div class="metric"><span>Credit</span><strong>${state.today.credit}</strong></div>
      </div>
      <div class="quick-row">
        <button data-action="demo-sale">Sale</button>
        <button data-action="demo-voice">Tap & Talk</button>
        <button data-action="demo-photo">Photo</button>
        <button data-action="demo-invoice">Invoice</button>
        <button data-action="demo-stock-correction">Stock fix</button>
        <button data-action="refresh-live-status">Live status</button>
        <a class="button-link" href="${escapeHtml(offlineSlot.url)}" target="_blank" rel="noreferrer">Offline app</a>
      </div>
      <p class="micro-copy">Offline route: ${offlineSlot.liveCompatibility}. Backend mode: ${escapeHtml(live.writeMode || "safe_queue_only")}.</p>
    </section>
  `;
}

function actionFeedTemplate() {
  return `
    <section class="panel action-panel" aria-label="Action feed">
      <div class="panel-header">
        <div>
          <p class="eyebrow">Fast flow</p>
          <h2>Talk, type, scan</h2>
        </div>
        <span class="tiny-badge">Zero-token first</span>
      </div>
      <div class="feed" id="feed">
        ${state.feed.map(feedItemTemplate).join("")}
      </div>
      <form class="command-bar" id="commandForm">
        <button type="button" title="Tap and talk" data-action="demo-voice">Voice</button>
        <button type="button" title="Upload photo" data-action="demo-photo">Photo</button>
        <button type="button" title="Barcode placeholder" data-action="demo-barcode">Scan</button>
        <input id="commandInput" type="text" autocomplete="off" placeholder="Try: Panadol 2 cash">
        <button type="submit">Go</button>
      </form>
      <input id="photoInput" class="hidden-input" type="file" accept="image/*">
    </section>
  `;
}

function feedItemTemplate(item) {
  return `
    <article class="feed-item ${item.type}">
      <span>${escapeHtml(item.time)}</span>
      <p>${escapeHtml(item.text)}</p>
    </article>
  `;
}

function cardWorkspaceTemplate() {
  return `
    <section class="panel card-panel" aria-label="Editable card workspace">
      <div class="panel-header">
        <div>
          <p class="eyebrow">Editable cards</p>
          <h2>Confirm before saving</h2>
        </div>
        <button data-action="sync-now">Sync ${queue.pendingCount()}</button>
      </div>
      <div class="card-list">
        ${state.cards.length ? state.cards.map(cardTemplate).join("") : emptyCardTemplate()}
      </div>
      <details class="contracts">
        <summary>Integration contracts</summary>
        <div class="contract-grid">
          <pre>${escapeHtml(JSON.stringify(TokenPolicy, null, 2))}</pre>
          <pre>${escapeHtml(JSON.stringify(CloudMemoryContract, null, 2))}</pre>
          <pre>${escapeHtml(JSON.stringify(listRouteSlots(state.liveBackend), null, 2))}</pre>
        </div>
      </details>
    </section>
  `;
}

function emptyCardTemplate() {
  return `
    <div class="empty-state">
      <strong>No active card</strong>
      <p>Send a command, tap voice, upload a photo, or start setup.</p>
    </div>
  `;
}

function cardTemplate(card) {
  const fields = cardFieldsFor(card.type);
  const displayed = fields.length ? fields : Object.keys(card.fields || {});
  const queued = card.status === "queued";
  return `
    <article class="editable-card ${card.status}" data-card-id="${card.id}">
      <div class="card-top">
        <div>
          <span class="card-type">${escapeHtml(card.type)}</span>
          <h3>${escapeHtml(card.title)}</h3>
        </div>
        <span class="confidence">${Math.round((card.confidence || 0) * 100)}%</span>
      </div>
      ${card.source ? `<p class="source-line">From: ${escapeHtml(card.source)}</p>` : ""}
      ${card.parser ? `<p class="source-line">Parser: ${escapeHtml(card.parser)}</p>` : ""}
      ${card.integration ? `<p class="integration-line">Backend: ${escapeHtml(card.integration.summary)}</p>` : ""}
      <div class="field-grid">
        ${displayed.map((field) => fieldTemplate(card, field)).join("")}
      </div>
      ${!queued && (card.type === "SaleCard" || card.type === "VoiceReviewCard") ? paymentToolbar(card) : ""}
      ${!queued && (card.type === "SaleCard" || card.type === "RestockCard") ? quantityToolbar(card) : ""}
      <div class="validation ${card.aiRequired ? "warn" : "ok"}">${escapeHtml(card.validation || "")}</div>
      ${queued ? queuedActionsTemplate() : activeActionsTemplate(card)}
    </article>
  `;
}

function fieldTemplate(card, field) {
  const value = card.fields?.[field] ?? "";
  const disabled = card.status === "queued" ? " disabled" : "";
  return `
    <label>
      <span>${escapeHtml(field.replaceAll("_", " "))}</span>
      <input data-card-id="${card.id}" data-field="${field}" value="${escapeHtml(String(value))}"${disabled}>
    </label>
  `;
}

function activeActionsTemplate(card) {
  return `
    <div class="card-actions">
      <button data-action="confirm-card" data-card-id="${card.id}">Confirm</button>
      <button data-action="correct-card" data-card-id="${card.id}">Correct</button>
      <button data-action="reject-card" data-card-id="${card.id}">Cancel</button>
    </div>
  `;
}

function queuedActionsTemplate() {
  return `
    <div class="card-actions">
      <button type="button" disabled>Queued</button>
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

  root.querySelector("#photoInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    addPhotoCards(file?.name || "camera-photo.jpg", "medicine_photo");
  });
}

function handleAction(dataset) {
  const action = dataset.action;
  if (action === "focus-chat") root.querySelector("#commandInput")?.focus();
  if (action === "demo-sale") handleCommand("Panadol 2 cash");
  if (action === "demo-voice") addVoiceCard();
  if (action === "demo-photo") root.querySelector("#photoInput")?.click();
  if (action === "demo-barcode") addBarcodeCard();
  if (action === "demo-invoice") addPhotoCards("supplier-invoice.jpg", "invoice");
  if (action === "demo-onboarding") addOnboardingCard();
  if (action === "demo-report") addReportCard();
  if (action === "demo-sync") addSyncCard();
  if (action === "demo-stock-correction") addStockCorrectionCard();
  if (action === "refresh-live-status") void refreshLiveStatus();
  if (action === "sync-now") syncNow();
  if (action === "confirm-card") confirmCard(dataset.cardId);
  if (action === "correct-card") correctCard(dataset.cardId);
  if (action === "reject-card") rejectCard(dataset.cardId);
  if (action === "set-payment") setPayment(dataset.cardId, dataset.payment);
  if (action === "bump-quantity") bumpQuantity(dataset.cardId, Number(dataset.amount));
}

function handleCommand(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed) {
    addFeed("system", "Type a command like Panadol 2 cash, or tap a quick action.");
    render();
    return;
  }
  const catalog = pharmacyBrain.catalog;
  const card = backendAdapters.adapters.commandParserAdapter.toCard(trimmed, catalog);
  card.integration = backendAdapters.prepareBackendAction(card, state.liveBackend);
  card.validation = `${card.validation || ""} ${card.integration.summary}`.trim();
  addFeed("owner", trimmed);
  addFeed("system", `${card.title} created locally. ${card.integration.summary} No AI token used.`);
  addCard(card);
}

function addVoiceCard() {
  const card = createEditableCard({
    type: "VoiceReviewCard",
    title: "Review voice",
    source: "Tap & Talk demo",
    fields: { transcript: "Panadol 2 cash", medicine: "Panadol", quantity: "2", payment: "cash" },
    confidence: 0.76,
    validation: "Voice capture placeholder. Local parser runs before AI."
  });
  addFeed("system", "Voice review card ready. Confirm or edit.");
  addCard(card);
}

function addPhotoCards(fileName, scanType) {
  const result = runVisualPipeline({ fileName, scanType });
  const visualCard = buildPhotoReviewCard(result);
  addFeed("system", `${scanType === "invoice" ? "Invoice" : "Photo"} scan card ready. No AI token used.`);
  addCard(visualCard);
  if (scanType !== "invoice") {
    addCard(createEditableCard({
      type: "PhotoReviewCard",
      title: "Review photo details",
      source: fileName,
      fields: { file: fileName, medicine: "", form: "", unit: "", pack_size: "" },
      confidence: result.confidence,
      validation: "Owner correction will save to pharmacy visual memory."
    }));
  }
}

function addBarcodeCard() {
  addCard(createEditableCard({
    type: "VisualScanCard",
    title: "Review barcode scan",
    source: "Barcode scanner placeholder",
    fields: { scan_type: "barcode", medicine: "", form: "", unit: "", pack_size: "", category: "" },
    confidence: 0.62,
    validation: "Barcode scans stay zero-token for known catalog items."
  }));
}

function addOnboardingCard() {
  addCard(createEditableCard({
    type: "OnboardingCard",
    title: "Review setup",
    source: "Setup assistant",
    fields: { pharmacy: "", owner: "", branch: "Main", location: "", payments: "cash, mpesa, credit" },
    confidence: 0.86,
    validation: "Confirmed setup saves to cloud memory."
  }));
}

function addReportCard() {
  const routes = backendAdapters.endpointLinks();
  addCard(createEditableCard({
    type: "ReportCard",
    title: "Review report",
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
    title: "Review sync",
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
    title: "Review stock correction",
    source: "Manual stock fix",
    fields: { medicine: "", current_stock: "", correct_stock: "", reason: "" },
    confidence: 0.82,
    validation: "Stock corrections require owner confirmation and audit trail."
  }));
}

function addCard(card) {
  state.cards.unshift(card);
  cloudGateway.saveCardHistory(card);
  render();
}

function addFeed(type, text) {
  state.feed.push({ id: `feed-${Date.now()}`, type, text, time: nowLabel() });
}

function updateCardField(cardId, field, value) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card) return;
  card.fields[field] = value;
}

function confirmCard(cardId) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card) return;
  if (card.status === "queued") {
    addFeed("system", "This card is already queued.");
    render();
    return;
  }
  const backend = backendAdapters.prepareBackendAction(card, state.liveBackend);
  card.integration = backend;
  if (!card.validation?.includes(backend.summary)) {
    card.validation = `${card.validation || ""} ${backend.summary}`.trim();
  }
  card.status = "queued";
  const action = {
    id: `action-${card.id}`,
    type: card.type,
    fields: card.fields,
    backend,
    localFirst: true,
    aiUsed: false
  };
  const result = syncAdapter.queueAction(action);
  if (result.added && card.type === "SaleCard") {
    const amount = Number(card.fields.quantity || 0);
    state.today.sales += amount;
    if (card.fields.payment === "mpesa") state.today.mpesa += amount;
    else if (card.fields.payment === "credit") state.today.credit += amount;
    else state.today.cash += amount;
  }
  addFeed("system", result.duplicate ? "Duplicate action blocked." : "Saved to offline queue. Sync when ready.");
  render();
}

function correctCard(cardId) {
  const card = state.cards.find((item) => item.id === cardId);
  if (!card) return;
  card.status = "needs_correction";
  card.validation = "Edit the fields, then confirm.";
  render();
}

function rejectCard(cardId) {
  state.cards.splice(state.cards.findIndex((item) => item.id === cardId), 1);
  addFeed("system", "Card cancelled.");
  render();
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
  render();
}

async function syncNow() {
  const result = await syncAdapter.syncPending();
  state.sync.lastSync = result.lastSync || "Not synced";
  addFeed("system", `Synced ${result.synced.length} queued action(s).`);
  render();
}

async function refreshLiveStatus({ silent = false } = {}) {
  const snapshot = await backendAdapters.getLiveStatus();
  state.liveBackend = snapshot;
  if (!silent) {
    const sheets = snapshot.readinessSummary?.sheets ? "Sheets OK" : "Sheets check needed";
    const offline = snapshot.offlineApp?.ok ? "offline app linked" : "offline app not reachable";
    addFeed("system", `Live status: backend ${snapshot.health?.ok ? "OK" : "not reachable"}, ${sheets}, ${offline}.`);
  }
  render();
  return snapshot;
}

function paymentLabel(payment) {
  if (payment === "mpesa") return "M-Pesa";
  return payment.charAt(0).toUpperCase() + payment.slice(1);
}

function shouldAutoProbeBackend() {
  if (typeof window === "undefined") return false;
  if (window.__MS20_AUTO_PROBE_BACKEND__ === true) return true;
  return window.location.port === "5000";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

window.addEventListener("online", render);
window.addEventListener("offline", render);

void sourceBrain.lookupMedicine("demo");
void aiFallback.enabled;

render();
if (shouldAutoProbeBackend()) {
  void refreshLiveStatus({ silent: true });
}
