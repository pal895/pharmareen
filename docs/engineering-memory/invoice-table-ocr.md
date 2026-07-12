# Invoice table OCR engineering memory

## Reusable diagnosis

Whole-page OCR text lines are not reliable table rows. Tesseract can recognize every cell but assign adjacent cells to different lines, reorder numeric columns, or omit one row from the linear text result. Repeated regular-expression and per-field merge changes cannot solve missing line structure.

## Preferred local-first method

1. Keep multiple deterministic preprocessing and page-segmentation passes.
2. Use trusted medicine identity only to locate candidate medicine-row anchors.
3. Read OCR word coordinates and rebuild each row from words in the same horizontal band.
4. Parse the reconstructed row through the shared medicine resolver.
5. Require quantity × unit cost = line total.
6. Require extracted line totals to equal the detected invoice total.
7. Merge only compatible complete candidates; never combine unrelated numeric fields independently.
8. If required cells remain missing, block approval and show a plain retry action.
9. Always return structured JSON and never expose OCR/parser internals to the owner.

This method is supplier-agnostic, offline, zero-token, and reusable for invoices, delivery notes, stock-count sheets, and other ruled medicine tables.

## Follow-up lessons from live phone scans

- Preserve the vertical order of coordinate-reconstructed medicine anchors; dictionary or confidence ordering must not reorder the owner’s document.
- Rightmost cells can sit slightly above or below the medicine baseline. Use a bounded row band wide enough to include them but narrower than the distance to the next medicine row.
- Reconstruct document-level header and footer lines from word coordinates too; supplier, invoice date, and total can be lost by normal OCR line grouping.
- Normalize ambiguous batch characters only from a pattern established by multiple batches on the same invoice. Never apply a global `O`/`0` guess.
