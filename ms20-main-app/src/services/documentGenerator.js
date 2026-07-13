const CSV_HEADERS = [
  "medicine",
  "strength",
  "form",
  "unit",
  "selling_price",
  "cost_price",
  "stock",
  "supplier",
  "barcode",
  "batch",
  "expiry",
  "shelf"
];

export function buildCatalogCsv(items = []) {
  const rows = items.map((item) => {
    const firstBatch = Array.isArray(item.batches) ? item.batches[0] || {} : {};
    return [
      item.name || item.medicine || "",
      item.strength || "",
      first(item.forms) || item.form || "",
      first(item.units) || item.unit || "",
      item.sellingPrice ?? item.selling_price ?? "",
      item.costPrice ?? item.cost_price ?? "",
      item.stockLeft ?? item.stock ?? item.current_stock ?? "",
      item.supplier || firstBatch.supplier || "",
      item.barcode || "",
      firstBatch.batch || item.batch || "",
      firstBatch.expiry || item.expiry || "",
      item.shelf || item.location || ""
    ];
  });
  return [CSV_HEADERS, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
}

export function buildBulkPasteTemplate() {
  return [
    "MS2.0 BULK PASTE TEMPLATE",
    "Enter one medicine per line.",
    "Format: medicine name form selling price",
    "Remove these instructions before pasting your medicine lines."
  ].join("\n");
}

export function buildDocumentCard({ title, document, format, itemCount = 0, status = "ready" }) {
  return {
    id: `card-document-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    type: "DocumentExportCard",
    title,
    source: "MS2.0 documents",
    confidence: 0.94,
    status,
    aiRequired: false,
    fields: {
      document,
      format,
      items: String(itemCount),
      status: "Ready to download"
    },
    validation: "Generated locally from stored pharmacy records."
  };
}

export function downloadTextFile({ filename, contents, mime = "text/plain;charset=utf-8" }) {
  const blob = new Blob([contents], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function first(values = []) {
  return Array.isArray(values) ? values[0] || "" : "";
}
