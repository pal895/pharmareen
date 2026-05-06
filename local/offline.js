const DB_KEY = "pharmareen_offline_actions";
const statusEl = document.getElementById("status");
const form = document.getElementById("actionForm");
const pendingList = document.getElementById("pendingList");

function loadActions() {
  return JSON.parse(localStorage.getItem(DB_KEY) || "[]");
}

function saveActions(actions) {
  localStorage.setItem(DB_KEY, JSON.stringify(actions));
  renderPending();
}

function setStatus(state, text) {
  statusEl.className = `banner ${state}`;
  statusEl.textContent = text;
}

function updateOnlineStatus() {
  setStatus(navigator.onLine ? "online" : "offline", navigator.onLine ? "Synced" : "Offline - saving safely");
}

function renderPending() {
  const actions = loadActions();
  pendingList.innerHTML = actions.map(action => `<li>${action.action_type}: ${action.drug_name} x${action.quantity} - ${action.sync_status}</li>`).join("");
}

form.addEventListener("submit", event => {
  event.preventDefault();
  const actions = loadActions();
  actions.push({
    action_id: `offline-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    action_type: document.getElementById("action_type").value,
    drug_name: document.getElementById("drug_name").value.trim(),
    quantity: Number(document.getElementById("quantity").value || 1),
    unit: document.getElementById("unit").value.trim(),
    expiry_date: document.getElementById("expiry_date").value.trim(),
    notes: document.getElementById("notes").value.trim(),
    created_by: "offline_app",
    created_at: new Date().toISOString(),
    sync_status: "pending",
    retry_count: 0,
    last_error: "",
    source: "offline_app"
  });
  saveActions(actions);
  form.reset();
  updateOnlineStatus();
});

async function syncActions() {
  if (!navigator.onLine) {
    setStatus("offline", "Offline - saving safely");
    return;
  }
  const actions = loadActions();
  const pending = actions.filter(action => action.sync_status !== "synced" && action.retry_count < 10);
  if (!pending.length) {
    setStatus("online", "Synced");
    return;
  }
  setStatus("syncing", "Syncing...");
  try {
    const response = await fetch("/sync/offline-actions", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({actions: pending})
    });
    const data = await response.json();
    const byId = new Map((data.results || []).map(result => [result.action_id, result]));
    const updated = actions.map(action => {
      const result = byId.get(action.action_id);
      if (!result) return action;
      if (result.status === "synced" || result.status === "already_synced") {
        return {...action, sync_status: "synced", last_error: ""};
      }
      return {...action, sync_status: "failed", retry_count: (action.retry_count || 0) + 1, last_error: result.error || "Sync failed"};
    });
    saveActions(updated);
    setStatus(updated.some(action => action.sync_status === "failed") ? "error" : "online", updated.some(action => action.sync_status === "failed") ? "Some items not synced yet" : "Synced");
  } catch (error) {
    const updated = actions.map(action => action.sync_status === "synced" ? action : {...action, retry_count: (action.retry_count || 0) + 1, last_error: String(error)});
    saveActions(updated);
    setStatus("error", "Some items not synced yet");
  }
}

document.getElementById("syncNow").addEventListener("click", syncActions);
window.addEventListener("online", syncActions);
window.addEventListener("offline", updateOnlineStatus);
setInterval(syncActions, 30000);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/offline_app/service-worker.js");
updateOnlineStatus();
renderPending();
