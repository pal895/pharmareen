const DB_KEY = "pharmareen_phase6_offline_queue";
const HISTORY_KEY = "pharmareen_phase6_synced_history";
const MAX_RETRIES = 3;
const Parser = window.PharMareenOfflineParser;

const examples = {
  sale: "Panadol sold 2",
  restock: "Panadol +20",
  bonus: "Panadol restock 20 bonus 5 cost 2000",
  discount: "Amoxicillin received 30 paid 2500 discount 300"
};

const statusBanner = document.getElementById("statusBanner");
const commandText = document.getElementById("commandText");
const pharmacyId = document.getElementById("pharmacyId");
const queueCount = document.getElementById("queueCount");
const pendingEntries = document.getElementById("pendingEntries");
const syncedEntries = document.getElementById("syncedEntries");
const emptyTemplate = document.getElementById("emptyTemplate");
const photoInput = document.getElementById("photoInput");
const photoPurpose = document.getElementById("photoPurpose");
const voiceInput = document.getElementById("voiceInput");

function loadJson(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); }
  catch { return fallback; }
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function loadQueue() {
  return loadJson(DB_KEY, []);
}

function saveQueue(queue) {
  saveJson(DB_KEY, queue);
  renderQueue();
}

function loadHistory() {
  return loadJson(HISTORY_KEY, []);
}

function saveHistory(history) {
  saveJson(HISTORY_KEY, history.slice(0, 30));
}

function setStatus(state, text) {
  statusBanner.className = `status ${state}`;
  statusBanner.textContent = text;
}

function updateConnectionStatus() {
  if (navigator.onLine) setStatus("online", "Online");
  else setStatus("offline", "Offline - saved safely");
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("File could not be read"));
    reader.readAsDataURL(file);
  });
}

function createCommandEntries(rawText) {
  return Parser.splitCommands(rawText).map(command => ({
    ...Parser.parseCommand(command),
    pharmacy_id: pharmacyId.value.trim()
  }));
}

function saveTextEntries() {
  const commands = createCommandEntries(commandText.value);
  if (!commands.length) return;
  const queue = loadQueue();
  queue.push(...commands);
  saveQueue(queue);
  commandText.value = "";
  if (navigator.onLine) syncQueue();
  else setStatus("offline", "Offline - saved safely");
}

async function queueMedia(file, kind, purpose) {
  if (!file) return;
  const entry = {
    id: `${kind}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    timestamp: new Date().toISOString(),
    pharmacy_id: pharmacyId.value.trim(),
    action: kind,
    type: kind,
    raw_text: `${kind}: ${file.name}`,
    command_text: "",
    file_name: file.name,
    file_type: file.type || (kind === "photo" ? "image/*" : "audio/*"),
    size: file.size,
    purpose,
    sync_status: "pending",
    retry_count: 0,
    last_error: ""
  };
  try {
    entry.data_url = await fileToDataUrl(file);
  } catch {
    entry.session_note = "Photo saved for this session. Please keep this page open until synced.";
  }
  const queue = loadQueue();
  queue.push(entry);
  saveQueue(queue);
  if (navigator.onLine) syncQueue();
  else setStatus("offline", "Offline - saved safely");
}

function entryLabel(item) {
  if (item.type === "photo") return `Photo: ${item.file_name || "invoice"}`;
  if (item.type === "voice" || item.type === "audio") return `Voice/audio: ${item.file_name || "audio"}`;
  if (item.action === "restock") {
    const bonus = Number(item.bonus_quantity || 0) > 0 ? ` + bonus ${item.bonus_quantity}` : "";
    return `${item.drug_name || item.command_text} restock ${item.quantity || ""}${bonus}`.trim();
  }
  if (item.action === "sale") return `${item.drug_name || item.command_text} sold ${item.quantity || ""}`.trim();
  return item.command_text || item.raw_text || "Unknown entry";
}

function renderList(target, items, emptyText) {
  target.innerHTML = "";
  if (!items.length) {
    const clone = emptyTemplate.content.cloneNode(true);
    clone.querySelector("li").textContent = emptyText;
    target.appendChild(clone);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    const title = document.createElement("div");
    title.textContent = entryLabel(item);
    const meta = document.createElement("div");
    meta.className = "entry-meta";
    const status = item.sync_status || "pending";
    meta.textContent = `${item.type || item.action || "entry"} · ${status} · retries ${item.retry_count || 0}`;
    if (item.last_error) meta.textContent += ` · ${item.last_error}`;
    li.append(title, meta);
    target.appendChild(li);
  }
}

function renderQueue() {
  const queue = loadQueue();
  const pending = queue.filter(item => item.sync_status !== "synced");
  const history = loadHistory();
  queueCount.textContent = String(pending.length);
  renderList(pendingEntries, pending.slice(-12).reverse(), "No pending entries.");
  renderList(syncedEntries, history.slice(0, 10), "No synced entries yet.");
}

function mergeResults(queue, data) {
  const synced = new Map((data.synced || []).map(item => [item.id, item]));
  const failed = new Map((data.failed || []).map(item => [item.id, item]));
  const pending = new Map((data.pending || []).map(item => [item.id, item]));
  const history = loadHistory();
  const nextQueue = [];

  for (const item of queue) {
    if (synced.has(item.id)) {
      const result = synced.get(item.id);
      history.unshift({ ...item, sync_status: "synced", last_error: "", reply: result.reply || result.message || "Synced" });
      continue;
    }
    if (failed.has(item.id)) {
      const result = failed.get(item.id);
      nextQueue.push({ ...item, sync_status: "failed", retry_count: (item.retry_count || 0) + 1, last_error: result.error || "Sync failed" });
      continue;
    }
    if (pending.has(item.id)) {
      const result = pending.get(item.id);
      nextQueue.push({ ...item, sync_status: "pending", retry_count: (item.retry_count || 0) + 1, last_error: result.reason || result.error || "Needs attention" });
      continue;
    }
    nextQueue.push(item);
  }

  saveHistory(history);
  return nextQueue;
}

async function syncQueue() {
  if (!navigator.onLine) {
    setStatus("offline", "Offline - saved safely");
    return;
  }
  const queue = loadQueue();
  const toSync = queue.filter(item => item.sync_status !== "synced" && (item.retry_count || 0) < MAX_RETRIES);
  if (!toSync.length) {
    setStatus("synced", "Synced");
    return;
  }
  setStatus("syncing", "Syncing...");
  try {
    const response = await fetch("/offline/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries: toSync })
    });
    const data = await response.json();
    const updated = mergeResults(queue, data);
    saveQueue(updated);
    const failedCount = (data.failed || []).length + (data.pending || []).length;
    setStatus(failedCount ? "error" : "synced", failedCount ? "Needs attention" : "Synced");
  } catch (error) {
    const updated = queue.map(item => item.sync_status === "synced" ? item : {
      ...item,
      sync_status: "failed",
      retry_count: (item.retry_count || 0) + 1,
      last_error: String(error)
    });
    saveQueue(updated);
    setStatus("error", "Needs attention");
  }
}

document.querySelectorAll("[data-action]").forEach(button => {
  button.addEventListener("click", () => {
    commandText.value = examples[button.dataset.action] || "Panadol sold 2";
    commandText.focus();
  });
});

document.getElementById("saveEntry").addEventListener("click", saveTextEntries);
document.getElementById("syncNow").addEventListener("click", syncQueue);
document.getElementById("queuePhoto").addEventListener("click", () => queueMedia(photoInput.files[0], "photo", photoPurpose.value));
document.getElementById("queueVoice").addEventListener("click", () => queueMedia(voiceInput.files[0], "voice", "offline_voice_note"));
window.addEventListener("online", syncQueue);
window.addEventListener("offline", updateConnectionStatus);
setInterval(syncQueue, 30000);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/offline_app/service-worker.js").catch(() => {});
}

updateConnectionStatus();
renderQueue();
if (navigator.onLine) syncQueue();

window.PharMareenOffline = { createCommandEntries, syncQueue, loadQueue };
