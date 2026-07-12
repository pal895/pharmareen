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
- Do not widen the shared row band to recover right-edge cells if stable numeric extraction regresses. Preserve the working row parser and assign expiry/batch tokens separately to the nearest medicine within midpoint row boundaries.
- Derive display order from coordinate anchors, but do not prioritize a less-complete geometry candidate over stronger OCR candidates merely to obtain that order. Sort the final merged rows afterward.
- When cells span several baselines, reconstruct within midpoint boundaries between adjacent medicine anchors. This captures the whole visual row without crossing into its neighbor.
- Join OCR tokens split around hyphens before parsing batches and expiries. Read invoice totals from all digits following the label, then restore printed decimal places.
- Avoid paying for duplicate OCR representations. One layout text pass plus one coordinate-data pass is sufficient; derive bounded rows and document lines from the coordinate pass.
- A missing form or unit may be filled only when the observed counterpart maps to exactly one trusted form–unit pair for that canonical medicine.
- Accept compact OCR expiries such as `202806` as `2028-06` only when the final two digits form a valid month. Recover invoice numbers from strict multi-segment alphanumeric identifiers rather than loose label text.
- Repeated captures of the same invoice are complementary evidence, not replacements. Match by invoice number or supplier/date/total signature, fill only blank fields from stronger prior local reviews, preserve current valid values, then rerun every required-field, row-arithmetic, and invoice-total check before enabling approval.
- The merge must include the union of medicine identities across scans, not only rows present in the newest capture. When several arithmetic-consistent versions compete, select one version per medicine whose combined line totals equal the invoice total; use completeness only as a tie-breaker.
- Metadata fallback must search every matching saved review for the first strong nonblank value. Never let the newest card’s blank total prevent total-based evidence selection.
- Keep one canonical active review card per invoice identity. Merge all matching evidence first, prefer stable remembered metadata over a corrupted reread, choose ordering from the strongest total-consistent review, then remove superseded duplicate cards so active-card limits cannot evict the best evidence.
# Canonical review evidence must remain medicine-scoped

When repeated scans are consolidated into one editable invoice card, never fill a missing field from the first non-empty row version. That can attach another scan's displaced batch, expiry, form, or unit to an otherwise arithmetically valid medicine row. Persist a compact evidence ledger inside the canonical review, keyed by normalized medicine identity and source position. Prefer a field only when its observation count is uniquely strongest; on a tie, leave it blank and keep approval blocked. Select quantity, unit cost, and line total as an atomic arithmetic-valid row, and learn source order by repeated positional votes. This is reusable for arbitrary suppliers and avoids fixture-specific corrections.

Resolve tied evidence only with invoice-wide invariants. A batch observed more strongly for another medicine must not be borrowed by the current row, and an incoming stock expiry earlier than the invoice month is invalid evidence. These constraints recover trustworthy alternatives while preserving the safety rule that unresolved ties remain blank.
