const LEGACY_QUEUE_KEY = "pharmareen_phase6_offline_queue";
const LEGACY_HISTORY_KEY = "pharmareen_phase6_synced_history";
const DB_NAME = "pharmareen_phase6_offline_db";
const DB_VERSION = 1;
const QUEUE_STORE = "queue";
const HISTORY_STORE = "history";
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

let dbPromise = null;
let persistentStorageReady = false;

function loadJson(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); }
  catch { return fallback; }
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function supportsIndexedDb() {
  return typeof indexedDB !== "undefined";
}

function openDatabase() {
  if (!supportsIndexedDb()) return Promise.reject(new Error("IndexedDB is not available"));
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) db.createObjectStore(QUEUE_STORE, { keyPath: "id" });
      if (!db.objectStoreNames.contains(HISTORY_STORE)) db.createObjectStore(HISTORY_STORE, { keyPath: "id" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("IndexedDB open failed"));
  });
  return dbPromise;
}

async function idbRequest(storeName, mode, callback) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, mode);
    const store = transaction.objectStore(storeName);
    let request;
    try { request = callback(store); }
    catch (error) { reject(error); return; }
    transaction.oncomplete = () => resolve(request && "result" in request ? request.result : undefined);
    transaction.onerror = () => reject(transaction.error || new Error("IndexedDB transaction failed"));
    transaction.onabort = () => reject(transaction.error || new Error("IndexedDB transaction aborted"));
  });
}

async function idbGetAll(storeName) {
  return idbRequest(storeName, "readonly", store => store.getAll());
}

async function idbPut(storeName, value) {
  return idbRequest(storeName, "readwrite", store => store.put(value));
}

async function idbDelete(storeName, id) {
  return idbRequest(storeName, "readwrite", store => store.delete(id));
}

async function migrateLegacyQueue() {
  const legacyQueue = loadJson(LEGACY_QUEUE_KEY, []);
  const legacyHistory = loadJson(LEGACY_HISTORY_KEY, []);
  if (legacyQueue.length) {
    for (const entry of legacyQueue) await idbPut(QUEUE_STORE, entry);
    localStorage.removeItem(LEGACY_QUEUE_KEY);
  }
  if (legacyHistory.length) {
    for (const entry of legacyHistory) await idbPut(HISTORY_STORE, entry);
    localStorage.removeItem(LEGACY_HISTORY_KEY);
  }
}

async function initializeStorage() {
  if (!supportsIndexedDb()) {
    persistentStorageReady = false;
    return;
  }
  try {
    await openDatabase();
    persistentStorageReady = true;
    await migrateLegacyQueue();
  } catch (error) {
    persistentStorageReady = false;
    console.warn("IndexedDB unavailable, using localStorage fallback", error);
  }
}

function sortEntries(entries) {
  return entries.slice().sort((a, b) => String(a.timestamp || "").localeCompare(String(b.timestamp || "")));
}

async function loadQueue() {
  if (persistentStorageReady) return sortEntries(await idbGetAll(QUEUE_STORE));
  return loadJson(LEGACY_QUEUE_KEY, []);
}

async function loadHistory() {
  const history = persistentStorageReady ? await idbGetAll(HISTORY_STORE) : loadJson(LEGACY_HISTORY_KEY, []);
  return history.slice().sort((a, b) => String(b.synced_at || b.timestamp || "").localeCompare(String(a.synced_at || a.timestamp || "")));
}

async function addEntries(entries) {
  if (!entries.length) return;
  if (persistentStorageReady) {
    for (const entry of entries) await idbPut(QUEUE_STORE, entry);
    return;
  }
  const queue = loadJson(LEGACY_QUEUE_KEY, []);
  queue.push(...entries);
  saveJson(LEGACY_QUEUE_KEY, queue);
}

async function updateQueueEntry(entry) {
  if (persistentStorageReady) {
    await idbPut(QUEUE_STORE, entry);
    return;
  }
  const queue = loadJson(LEGACY_QUEUE_KEY, []);
  const index = queue.findIndex(item => item.id === entry.id);
  if (index >= 0) queue[index] = entry;
  else queue.push(entry);
  saveJson(LEGACY_QUEUE_KEY, queue);
}

async function deleteQueueEntry(id) {
  if (persistentStorageReady) {
    await idbDelete(QUEUE_STORE, id);
    return;
  }
  saveJson(LEGACY_QUEUE_KEY, loadJson(LEGACY_QUEUE_KEY, []).filter(item => item.id !== id));
}

async function addHistoryEntry(entry) {
  const historyEntry = { ...entry, synced_at: new Date().toISOString() };
  if (persistentStorageReady) {
    await idbPut(HISTORY_STORE, historyEntry);
    return;
  }
  const history = loadJson(LEGACY_HISTORY_KEY, []);
  history.unshift(historyEntry);
  saveJson(LEGACY_HISTORY_KEY, history.slice(0, 30));
}

function setStatus(state, text) {
  statusBanner.className = `status ${state}`;
  statusBanner.textContent = text;
}

function updateConnectionStatus() {
  if (navigator.onLine) setStatus("online", "Online");
  else setStatus("offline", "Offline - saved safely");
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("File could not be read"));
    reader.readAsDataURL(blob);
  });
}

function createCommandEntries(rawText) {
  return Parser.splitCommands(rawText).map(command => ({
    ...Parser.parseCommand(command),
    pharmacy_id: pharmacyId.value.trim()
  }));
}

async function queueMedia(file, kind, purpose, options = {}) {
  if (!file) return null;
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
    last_error: "",
    storage: persistentStorageReady ? "indexeddb" : "localstorage"
  };
  if (persistentStorageReady) entry.blob = file;
  else entry.data_url = await blobToDataUrl(file);

  try {
    await addEntries([entry]);
  } catch (error) {
    const fallback = { ...entry, blob: undefined, data_url: await blobToDataUrl(file), storage: "localstorage", session_note: "Photo saved for this session. Please keep this page open until synced." };
    await addEntries([fallback]);
  }
  if (!options.skipRender) await renderQueue();
  if (!options.skipSync && navigator.onLine) await syncQueue();
  return entry;
}

async function queuePhotoInputIfPresent(options = {}) {
  return queueMedia(photoInput.files && photoInput.files[0], "photo", photoPurpose.value, options);
}

async function queueAudioInputIfPresent(options = {}) {
  return queueMedia(voiceInput.files && voiceInput.files[0], "audio", "offline_voice_note", options);
}

async function saveOfflineEntries() {
  const textEntries = createCommandEntries(commandText.value);
  let savedCount = 0;
  if (textEntries.length) {
    await addEntries(textEntries);
    savedCount += textEntries.length;
  }
  const photoEntry = await queuePhotoInputIfPresent({ skipRender: true, skipSync: true });
  const audioEntry = await queueAudioInputIfPresent({ skipRender: true, skipSync: true });
  if (photoEntry) savedCount += 1;
  if (audioEntry) savedCount += 1;
  if (!savedCount) return;

  commandText.value = "";
  photoInput.value = "";
  voiceInput.value = "";
  await renderQueue();
  if (navigator.onLine) await syncQueue();
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
    const storage = item.type === "photo" || item.type === "audio" || item.type === "voice" ? ` · ${item.storage || "stored"}` : "";
    meta.textContent = `${item.type || item.action || "entry"} · ${status}${storage} · retries ${item.retry_count || 0}`;
    if (item.last_error) meta.textContent += ` · ${item.last_error}`;
    li.append(title, meta);
    target.appendChild(li);
  }
}

async function renderQueue() {
  const queue = await loadQueue();
  const pending = queue.filter(item => item.sync_status !== "synced");
  const history = await loadHistory();
  queueCount.textContent = String(pending.length);
  renderList(pendingEntries, pending.slice(-12).reverse(), "No pending entries.");
  renderList(syncedEntries, history.slice(0, 10), "No synced entries yet.");
}

async function entryForSync(item) {
  const copy = { ...item };
  if (copy.blob && !copy.data_url) copy.data_url = await blobToDataUrl(copy.blob);
  delete copy.blob;
  return copy;
}

async function mergeResults(queue, data) {
  const synced = new Map((data.synced || []).map(item => [item.id, item]));
  const failed = new Map((data.failed || []).map(item => [item.id, item]));
  const pending = new Map((data.pending || []).map(item => [item.id, item]));

  for (const item of queue) {
    if (synced.has(item.id)) {
      const result = synced.get(item.id);
      await deleteQueueEntry(item.id);
      await addHistoryEntry({ ...item, blob: undefined, sync_status: "synced", last_error: "", reply: result.reply || result.message || "Synced" });
      continue;
    }
    if (failed.has(item.id)) {
      const result = failed.get(item.id);
      await updateQueueEntry({ ...item, sync_status: "failed", retry_count: (item.retry_count || 0) + 1, last_error: result.error || "Sync failed" });
      continue;
    }
    if (pending.has(item.id)) {
      const result = pending.get(item.id);
      await updateQueueEntry({ ...item, sync_status: "pending", retry_count: (item.retry_count || 0) + 1, last_error: result.reason || result.error || "Needs attention" });
    }
  }
}

async function syncQueue() {
  if (!navigator.onLine) {
    setStatus("offline", "Offline - saved safely");
    return;
  }
  const queue = await loadQueue();
  const toSync = queue.filter(item => item.sync_status !== "synced" && (item.retry_count || 0) < MAX_RETRIES);
  if (!toSync.length) {
    setStatus("synced", "Synced");
    return;
  }
  setStatus("syncing", "Syncing...");
  try {
    const entries = [];
    for (const item of toSync) entries.push(await entryForSync(item));
    const response = await fetch("/offline/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries })
    });
    const data = await response.json();
    await mergeResults(toSync, data);
    await renderQueue();
    const failedCount = (data.failed || []).length + (data.pending || []).length;
    setStatus(failedCount ? "error" : "synced", failedCount ? "Needs attention" : "Synced");
  } catch (error) {
    for (const item of toSync) {
      await updateQueueEntry({ ...item, sync_status: "failed", retry_count: (item.retry_count || 0) + 1, last_error: String(error) });
    }
    await renderQueue();
    setStatus("error", "Needs attention");
  }
}

document.querySelectorAll("[data-action]").forEach(button => {
  button.addEventListener("click", () => {
    commandText.value = examples[button.dataset.action] || "Panadol sold 2";
    commandText.focus();
  });
});

document.getElementById("saveEntry").addEventListener("click", () => saveOfflineEntries());
document.getElementById("syncNow").addEventListener("click", () => syncQueue());
document.getElementById("queuePhoto").addEventListener("click", () => queuePhotoInputIfPresent());
document.getElementById("queueVoice").addEventListener("click", () => queueAudioInputIfPresent());
window.addEventListener("online", () => syncQueue());
window.addEventListener("offline", updateConnectionStatus);
setInterval(syncQueue, 30000);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/offline_app/service-worker.js").catch(() => {});
}

async function boot() {
  await initializeStorage();
  updateConnectionStatus();
  await renderQueue();
  if (navigator.onLine) await syncQueue();
}

window.PharMareenOffline = {
  addEntries,
  blobToDataUrl,
  createCommandEntries,
  entryForSync,
  initializeStorage,
  loadQueue,
  persistentStorageReady: () => persistentStorageReady,
  queueMedia,
  saveOfflineEntries,
  syncQueue
};

boot();
