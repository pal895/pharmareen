const LEGACY_QUEUE_KEY = "pharmareen_phase6_offline_queue";
const LEGACY_HISTORY_KEY = "pharmareen_phase6_synced_history";
const PAYMENT_MODE_KEY = "pharmareen_payment_mode";
const SHORTCUTS_KEY = "pharmareen_medicine_shortcuts";
const SHORTCUT_USAGE_KEY = "pharmareen_medicine_shortcut_usage";
const DB_NAME = "pharmareen_phase6_offline_db";
const DB_VERSION = 1;
const QUEUE_STORE = "queue";
const HISTORY_STORE = "history";
const MAX_RETRIES = 3;
const Parser = window.PharMareenOfflineParser;
const SERVICE_WORKER_VERSION = "phase6-smooth-test-v15";
const DEFAULT_MEDICINE_SHORTCUTS = ["Panadol", "Amox", "Piriton", "ORS"];

const examples = {
  sale: "Panadol sold 2",
  "cash-sale": "Panadol 2",
  "mpesa-sale": "Panadol 2",
  "credit-sale": "Panadol 2",
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
const paymentModeLabel = document.getElementById("paymentModeLabel");
const medicineGrid = document.getElementById("medicineGrid");

let dbPromise = null;
let persistentStorageReady = false;
let barcodeStream = null;
let barcodeScanTimer = null;
let barcodeTorchEnabled = false;
let currentBarcodeMedicine = "";
let mediaRecorder = null;
let recordedChunks = [];
let currentPaymentMode = localStorage.getItem(PAYMENT_MODE_KEY) || "Cash";
let lastBarcodeScan = { code: "", at: 0 };
let pendingBarcodeScan = { code: "", count: 0, at: 0 };

function loadJson(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); }
  catch { return fallback; }
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function loadMedicineShortcuts() {
  const saved = loadJson(SHORTCUTS_KEY, DEFAULT_MEDICINE_SHORTCUTS);
  const list = Array.isArray(saved) && saved.length ? saved : DEFAULT_MEDICINE_SHORTCUTS;
  const usage = loadJson(SHORTCUT_USAGE_KEY, {});
  return list
    .map(name => String(name || "").trim())
    .filter(Boolean)
    .slice(0, 6)
    .sort((a, b) => Number(usage[b] || 0) - Number(usage[a] || 0));
}

function saveMedicineShortcuts(list) {
  saveJson(SHORTCUTS_KEY, list.map(name => String(name || "").trim()).filter(Boolean).slice(0, 6));
}

function recordMedicineUse(name) {
  const clean = String(name || "").trim();
  if (!clean) return;
  const usage = loadJson(SHORTCUT_USAGE_KEY, {});
  usage[clean] = Number(usage[clean] || 0) + 1;
  saveJson(SHORTCUT_USAGE_KEY, usage);
}

function editMedicineShortcut(index) {
  const shortcuts = loadMedicineShortcuts();
  const current = shortcuts[index] || "";
  const next = prompt("Which medicine should appear here?", current);
  if (next === null) return;
  shortcuts[index] = next.trim();
  saveMedicineShortcuts(shortcuts);
  renderMedicineShortcuts();
}

function renderMedicineShortcuts() {
  if (!medicineGrid) return;
  medicineGrid.innerHTML = "";
  loadMedicineShortcuts().forEach((medicine, index) => {
    const card = document.createElement("article");
    card.className = "medicine-card";
    card.dataset.medicine = medicine;
    const title = document.createElement("strong");
    title.textContent = medicine;
    const actions = document.createElement("div");
    for (const [label, action] of [["+1", "+1"], ["+2", "+2"], ["Stock", "stock"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.medicine = medicine;
      button.dataset.medicineAction = action;
      button.textContent = label;
      actions.appendChild(button);
    }
    const edit = document.createElement("button");
    edit.className = "edit-shortcut";
    edit.type = "button";
    edit.dataset.shortcutIndex = String(index);
    edit.textContent = "Edit";
    card.append(title, actions, edit);
    medicineGrid.appendChild(card);
  });
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
  pendingBarcodeScan = { code: "", count: 0, at: 0 };
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
        const rawValue = codes[0].rawValue || "";
        const now = Date.now();
        if (!rawValue) return;
        if (rawValue !== pendingBarcodeScan.code || now - pendingBarcodeScan.at > 2500) {
          pendingBarcodeScan = { code: rawValue, count: 1, at: now };
          barcodeResult.textContent = "Confirming barcode...";
          return;
        }
        pendingBarcodeScan = { code: rawValue, count: pendingBarcodeScan.count + 1, at: now };
        if (pendingBarcodeScan.count < 2) {
          barcodeResult.textContent = "Confirming barcode...";
          return;
        }
        if (rawValue && rawValue === lastBarcodeScan.code && now - lastBarcodeScan.at < 2500) return;
        lastBarcodeScan = { code: rawValue, at: now };
        barcodeInput.value = rawValue;
        updateBarcodeResult();
        if (!currentBarcodeMedicine) barcodeResult.textContent = `✅ Barcode detected: ${rawValue}`;
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
    setStatus("offline", "📡 Offline mode active — saving safely");
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
  return Parser.splitCommands(rawText).map(command => {
    const entry = {
      ...applyPaymentMode(Parser.parseCommand(command)),
      pharmacy_id: pharmacyId.value.trim()
    };
    if (entry.drug_name) recordMedicineUse(entry.drug_name);
    return entry;
  });
}

function applyPaymentMode(entry) {
  if (!entry || entry.action !== "sale") return entry;
  if (entry.payment_method) return entry;
  if (!["Cash", "M-Pesa", "Credit"].includes(currentPaymentMode)) return entry;
  return { ...entry, payment_method: currentPaymentMode };
}

function setPaymentMode(mode) {
  currentPaymentMode = mode || "Cash";
  localStorage.setItem(PAYMENT_MODE_KEY, currentPaymentMode);
  if (paymentModeLabel) paymentModeLabel.textContent = `🟢 ${currentPaymentMode} mode active`;
  document.querySelectorAll("[data-payment-mode]").forEach(button => {
    button.classList.toggle("active-mode", button.dataset.paymentMode === currentPaymentMode);
  });
}

function appendCommandLine(line) {
  const current = commandText.value.trim();
  commandText.value = current ? `${current}\n${line}` : line;
  commandText.focus();
}

function quickMedicineAction(medicine, action) {
  if (!medicine) return;
  recordMedicineUse(medicine);
  if (action === "stock") appendCommandLine(`${medicine} stock`);
  else appendCommandLine(`${medicine} ${action.replace("+", "")}`);
  renderMedicineShortcuts();
}

function mediaDisplayPrefix(kind, purpose) {
  if (kind === "audio" || kind === "voice") return "Voice note";
  if (purpose === "stock_photo") return "Shelf photo";
  return "Invoice photo";
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
    raw_text: kind === "photo" ? "photo saved safely" : "voice note saved safely",
    command_text: "",
    file_name: storedFile.name || (kind === "photo" ? "photo" : "voice note"),
    file_type: storedFile.type || (kind === "photo" ? "image/*" : "audio/*"),
    size: storedFile.size,
    purpose,
    sync_status: "pending",
    retry_count: 0,
    last_error: "",
    storage: persistentStorageReady ? "indexeddb" : "localstorage",
    file_signature: originalSignature,
    display_label: options.displayLabel || mediaDisplayPrefix(kind, purpose)
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
  let nextNumber = existing.filter(item => item.type === kind || item.action === kind).length + 1;
  for (const file of files) {
    const signature = mediaSignature(file, kind);
    if (seen.has(signature)) continue;
    seen.add(signature);
    const displayLabel = `${mediaDisplayPrefix(kind, purpose)} ${nextNumber++}`;
    const entry = await queueMedia(file, kind, purpose, { ...options, displayLabel, skipRender: true });
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
      voiceStatus.textContent = "🎤 Voice note saved safely";
      const button = document.getElementById("tapTalk");
      if (button) button.textContent = "Tap & Talk";
    };
    mediaRecorder.start();
    voiceStatus.textContent = "Recording... tap again to save.";
    const button = document.getElementById("tapTalk");
    if (button) button.textContent = "Save Voice";
  } catch {
    voiceStatus.textContent = "Please allow microphone to use Tap & Talk.";
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
  renderMedicineShortcuts();
  await renderQueue();
  if (audioEntries.length) voiceStatus.textContent = "🎤 Voice note saved safely";
  if (photoEntries.length && !textEntries.length && !audioEntries.length) {
    setStatus(navigator.onLine ? "online" : "offline", `📷 ${photoEntries.length} photos saved safely`);
  } else if (navigator.onLine) setStatus("online", "✅ Saved safely");
  else setStatus("offline", "📡 Offline mode active — saving safely");
}

function mediaStatusLabel(item) {
  const status = item.sync_status || "pending";
  if (status === "syncing") return "🔄 Syncing";
  if (status === "synced") return "✅ Synced";
  if (status === "failed") return "⚠️ Needs attention";
  return "⏳ Waiting";
}

function entryLabel(item) {
  if (item.type === "photo") {
    const label = item.display_label || mediaDisplayPrefix("photo", item.purpose);
    return `${item.sync_status === "synced" ? "✅" : "📷"} ${label}\n${mediaStatusLabel(item)}`;
  }
  if (item.type === "voice" || item.type === "audio") {
    return `${item.sync_status === "synced" ? "✅ Voice synced safely" : "🎤 Voice note saved safely"}\n${mediaStatusLabel(item)}`;
  }
  if (item.action === "restock") {
    const bonus = Number(item.bonus_quantity || 0) > 0 ? ` + bonus ${item.bonus_quantity}` : "";
    return `${item.drug_name || item.command_text} restock ${item.quantity || ""}${bonus}`.trim();
  }
  if (item.action === "sale") {
    const payment = item.payment_method ? ` ${item.payment_method}` : "";
    return `${item.drug_name || item.command_text} sold ${item.quantity || ""}${payment}`.trim();
  }
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
    setStatus("offline", "📡 Offline mode active — saving safely");
    return;
  }
  const queue = await loadQueue();
  const toSync = queue.filter(item => item.sync_status !== "synced" && (item.retry_count || 0) < MAX_RETRIES);
  if (!toSync.length) {
    setStatus("synced", "✅ Everything synced safely");
    return;
  }
  setStatus("syncing", `🔄 Syncing 1 of ${toSync.length}`);
  try {
    const entries = [];
    for (const [index, item] of toSync.entries()) {
      setStatus("syncing", `🔄 Syncing ${index + 1} of ${toSync.length}`);
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
    setStatus(failedCount ? "error" : "synced", failedCount ? "⚠️ Needs attention" : `✅ ${toSync.length} records synced safely`);
    if (!failedCount) gentleFeedback();
  } catch (error) {
    for (const item of toSync) {
      await updateQueueEntry({ ...item, sync_status: "failed", retry_count: (item.retry_count || 0) + 1, last_error: String(error) });
    }
    await renderQueue();
    setStatus("error", "⚠️ Needs attention");
  }
}

document.querySelectorAll("[data-action]").forEach(button => {
  button.addEventListener("click", () => {
    if (button.dataset.action === "cash-sale") setPaymentMode("Cash");
    if (button.dataset.action === "mpesa-sale") setPaymentMode("M-Pesa");
    if (button.dataset.action === "credit-sale") setPaymentMode("Credit");
    commandText.value = examples[button.dataset.action] || "Panadol sold 2";
    commandText.focus();
  });
});

document.querySelectorAll("[data-payment-mode]").forEach(button => {
  button.addEventListener("click", () => setPaymentMode(button.dataset.paymentMode));
});

if (medicineGrid) {
  medicineGrid.addEventListener("click", event => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.shortcutIndex !== undefined) {
      editMedicineShortcut(Number(target.dataset.shortcutIndex));
      return;
    }
    if (target.dataset.medicineAction) quickMedicineAction(target.dataset.medicine, target.dataset.medicineAction);
  });
  medicineGrid.addEventListener("contextmenu", event => {
    const card = event.target instanceof HTMLElement ? event.target.closest(".medicine-card") : null;
    if (!card) return;
    event.preventDefault();
    editMedicineShortcut(Array.from(medicineGrid.querySelectorAll(".medicine-card")).indexOf(card));
  });
}

function disableBriefly(button, replacementText) {
  if (!button) return;
  const originalText = button.textContent;
  button.disabled = true;
  if (replacementText) button.textContent = replacementText;
  setTimeout(() => {
    button.disabled = false;
    button.textContent = originalText;
  }, 1200);
}

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
document.getElementById("queuePhoto").addEventListener("click", async event => {
  const button = event.currentTarget;
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Saving...";
  try {
    const queued = await queuePhotoInputIfPresent();
    if (queued.length) setStatus(navigator.onLine ? "online" : "offline", `📷 ${queued.length} photos saved safely`);
    else setStatus(navigator.onLine ? "online" : "offline", "✅ Already saved safely");
  } finally {
    setTimeout(() => {
      button.disabled = false;
      button.textContent = originalText;
    }, 1200);
  }
});
document.getElementById("queueVoice").addEventListener("click", async event => {
  const button = event.currentTarget;
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Saving...";
  try {
    const queued = await queueAudioInputIfPresent();
    if (queued.length) {
      voiceStatus.textContent = "🎤 Voice note saved safely";
      setStatus(navigator.onLine ? "online" : "offline", `🎤 ${queued.length} voice notes saved safely`);
    } else {
      setStatus(navigator.onLine ? "online" : "offline", "✅ Already saved safely");
    }
  } finally {
    setTimeout(() => {
      button.disabled = false;
      button.textContent = originalText;
    }, 1200);
  }
});
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
  setPaymentMode(currentPaymentMode);
  renderMedicineShortcuts();
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
