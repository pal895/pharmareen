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
const SETUP_KEY = "ms20-main-app:onboarding-complete";
const CARD_FONT_SCALE_KEY = "ms20-main-app:card-font-scale";
const CARD_FONT_SCALE_MIN = 0.85;
const CARD_FONT_SCALE_MAX = 1.25;
const CARD_FONT_SCALE_STEP = 0.1;
let activeRecognition = null;

state.ui = { screen: "home" };
state.voice = { listening: false, status: "" };
state.onboarding = { started: false, completed: setupComplete() };
state.cardFontScale = readCardFontScale();
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
    <main class="chat-app" style="--card-font-scale: ${state.cardFontScale};">
      ${state.ui.screen === "chat" ? chatScreenTemplate() : chatHomeTemplate()}
    </main>
  `;
  bindEvents();
  hideReplitBadge();
  scrollChatToBottom();
}

function chatHomeTemplate() {
  const setupReady = state.onboarding.completed;
  return `
    <section class="chat-home" aria-label="MS2.0 chat home">
      <header class="home-header">
        <div class="brand-lockup">
          <span class="brand-mark">MS2.0</span>
          <span>Pharmacy operating intelligence</span>
        </div>
      </header>
      <button class="conversation-row" type="button" data-action="open-chat" aria-label="Open MS2.0 Assistant">
        <span class="assistant-avatar">M</span>
        <span class="conversation-copy">
          <strong>MS2.0 Assistant</strong>
          <small>${setupReady ? "Ready" : "Setup needed"}</small>
          <span>${setupReady ? "Ask, record, scan, or manage your pharmacy." : "Set up your pharmacy to begin."}</span>
        </span>
        <span class="row-arrow">Open</span>
      </button>
    </section>
  `;
}

function chatScreenTemplate() {
  return `
    <section class="chat-screen" aria-label="MS2.0 assistant conversation">
      <header class="chat-header">
        <button class="icon-button" type="button" data-action="back-home" aria-label="Back to chat home">&lt;</button>
        <span class="assistant-avatar">M</span>
        <span class="chat-title">
          <strong>MS2.0</strong>
          <small>${state.sync.online ? "Online" : "Offline"} / ${state.onboarding.completed ? "Ready" : "Setup needed"}</small>
        </span>
        ${adminMenuTemplate()}
      </header>
      <section class="chat-body" id="chatBody" aria-label="Messages">
        <div class="message-list">
          ${chatMessageTemplates()}
          ${state.cards.map(cardTemplate).join("")}
        </div>
      </section>
      ${composerTemplate()}
    </section>
  `;
}

function chatMessageTemplates() {
  const intro = {
    id: "intro",
    type: "system",
    text: state.onboarding.completed ? `${greetingText()} How can I help today?` : "Welcome. Let's set up your pharmacy first.",
    time: "Now"
  };
  return [intro, ...state.feed].map(feedItemTemplate).join("");
}

function feedItemTemplate(item) {
  return `
    <article class="message-bubble ${item.type}" aria-label="${item.type === "owner" ? "You" : "MS2.0"} message">
      <p>${escapeHtml(item.text)}</p>
      <span>${item.type === "owner" ? "You" : "MS2.0"} / ${escapeHtml(item.time)}</span>
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
          <button type="button" data-action="demo-invoice">Invoice</button>
          <button type="button" data-action="demo-barcode">Scan</button>
          <button type="button" data-action="demo-stock-correction">Stock fix</button>
          <button type="button" data-action="demo-report">Report</button>
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
        ${cardFontControlsTemplate()}
      </div>
      <div class="field-grid">
        ${displayed.map((field) => fieldTemplate(card, field)).join("")}
      </div>
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

function fieldTemplate(card, field) {
  const value = card.fields?.[field] ?? "";
  return `
    <label>
      <span>${escapeHtml(field.replaceAll("_", " "))}</span>
      <input data-card-id="${card.id}" data-field="${field}" value="${escapeHtml(String(value))}">
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

  root.querySelector("#photoInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    addPhotoCards(file?.name || "camera-photo.jpg", "medicine_photo");
  });

  root.querySelector("#cameraInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    addPhotoCards(file?.name || "camera-photo.jpg", "medicine_photo");
  });
}

function handleAction(dataset) {
  const action = dataset.action;
  if (action === "open-chat") {
    state.ui.screen = "chat";
    ensureOnboardingStarted();
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
  if (action === "take-photo") root.querySelector("#cameraInput")?.click();
  if (action === "upload-photo") root.querySelector("#photoInput")?.click();
  if (action === "demo-barcode") addBarcodeCard();
  if (action === "demo-invoice") addPhotoCards("supplier-invoice.jpg", "invoice");
  if (action === "demo-onboarding") addOnboardingCard();
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
  if (action === "set-payment") setPayment(dataset.cardId, dataset.payment);
  if (action === "bump-quantity") bumpQuantity(dataset.cardId, Number(dataset.amount));
}

function handleCommand(text) {
  state.ui.screen = "chat";
  const trimmed = String(text || "").trim();
  if (!state.onboarding.completed) {
    ensureOnboardingStarted();
    render();
    return;
  }
  if (!trimmed) {
    addFeed("system", "Please add medicine, quantity, and payment. Example: Panadol 2 cash.");
    render();
    return;
  }

  const card = buildCommandCard(trimmed);
  addFeed("owner", trimmed);
  if (canRecordInstantly(card, trimmed)) {
    recordCard(card);
    render();
  } else {
    addCard(card);
  }
}

function handleVoiceTranscript(text) {
  state.ui.screen = "chat";
  const card = buildCommandCard(text);
  addFeed("owner", text);
  if (canRecordInstantly(card, text)) {
    recordCard(card);
    render();
  } else {
    card.type = "VoiceReviewCard";
    card.title = "Check voice result";
    card.fields = {
      transcript: text,
      medicine: card.fields?.medicine || "",
      quantity: card.fields?.quantity || "",
      payment: card.fields?.payment || ""
    };
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
  return ["cash", "mpesa", "credit", "mixed"].includes(String(card.fields?.payment || "").toLowerCase());
}

function commandHasExplicitPayment(text) {
  return /(?:^|[\s\d-])(cash|mpesa|m-pesa|credit|mixed)$/i.test(String(text || "").trim());
}

function addPhotoCards(fileName, scanType) {
  state.ui.screen = "chat";
  const result = runVisualPipeline({ fileName, scanType });
  const visualCard = buildPhotoReviewCard(result);
  addCard(visualCard);
  if (scanType !== "invoice") {
    addCard(createEditableCard({
      type: "PhotoReviewCard",
      title: "Check photo details",
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
  if (state.onboarding.completed || state.onboarding.started) return;
  state.cards.unshift(createOnboardingCard());
  state.onboarding.started = true;
}

function resetOnboarding() {
  safeLocalStorage()?.removeItem(SETUP_KEY);
  state.onboarding.completed = false;
  state.onboarding.started = false;
  state.cards = state.cards.filter((card) => card.type !== "OnboardingCard");
  ensureOnboardingStarted();
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
  recordCard(card);
  if (card.type === "OnboardingCard") {
    state.onboarding.completed = true;
    safeLocalStorage()?.setItem(SETUP_KEY, "true");
  }
  removeCard(cardId);
  render();
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
  if (result.added && (card.type === "SaleCard" || card.type === "VoiceReviewCard")) {
    updateTodayTotals(card);
  }
  addFeed("system", result.duplicate ? "Already saved." : savedReplyFor(card));
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
  render();
}

function rejectCard(cardId) {
  const card = state.cards.find((item) => item.id === cardId);
  removeCard(cardId);
  if (card?.type === "OnboardingCard") state.onboarding.started = false;
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
  if (index >= 0) state.cards.splice(index, 1);
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
    SyncReviewCard: "Sync"
  };
  return labels[card.type] || "Review";
}

function ownerCardNote(card) {
  if (card.status === "needs_correction") return "Edit anything that looks wrong, then confirm.";
  if (card.type === "SaleCard") return "Complete the sale details, then confirm.";
  if (card.type === "VoiceReviewCard") return "Check the voice result, then confirm.";
  if (card.type === "InvoiceCard") return "Check the invoice before saving.";
  if (card.type === "PhotoReviewCard" || card.type === "VisualScanCard") return "Check the photo details before saving.";
  if (card.type === "ReportCard") return "Check the report request before saving.";
  if (card.type === "SyncReviewCard") return "Review saved work before syncing.";
  return "Check the details, then confirm.";
}

function savedReplyFor(card) {
  if (card.type === "SaleCard" || card.type === "VoiceReviewCard") {
    const medicine = card.fields?.medicine || "Sale";
    const quantity = card.fields?.quantity || "1";
    const payment = paymentLabel(String(card.fields?.payment || "cash").toLowerCase());
    const lines = [
      "Sale recorded.",
      `${medicine} x${quantity}`,
      `Payment: ${payment}`
    ];
    const stockLine = stockReplyLine(card);
    if (stockLine) lines.push(stockLine);
    return lines.join("\n");
  }
  if (card.type === "StockCorrectionCard") return "Stock correction saved.";
  if (card.type === "RestockCard") return "Restock saved.";
  if (card.type === "OnboardingCard") return "Setup saved.";
  if (card.type === "ReportCard") return "Report request saved.";
  return "Saved.";
}

function setupComplete() {
  return safeLocalStorage()?.getItem(SETUP_KEY) === "true";
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
  const stockLeft = Number(card.fields?.stockLeft);
  const quantity = Number(card.fields?.quantity || 0);
  if (!Number.isFinite(stockLeft)) return "";
  const remaining = Math.max(0, stockLeft - quantity);
  return `Stock left: ${remaining}`;
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
