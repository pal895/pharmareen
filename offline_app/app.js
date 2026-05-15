const LEGACY_QUEUE_KEY = "pharmareen_phase6_offline_queue";
const LEGACY_HISTORY_KEY = "pharmareen_phase6_synced_history";
const DB_NAME = "pharmareen_phase6_offline_db";
const DB_VERSION = 1;
const QUEUE_STORE = "queue";
const HISTORY_STORE = "history";
const MAX_RETRIES = 3;
const Parser = window.PharMareenOfflineParser;
const SERVICE_WORKER_VERSION = "phase6-sync-trust-v12";

const examples = {
  sale: "Panadol sold 2",
  restock: "Panadol +20",
  nostock: "Insulin no stock",
  report: "report today",
  stock: "Panadol stock"
};

const statusBanner = document.getElementById("statusBanner");
const commandText = document.getElementById("commandText");
const pharmacyId = document.getElementById("pharmacyId");
const queueCount = document.getElementById("queueCount");
const pendingEntries = document.getElementById("pendingEntries");
const syncedEntries = document.getElementById("syncedEntries");
const emptyTemplate = document.getElementById("emptyTemplate");
const photoInput = document.getElementById("photoInput");
const cameraPhotoInput = document.getElementById("cameraPhotoInput");
const photoPurpose = document.getElementById("photoPurpose");
const voiceInput = document.getElementById("voiceInput");
const barcodeInput = document.getElementById("barcodeInput");
const barcodeMedicineName = document.getElementById("barcodeMedicineName");
const barcodeResult = document.getElementById("barcodeResult");
const lastScanned = document.getElementById("lastScanned");
const barcodeCameraBox = document.getElementById("barcodeCameraBox");
const barcodeVideo = document.getElementById("barcodeVideo");
const torchToggle = document.getElementById("torchToggle");
const voiceStatus = document.getElementById("voiceStatus");

let dbPromise = null;
let persistentStorageReady = false;
let barcodeStream = null;
let barcodeScanTimer = null;
let barcodeTorchEnabled = false;
let currentBarcodeMedicine = "";
let mediaRecorder = null;
let recordedChunks = [];

function loadJson(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); }
  catch { return fallback; }
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function barcodeMap() {
  return loadJson("pharmareen_barcode_map", {});
}

function saveBarcodeMap(map) {
  saveJson("pharmareen_barcode_map", map);
}

function lookupBarcode(code) {
  const clean = String(code || "").trim();
  if (!clean) return null;
  return barcodeMap()[clean] || null;
}

function updateBarcodeResult() {
  if (!barcodeInput || !barcodeResult) return;
  const code = barcodeInput.value.trim();
  if (!code) {
    barcodeResult.textContent = "Barcode not scanned yet.";
    return;
  }
  const medicine = lookupBarcode(code);
  if (medicine) {
    currentBarcodeMedicine = medicine;
    barcodeResult.textContent = `✅ ${medicine} detected`;
    if (lastScanned) lastScanned.textContent = `Last scanned: ${medicine}`;
    return;
  }
  currentBarcodeMedicine = "";
  barcodeResult.textContent = "Barcode not found. What is the medicine name?";
}

async function saveBarcodeMapping() {
  if (!barcodeInput || !barcodeMedicineName || !barcodeResult) return;
  const code = barcodeInput.value.trim();
  const medicine = barcodeMedicineName.value.trim();
  if (!code || !medicine) {
    barcodeResult.textContent = "Enter barcode and medicine name first.";
    return;
  }
  const map = barcodeMap();
  map[code] = medicine;
  saveBarcodeMap(map);
  currentBarcodeMedicine = medicine;
  barcodeResult.textContent = `✅ ${medicine} saved for this barcode`;
  if (lastScanned) lastScanned.textContent = `Last scanned: ${medicine}`;
  await addEntries([{
    id: `barcode-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    timestamp: new Date().toISOString(),
    pharmacy_id: pharmacyId.value.trim(),
    action: "barcode_mapping",
    type: "barcode_mapping",
    barcode: code,
    drug_name: medicine,
    raw_text: `barcode ${code} ${medicine}`,
    command_text: "",
    sync_status: "pending",
    retry_count: 0,
    last_error: ""
  }]);
  await renderQueue();
}

async function stopBarcodeScanner() {
  if (barcodeScanTimer) {
    clearInterval(barcodeScanTimer);
    barcodeScanTimer = null;
  }
  if (barcodeStream) {
    barcodeStream.getTracks().forEach(track => track.stop());
    barcodeStream = null;
  }
  if (barcodeVideo) barcodeVideo.srcObject = null;
  if (barcodeCameraBox) barcodeCameraBox.hidden = true;
  if (torchToggle) torchToggle.hidden = true;
}

async function toggleTorch() {
  if (!barcodeStream) return;
  const track = barcodeStream.getVideoTracks()[0];
  if (!track || !track.getCapabilities) return;
  const capabilities = track.getCapabilities();
  if (!capabilities.torch) return;
  barcodeTorchEnabled = !barcodeTorchEnabled;
  await track.applyConstraints({ advanced: [{ torch: barcodeTorchEnabled }] });
  torchToggle.textContent = barcodeTorchEnabled ? "Flashlight Off" : "Flashlight";
}

async function startBarcodeScanner() {
  if (!navigator.mediaDevices || !window.BarcodeDetector) {
    barcodeResult.textContent = "Camera scan is not available here. Type or scan the barcode below.";
    barcodeInput.focus();
    return;
  }
  await stopBarcodeScanner();
  try {
    barcodeStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: "environment" },
        focusMode: { ideal: "continuous" },
        width: { ideal: 1280 },
        height: { ideal: 720 }
      },
      audio: false
    });
    barcodeVideo.srcObject = barcodeStream;
    barcodeCameraBox.hidden = false;
    await barcodeVideo.play();
    const track = barcodeStream.getVideoTracks()[0];
    const capabilities = track && track.getCapabilities ? track.getCapabilities() : {};
    if (capabilities.torch) torchToggle.hidden = false;
    if (track && track.applyConstraints) {
      try { await track.applyConstraints({ advanced: [{ focusMode: "continuous" }] }); } catch {}
    }
    const detector = new BarcodeDetector({ formats: ["ean_13", "ean_8", "code_128", "upc_a", "upc_e"] });
    barcodeScanTimer = setInterval(async () => {
      try {
        const codes = await detector.detect(barcodeVideo);
        if (!codes.length) return;
        barcodeInput.value = codes[0].rawValue || "";
        updateBarcodeResult();
        gentleFeedback();
        await stopBarcodeScanner();
      } catch {
        // Keep camera open while scanning is available.
      }
    }, 500);
  } catch {
    barcodeResult.textContent = "Camera could not open. Type or scan the barcode below.";
    barcodeInput.focus();
  }
}

function barcodeAction(action) {
  const medicine = currentBarcodeMedicine || lookupBarcode(barcodeInput.value);
  if (!medicine) {
    barcodeResult.textContent = "Scan or save the barcode first.";
    return;
  }
  if (action === "stock") {
    commandText.value = `${medicine} stock`;
    commandText.focus();
    return;
  }
  const quantity = prompt(action === "sale" ? `How many ${medicine} were sold?` : `How many ${medicine} came in?`);
  if (!quantity) return;
  commandText.value = action === "sale" ? `${medicine} ${quantity}` : `${medicine} restock ${quantity}`;
  commandText.focus();
}


function disableNativeRequiredValidation() {
  document.querySelectorAll("[required]").forEach(element => {
    element.required = false;
    element.removeAttribute("required");
  });
  document.querySelectorAll("form").forEach(form => { form.noValidate = true; });
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
    console.warn("Persistent offline storage unavailable, using browser backup storage", error);
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
  const { blob, data_url, ...safeEntry } = entry;
  const historyEntry = { ...safeEntry, synced_at: new Date().toISOString() };
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
  const syncButton = document.getElementById("syncNow");
  if (navigator.onLine) {
    setStatus("online", "Online");
    if (syncButton) {
      syncButton.disabled = false;
      syncButton.title = "";
    }
  } else {
    setStatus("offline", "Offline - saved safely");
    if (syncButton) {
      syncButton.disabled = true;
      syncButton.title = "Records are saved safely and will send when internet returns.";
    }
  }
}

function gentleFeedback() {
  if (navigator.vibrate) navigator.vibrate(80);
}

function formatEntryTime(value) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("File could not be read"));
    reader.readAsDataURL(blob);
  });
}

async function storageHasRoom(file) {
  if (!navigator.storage || !navigator.storage.estimate) return true;
  try {
    const estimate = await navigator.storage.estimate();
    const free = Number(estimate.quota || 0) - Number(estimate.usage || 0);
    return free <= 0 || free > file.size * 2;
  } catch {
    return true;
  }
}

async function compressPhoto(file) {
  if (!file || !String(file.type || "").startsWith("image/")) return file;
  if (file.size < 700000) return file;
  try {
    const image = await createImageBitmap(file);
    const maxSide = 1400;
    const scale = Math.min(1, maxSide / Math.max(image.width, image.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.width * scale));
    canvas.height = Math.max(1, Math.round(image.height * scale));
    const context = canvas.getContext("2d");
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.72));
    if (!blob) return file;
    return typeof File !== "undefined"
      ? new File([blob], (file.name || "photo").replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" })
      : Object.assign(blob, { name: "photo.jpg", type: "image/jpeg" });
  } catch {
    return file;
  }
}

function createCommandEntries(rawText) {
  return Parser.splitCommands(rawText).map(command => ({
    ...Parser.parseCommand(command),
    pharmacy_id: pharmacyId.value.trim()
  }));
}

async function queueMedia(file, kind, purpose, options = {}) {
  if (!file) return null;
  const originalSignature = mediaSignature(file, kind);
  let storedFile = file;
  if (kind === "photo") storedFile = await compressPhoto(file);
  if (!(await storageHasRoom(storedFile))) {
    setStatus("error", "Phone storage is low. Please sync or free space.");
    return null;
  }
  const entry = {
    id: `${kind}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    timestamp: new Date().toISOString(),
    pharmacy_id: pharmacyId.value.trim(),
    action: kind,
    type: kind,
    raw_text: kind === "photo" ? "photo saved offline" : "voice note saved offline",
    command_text: "",
    file_name: storedFile.name || (kind === "photo" ? "photo" : "voice note"),
    file_type: storedFile.type || (kind === "photo" ? "image/*" : "audio/*"),
    size: storedFile.size,
    purpose,
    sync_status: "pending",
    retry_count: 0,
    last_error: "",
    storage: persistentStorageReady ? "indexeddb" : "localstorage",
    file_signature: originalSignature
  };
  if (persistentStorageReady) entry.blob = storedFile;
  else entry.data_url = await blobToDataUrl(storedFile);

  try {
    await addEntries([entry]);
  } catch (error) {
    const fallback = { ...entry, blob: undefined, data_url: await blobToDataUrl(storedFile), storage: "localstorage", session_note: "Saved for this session. Please keep this page open until synced." };
    await addEntries([fallback]);
  }
  if (!options.skipRender) await renderQueue();
  return entry;
}

function mediaSignature(file, kind) {
  return [
    kind,
    file && file.name ? file.name : "unnamed",
    file && file.size ? file.size : 0,
    file && file.lastModified ? file.lastModified : 0,
    file && file.type ? file.type : ""
  ].join("|");
}

async function queueMediaFiles(fileList, kind, purpose, options = {}) {
  const files = Array.from(fileList || []);
  const queued = [];
  const existing = await loadQueue();
  const seen = new Set(existing.map(item => item.file_signature).filter(Boolean));
  for (const file of files) {
    const signature = mediaSignature(file, kind);
    if (seen.has(signature)) continue;
    seen.add(signature);
    const entry = await queueMedia(file, kind, purpose, { ...options, skipRender: true });
    if (entry) queued.push(entry);
  }
  if (!options.skipRender) await renderQueue();
  return queued;
}

async function queuePhotoInputIfPresent(options = {}) {
  const chosen = await queueMediaFiles(photoInput.files, "photo", photoPurpose.value, { ...options, skipRender: true });
  const captured = await queueMediaFiles(cameraPhotoInput ? cameraPhotoInput.files : [], "photo", photoPurpose.value, { ...options, skipRender: true });
  if (!options.skipRender) {
    photoInput.value = "";
    if (cameraPhotoInput) cameraPhotoInput.value = "";
  }
  if (!options.skipRender) await renderQueue();
  return [...chosen, ...captured];
}

async function queueAudioInputIfPresent(options = {}) {
  const queued = await queueMediaFiles(voiceInput.files, "audio", "offline_voice_note", options);
  if (!options.skipRender) voiceInput.value = "";
  return queued;
}

async function stopVoiceRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
}

async function startVoiceRecording() {
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    voiceStatus.textContent = "Recording is not available here. Use More options to choose an audio file.";
    voiceInput.click();
    return;
  }
  if (mediaRecorder && mediaRecorder.state === "recording") {
    await stopVoiceRecording();
    return;
  }
  try {
    recordedChunks = [];
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = event => {
      if (event.data && event.data.size > 0) recordedChunks.push(event.data);
    };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(track => track.stop());
      const type = recordedChunks[0] ? recordedChunks[0].type || "audio/webm" : "audio/webm";
      const blob = new Blob(recordedChunks, { type });
      const fileName = `voice-note-${Date.now()}.webm`;
      const file = typeof File !== "undefined" ? new File([blob], fileName, { type }) : Object.assign(blob, { name: fileName });
      await queueMedia(file, "audio", "tap_talk_voice");
      voiceStatus.textContent = "Voice saved. It will send when online.";
      const button = document.getElementById("tapTalk");
      if (button) button.textContent = "Tap & Talk";
    };
    mediaRecorder.start();
    voiceStatus.textContent = "Recording... tap again to save.";
    const button = document.getElementById("tapTalk");
    if (button) button.textContent = "Save Voice";
  } catch {
    voiceStatus.textContent = "Recording could not start. Use More options to choose an audio file.";
    voiceInput.click();
  }
}

async function saveOfflineEntries() {
  const textEntries = createCommandEntries(commandText.value);
  let savedCount = 0;
  if (textEntries.length) {
    await addEntries(textEntries);
    savedCount += textEntries.length;
  }
  const photoEntries = await queuePhotoInputIfPresent({ skipRender: true });
  const audioEntries = await queueAudioInputIfPresent({ skipRender: true });
  savedCount += photoEntries.length;
  savedCount += audioEntries.length;
  if (!savedCount) return;

  commandText.value = "";
  photoInput.value = "";
  if (cameraPhotoInput) cameraPhotoInput.value = "";
  voiceInput.value = "";
  await renderQueue();
  if (audioEntries.length) voiceStatus.textContent = "Voice saved. It will send when online.";
  if (navigator.onLine) setStatus("online", "Saved safely");
  else setStatus("offline", "Offline - saved safely");
}

function mediaStatusLabel(item) {
  const status = item.sync_status || "pending";
  if (status === "syncing") return "🔄 Syncing";
  if (status === "synced") return "✅ Synced";
  if (status === "failed") return "❌ Failed";
  return "⏳ Waiting";
}

function entryLabel(item) {
  if (item.type === "photo") return `${item.sync_status === "synced" ? "✅ Photo synced" : "📷 Photo"}\n${mediaStatusLabel(item)}`;
  if (item.type === "voice" || item.type === "audio") return `${item.sync_status === "synced" ? "✅ Voice synced" : "🎤 Voice note"}\n${mediaStatusLabel(item)}`;
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
    const kind = item.type === "photo" ? "Photo" : (item.type === "audio" || item.type === "voice" ? "Voice" : "Entry");
    const time = formatEntryTime(item.synced_at || item.timestamp);
    meta.textContent = `${kind}${time ? ` - ${time}` : ""}`;
    const friendlyError = friendlySyncError(item.last_error);
    if (friendlyError) meta.textContent += ` - ${friendlyError}`;
    li.append(title, meta);
    target.appendChild(li);
  }
}

function friendlySyncError(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (/indexeddb|retry|blob|base64|payload|typeerror/i.test(text)) return "Needs attention";
  return text.length > 80 ? "Needs attention" : text;
}

async function renderQueue() {
  const queue = await loadQueue();
  const pending = queue.filter(item => item.sync_status !== "synced");
  const history = await loadHistory();
  queueCount.textContent = String(pending.length);
  renderList(pendingEntries, pending.slice(-12).reverse(), "Nothing saved offline yet.");
  renderList(syncedEntries, history.slice(0, 10), "Nothing sent yet.");
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
      await addHistoryEntry({ ...item, blob: undefined, sync_status: "synced", last_error: "", reply: result.reply || result.message || "Sent successfully" });
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
    setStatus("synced", "✅ Synced");
    return;
  }
  setStatus("syncing", "🔄 Syncing");
  try {
    const entries = [];
    for (const item of toSync) {
      await updateQueueEntry({ ...item, sync_status: "syncing" });
      entries.push(await entryForSync(item));
    }
    await renderQueue();
    const response = await fetch("/offline/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries })
    });
    const data = await response.json();
    await mergeResults(toSync, data);
    await renderQueue();
    const failedCount = (data.failed || []).length + (data.pending || []).length;
    setStatus(failedCount ? "error" : "synced", failedCount ? "❌ Needs attention" : (data.message || "✅ Synced"));
    if (!failedCount) gentleFeedback();
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

document.getElementById("takePhoto").addEventListener("click", () => (cameraPhotoInput || photoInput).click());
document.getElementById("scanBarcode").addEventListener("click", () => startBarcodeScanner());
document.getElementById("scanInvoice").addEventListener("click", () => photoInput.click());
document.getElementById("voiceEntry").addEventListener("click", () => startVoiceRecording());
document.getElementById("tapTalk").addEventListener("click", () => startVoiceRecording());
document.getElementById("manualEntry").addEventListener("click", () => commandText.focus());
document.getElementById("saveBarcodeMapping").addEventListener("click", saveBarcodeMapping);
document.getElementById("barcodeSell").addEventListener("click", () => barcodeAction("sale"));
document.getElementById("barcodeRestock").addEventListener("click", () => barcodeAction("restock"));
document.getElementById("barcodeCheck").addEventListener("click", () => barcodeAction("stock"));
document.getElementById("stopBarcodeScan").addEventListener("click", () => stopBarcodeScanner());
document.getElementById("torchToggle").addEventListener("click", () => toggleTorch());
barcodeInput.addEventListener("input", updateBarcodeResult);
document.getElementById("saveEntry").addEventListener("click", () => saveOfflineEntries());
document.getElementById("syncNow").addEventListener("click", () => syncQueue());
document.getElementById("queuePhoto").addEventListener("click", () => queuePhotoInputIfPresent());
document.getElementById("queueVoice").addEventListener("click", () => queueAudioInputIfPresent());
window.addEventListener("online", () => syncQueue());
window.addEventListener("offline", updateConnectionStatus);
setInterval(syncQueue, 30000);

async function registerFreshServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  try {
    const registrations = await navigator.serviceWorker.getRegistrations();
    for (const registration of registrations) {
      const urls = [registration.active, registration.waiting, registration.installing]
        .filter(Boolean)
        .map(worker => worker.scriptURL || "");
      const hasOldOfflineWorker = urls.some(url => url.includes("/offline_app/service-worker.js") && !url.includes(SERVICE_WORKER_VERSION));
      if (hasOldOfflineWorker) await registration.unregister();
    }
    await navigator.serviceWorker.register(`/offline_app/service-worker.js?v=${SERVICE_WORKER_VERSION}`);
  } catch {
    // The app still works online if service worker refresh is unavailable.
  }
}

async function boot() {
  disableNativeRequiredValidation();
  await initializeStorage();
  updateConnectionStatus();
  await renderQueue();
  await registerFreshServiceWorker();
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
  queueMediaFiles,
  saveOfflineEntries,
  syncQueue
};

boot();
