const statusEl = document.getElementById("status");
const form = document.getElementById("actionForm");
const pendingList = document.getElementById("pendingList");
const DB_KEY = "pharmareen_legacy_media_safe_queue";
const SYNC_ENDPOINT = "/offline/sync";
const LEGACY_SYNC_ENDPOINT = "/sync/offline-actions";

function loadActions() { try { return JSON.parse(localStorage.getItem(DB_KEY) || "[]"); } catch { return []; } }
function saveActions(actions) { localStorage.setItem(DB_KEY, JSON.stringify(actions)); renderPending(); }
function setStatus(state, text) { if (statusEl) { statusEl.className = `banner ${state}`; statusEl.textContent = text; } }
function renderPending() {
  if (!pendingList) return;
  pendingList.innerHTML = loadActions().map(action => `<li>${action.type}: ${action.file_name || action.drug_name || action.command_text || "entry"} - ${action.sync_status}</li>`).join("");
}
function disableRequired() {
  document.querySelectorAll("[required]").forEach(element => { element.required = false; element.removeAttribute("required"); });
  document.querySelectorAll("form").forEach(item => { item.noValidate = true; });
}
function queueFiles(inputId, type) {
  const input = document.getElementById(inputId);
  return Array.from((input && input.files) || []).map(file => ({
    id: `${type}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    type,
    action: type,
    file_name: file.name,
    file_type: file.type,
    size: file.size,
    timestamp: new Date().toISOString(),
    sync_status: "pending",
    retry_count: 0,
    last_error: ""
  }));
}

function canRetryAction(action) {
  return !action.retry_count || action.retry_count < 10;
}

async function syncActions() {
  if (!navigator.onLine) return;
  const actions = loadActions();
  const pending = actions.filter(action => action.sync_status !== "synced" && canRetryAction(action));
  if (!pending.length) return;
  setStatus("syncing", "Syncing...");
  const payload = { entries: pending, actions: pending };
  try {
    let response = await fetch(SYNC_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      response = await fetch("/sync/offline-actions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }
    if (!response.ok) throw new Error(`Sync failed: ${response.status}`);
    const data = await response.json().catch(() => ({}));
    const syncedIds = new Set([...(data.synced || []), ...(data.processed || [])].map(item => item.id).filter(Boolean));
    const next = actions.map(action => {
      if (syncedIds.has(action.id) || !syncedIds.size) return { ...action, sync_status: "synced", last_error: "" };
      return action;
    });
    saveActions(next);
    setStatus("synced", "Synced");
  } catch (error) {
    const next = actions.map(action => {
      if (pending.some(item => item.id === action.id)) {
        return {
          ...action,
          retry_count: (action.retry_count || 0) + 1,
          last_error: error && error.message ? error.message : "Sync failed",
          sync_status: "pending"
        };
      }
      return action;
    });
    saveActions(next);
    setStatus("error", "Some items not synced yet");
  }
}
if (form) {
  form.noValidate = true;
  form.addEventListener("submit", event => {
    event.preventDefault();
    disableRequired();
    const actions = loadActions();
    const drug = (document.getElementById("drug_name")?.value || "").trim();
    const photos = queueFiles("image", "photo");
    const audios = queueFiles("voice", "audio");
    if (drug) {
      actions.push({
        id: `legacy-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        type: document.getElementById("action_type")?.value || "sale",
        drug_name: drug,
        quantity: Number(document.getElementById("quantity")?.value || 1),
        timestamp: new Date().toISOString(),
        sync_status: "pending",
        retry_count: 0,
        last_error: ""
      });
    }
    actions.push(...photos, ...audios);
    if (!drug && !photos.length && !audios.length) return;
    saveActions(actions);
    form.reset();
    setStatus(navigator.onLine ? "online" : "offline", navigator.onLine ? "Online - saved safely" : "Offline - saved safely");
  });
}
disableRequired();
renderPending();
setStatus(navigator.onLine ? "online" : "offline", navigator.onLine ? "Online" : "Offline - saving safely");
window.addEventListener("online", syncActions);
setInterval(syncActions, 30000);
