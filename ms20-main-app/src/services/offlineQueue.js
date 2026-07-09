const STORAGE_KEY = "ms20-main-app:offline-queue";

function safeStorage() {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      return window.localStorage;
    }
  } catch {
    return null;
  }
  return null;
}

export class OfflineQueue {
  constructor(storage = safeStorage()) {
    this.storage = storage;
    this.memory = [];
  }

  list() {
    if (!this.storage) return [...this.memory];
    try {
      return JSON.parse(this.storage.getItem(STORAGE_KEY) || "[]");
    } catch {
      return [];
    }
  }

  save(items) {
    if (!this.storage) {
      this.memory = [...items];
      return;
    }
    this.storage.setItem(STORAGE_KEY, JSON.stringify(items));
  }

  add(action) {
    const items = this.list();
    const existing = items.find((item) => item.id === action.id);
    if (existing) {
      return { added: false, duplicate: true, pending: items.length };
    }
    const queued = {
      ...action,
      queuedAt: new Date().toISOString(),
      status: "pending"
    };
    items.push(queued);
    this.save(items);
    return { added: true, duplicate: false, pending: items.length, action: queued };
  }

  update(id, patch) {
    const items = this.list().map((item) => (item.id === id ? { ...item, ...patch } : item));
    this.save(items);
    return items.find((item) => item.id === id);
  }

  clearSynced() {
    const items = this.list().filter((item) => item.status !== "synced");
    this.save(items);
    return items;
  }

  pendingCount() {
    return this.list().filter((item) => item.status === "pending").length;
  }
}
