const DB_KEY = "pharmareen_phase6_offline_queue";
const MAX_RETRIES = 10;
const examples = {
  sale: "Panadol sold 2",
  restock: "Panadol restock 20",
  bonus: "Panadol restock 20 bonus 5",
  discount: "Amoxicillin received 30 paid 2500 discount 300"
};

const statusBanner = document.getElementById("statusBanner");
const commandText = document.getElementById("commandText");
const pharmacyId = document.getElementById("pharmacyId");
const queueCount = document.getElementById("queueCount");
const recentEntries = document.getElementById("recentEntries");
const emptyTemplate = document.getElementById("emptyTemplate");

function loadQueue() {
  try { return JSON.parse(localStorage.getItem(DB_KEY) || "[]"); }
  catch { return []; }
}

function saveQueue(queue) {
  localStorage.setItem(DB_KEY, JSON.stringify(queue));
  renderQueue();
}

function detectType(text) {
  const value = text.toLowerCase();
  if (value.includes("bonus") || value.includes("free") || value.includes("plus")) return "bonus_restock";
  if (value.includes("discount") || value.includes("paid") || value.includes("cost")) return "discount_restock";
  if (value.includes("restock") || value.includes("received") || value.includes("+")) return "restock";
  return "sale";
}

function setStatus(state, text) {
  statusBanner.className = `status ${state}`;
  statusBanner.textContent = text;
}

function updateConnectionStatus() {
  if (navigator.onLine) setStatus("online", "Online");
  else setStatus("offline", "Offline — saving safely");
}

function pendingItems(queue = loadQueue()) {
  return queue.filter(item => item.sync_status !== "synced");
}

function renderQueue() {
  const queue = loadQueue();
  const pending = pendingItems(queue);
  queueCount.textContent = String(pending.length);
  recentEntries.innerHTML = "";
  const latest = queue.slice(-8).reverse();
  if (!latest.length) {
    recentEntries.appendChild(emptyTemplate.content.cloneNode(true));
    return;
  }
  for (const item of latest) {
    const li = document.createElement("li");
    const title = document.createElement("div");
    title.textContent = item.command_text;
    const meta = document.createElement("div");
    meta.className = "entry-meta";
    meta.textContent = `${item.type} · ${item.sync_status} · retries ${item.retry_count || 0}`;
    if (item.last_error) meta.textContent += ` · ${item.last_error}`;
    li.append(title, meta);
    recentEntries.appendChild(li);
  }
}

function createEntry(command) {
  return {
    id: `offline-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    timestamp: new Date().toISOString(),
    pharmacy_id: pharmacyId.value.trim(),
    command_text: command,
    type: detectType(command),
    sync_status: "pending",
    retry_count: 0,
    last_error: ""
  };
}

function saveEntry() {
  const command = commandText.value.trim();
  if (!command) return;
  const queue = loadQueue();
  queue.push(createEntry(command));
  saveQueue(queue);
  commandText.value = "";
  if (navigator.onLine) syncQueue();
  else setStatus("offline", "Offline — saving safely");
}

async function syncQueue() {
  if (!navigator.onLine) {
    setStatus("offline", "Offline — saving safely");
    return;
  }
  const queue = loadQueue();
  const pending = queue.filter(item => item.sync_status !== "synced" && (item.retry_count || 0) < MAX_RETRIES);
  if (!pending.length) {
    setStatus("synced", "Synced");
    return;
  }
  setStatus("syncing", "Syncing");
  try {
    const response = await fetch("/offline/sync", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({entries: pending})
    });
    const data = await response.json();
    const synced = new Map((data.synced || []).map(item => [item.id, item]));
    const failed = new Map((data.failed || []).map(item => [item.id, item]));
    const updated = queue.map(item => {
      if (synced.has(item.id)) return {...item, sync_status: "synced", last_error: ""};
      if (failed.has(item.id)) {
        const failure = failed.get(item.id);
        return {...item, sync_status: "failed", retry_count: (item.retry_count || 0) + 1, last_error: failure.error || "Sync failed"};
      }
      return item;
    });
    saveQueue(updated);
    setStatus(failed.size ? "error" : "synced", failed.size ? "Some items not synced yet" : "Synced");
  } catch (error) {
    const updated = queue.map(item => item.sync_status === "synced" ? item : {
      ...item,
      sync_status: "failed",
      retry_count: (item.retry_count || 0) + 1,
      last_error: String(error)
    });
    saveQueue(updated);
    setStatus("error", "Some items not synced yet");
  }
}

document.querySelectorAll("[data-action]").forEach(button => {
  button.addEventListener("click", () => {
    commandText.value = examples[button.dataset.action] || "Panadol sold 2";
    commandText.focus();
  });
});

document.getElementById("saveEntry").addEventListener("click", saveEntry);
document.getElementById("syncNow").addEventListener("click", syncQueue);
window.addEventListener("online", syncQueue);
window.addEventListener("offline", updateConnectionStatus);
setInterval(syncQueue, 30000);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/offline_app/service-worker.js").catch(() => {});
}

updateConnectionStatus();
renderQueue();
if (navigator.onLine) syncQueue();
