export function createCatalogWorkspaceCard(itemCount = 0) {
  return {
    id: "card-pharmacy-catalog",
    type: "CatalogWorkspaceCard",
    title: "Pharmacy catalog",
    source: "Pharmacy Catalog",
    confidence: 1,
    status: "ready",
    aiRequired: false,
    fields: { item_count: String(itemCount), query: "" },
    validation: "Loaded directly from the saved Pharmacy Catalog. No medicines are recreated by this view."
  };
}

export function catalogWorkspaceItems(catalog = [], query = "") {
  const unique = new Map();
  for (const item of catalog) {
    const key = normalize(item.name || item.medicine);
    if (key && !unique.has(key)) unique.set(key, item);
  }
  const wanted = normalize(query);
  return [...unique.values()]
    .filter((item) => !wanted || searchableText(item).includes(wanted))
    .sort((left, right) => String(left.name || left.medicine).localeCompare(String(right.name || right.medicine)));
}

function searchableText(item) {
  return [
    item.name,
    item.medicine,
    item.strength,
    item.form,
    ...(item.forms || []),
    item.unit,
    ...(item.units || []),
    item.supplier,
    item.barcode,
    item.shelf
  ].map(normalize).join(" ");
}

function normalize(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}
