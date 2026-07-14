export function catalogReviewCapabilities(card) {
  const isCatalogReview = card?.type === "CatalogImportCard" && card.fields?.entry_mode !== "paste_input";
  const safetyBlocked = card?.fields?.import_mode === "invoice_ocr" && card.fields?.import_incomplete === "true";
  return {
    editingAllowed: isCatalogReview,
    reorderable: isCatalogReview && !safetyBlocked,
    addRowAllowed: isCatalogReview && !safetyBlocked,
    approvalAllowed: isCatalogReview && !safetyBlocked,
    correctionAllowed: isCatalogReview
  };
}

export function reorderedCatalogRows(rows, rowIndex, direction) {
  const next = rows.map((row) => ({ ...row }));
  const from = Number(rowIndex);
  const to = from + Number(direction);
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0 || from >= next.length || to >= next.length) return next;
  [next[from], next[to]] = [next[to], next[from]];
  return next;
}
