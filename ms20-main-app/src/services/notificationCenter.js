const DEFAULT_MIN_STOCK = 5;
const DAY_MS = 24 * 60 * 60 * 1000;

export function buildDeterministicNotifications({ catalog = [], pendingCards = [], now = new Date(), catalogRequired = true } = {}) {
  const notifications = [];
  const catalogItems = Array.isArray(catalog) ? catalog : [];
  const cards = Array.isArray(pendingCards) ? pendingCards : [];

  if (catalogRequired && catalogItems.length === 0) {
    notifications.push(createNotification({
      category: "Learning",
      key: "catalog-empty",
      title: "Medicine catalog needed",
      message: "Add medicines by invoice, scan, paste, or CSV before daily sales.",
      action: "Open onboarding"
    }));
  }

  for (const item of catalogItems) {
    const name = item.name || item.medicine || "Medicine";
    const stock = numberOrNull(item.stockLeft ?? item.stock ?? item.current_stock);
    if (stock !== null && stock <= 0) {
      notifications.push(createNotification({
        category: "Inventory",
        key: `out-${normalize(name)}`,
        title: `${name} is out of stock`,
        message: "Prepare an order or correct stock if the count is wrong.",
        action: "Review stock"
      }));
    } else if (stock !== null && stock <= DEFAULT_MIN_STOCK) {
      notifications.push(createNotification({
        category: "Inventory",
        key: `low-${normalize(name)}`,
        title: `${name} is low`,
        message: `${name} has ${stock} left. Prepare a restock if needed.`,
        action: "Prepare order"
      }));
    }

    for (const expiryRecord of expiryRecords(item)) {
      const expiry = parseDate(expiryRecord.expiry || expiryRecord.expiry_date || item.expiry);
      if (!expiry) continue;
      const days = Math.ceil((expiry.getTime() - now.getTime()) / DAY_MS);
      const band = expiryBand(days);
      if (!band) continue;
      notifications.push(createNotification({
        category: "Expiry",
        key: `expiry-${normalize(name)}-${expiry.toISOString().slice(0, 10)}-${band}`,
        title: expiryTitle(name, days),
        message: expiryRecord.batch
          ? `Batch ${expiryRecord.batch} expires on ${expiry.toISOString().slice(0, 10)}.`
          : `${name} expires on ${expiry.toISOString().slice(0, 10)}.`,
        action: "Review expiry"
      }));
    }
  }

  for (const card of cards) {
    if (card.type === "InvoiceCard" || card.type === "PhotoReviewCard" || card.type === "VisualScanCard") {
      notifications.push(createNotification({
        category: "System",
        key: `pending-${card.id}`,
        title: "Scan needs review",
        message: `${card.title || "A scan"} is waiting for approval.`,
        action: "Open review"
      }));
    }
    if (card.type === "CatalogImportCard") {
      notifications.push(createNotification({
        category: "Learning",
        key: `import-${card.id}`,
        title: "Medicine import needs approval",
        message: "A medicine list is ready to check and save.",
        action: "Review import"
      }));
    }
  }

  return dedupeNotifications(notifications);
}

export function mergeNotifications(existing = [], generated = []) {
  const byId = new Map();
  for (const item of existing) byId.set(item.id, item);
  const merged = [];
  for (const item of generated) {
    const previous = byId.get(item.id);
    merged.push({
      ...item,
      createdAt: previous?.createdAt || item.createdAt,
      status: previous?.status || "unread",
      completedAt: previous?.completedAt
    });
  }
  return merged.sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
}

export function notificationToCard(notification) {
  return {
    id: `card-notification-${notification.id}`,
    type: "NotificationCard",
    title: notification.title,
    source: "Digital Operations Assistant",
    confidence: 0.95,
    status: notification.status === "unread" ? "ready" : "reviewed",
    aiRequired: false,
    fields: {
      category: notification.category,
      message: notification.message,
      action: notification.action,
      status: notification.status || "unread"
    },
    validation: "Generated locally from pharmacy records."
  };
}

function createNotification({ category, key, title, message, action }) {
  return {
    id: `${category.toLowerCase()}-${key}`,
    category,
    title,
    message,
    action,
    status: "unread",
    createdAt: new Date().toISOString(),
    aiUsed: false
  };
}

function dedupeNotifications(items) {
  return [...new Map(items.map((item) => [item.id, item])).values()];
}

function expiryRecords(item) {
  const records = Array.isArray(item.batches) ? item.batches : [];
  if (item.expiry && records.length === 0) return [{ expiry: item.expiry, batch: item.batch || "" }];
  return records;
}

function expiryBand(days) {
  if (days < 0) return "expired";
  if (days <= 7) return "7";
  if (days <= 30) return "30";
  if (days <= 60) return "60";
  if (days <= 90) return "90";
  return "";
}

function expiryTitle(name, days) {
  if (days < 0) return `${name} has expired`;
  if (days === 0) return `${name} expires today`;
  return `${name} expires in ${days} day(s)`;
}

function parseDate(value) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function numberOrNull(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "string" && value.trim() === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function normalize(value) {
  return String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
