# Invoice table OCR engineering memory

## Test 1 accepted baseline (2026-07-13)

- The AfyaLink first supplier-invoice onboarding test passed end to end: four medicines, no unclear lines, approval, catalog save, export confirmation, and final Saved message.
- Preserve strongest-evidence merging, medicine-scoped evidence, total consistency, editable correction, and manual row-order controls as the regression baseline.
- Test 2 is the required final consistency invoice. Its asset is `ms20-main-app/fixtures/test-2-dawa-bora-invoice.png`, backed by a verified manifest and new Source Brain medicines excluded from Zuri Pharmacy's 13-item catalog.
- Test 2's first two landscape phone captures found no rows. The reusable cause was layout diversity: strength, pack-size, and selling-price columns make numeric token order unsafe, and a single dense-block OCR segmentation can miss wide sparse tables. Preserve more landscape resolution, retry sparse segmentation only when row anchors are absent, and parse named columns by x-position.
- A sideways browser camera capture may rotate the visible preview without writing EXIF orientation into its canvas JPEG. If normal and sparse OCR find no medicine anchors, retry the local coordinate pass at 90, 270, then 180 degrees and stop at the first anchored orientation. Keep these extra passes out of the successful fast path.
- Named geometry is authoritative for quantity, buying price, optional selling price, and line total. Do not let arithmetic select a different role combination merely because extra numeric columns form another valid equation. Missing geometry stays missing and blocks approval.
- Canceling a review card is a UI action, not permission to forget strong recognition evidence. Retain a small local invoice-memory ledger so a weaker rescan cannot replace a stronger earlier read. Optional selling price should be reviewed and saved when present but must not become an approval requirement when absent.
- Derive header, row, and order text from the selected coordinate pass instead of running a redundant whole-page text OCR pass. Camera frames already prepared at the capture limit should be uploaded directly without a second canvas decode/re-encode.
- If a geometry row is incomplete or its buying price is not below an observed selling price, run one alternate high-contrast binary coordinate pass. Prefer an arithmetic-valid complete row with a positive selling margin, and use the other pass only to fill nonnumeric blanks such as batch. Do not pay for this pass on already coherent rows.
- Full-page preprocessing variants can repeat the same digit confusion. For an incomplete batch or an arithmetic-valid but margin-suspicious row, crop only the named cells from the established table geometry, enlarge locally, and use field-specific OCR character sets. Accept numeric replacements only when quantity x buying price equals line total and an observed selling price remains above buying price. This is faster and safer than another whole-page pass.
- Editable review truth must update immediately after owner corrections and again after reload. Incomplete copy must say values may be missing or incorrect and require checking every field against the invoice; arithmetic consistency enables approval but is not a claim that OCR values match the source.
- Keep Scan again available on complete reviews, but tell owners to stop repeated scans when results differ and edit against the source. Once an owner-edited review is complete and total-consistent, treat those rows as stronger than later OCR so a rescan cannot undo verified corrections.
- Test 2 passed through the intended safety model: local OCR supplied an editable draft, the owner corrected remaining uncertainty against the invoice, approval stayed blocked until completeness and arithmetic passed, and only then did the catalog change. External Android CSV viewer compatibility is separate from export generation; validate file contents in the dedicated export-integrity test.
- Export lesson: a valid CSV and a professional owner-facing document are different products. Keep CSV machine-readable and test it with spreadsheet software; design Excel, PDF, and Word outputs for their purpose at the scheduled document stage. Prepare and verify Source Brain-backed fixtures before every remaining onboarding test, and keep discounts and bonus quantities deterministic, explicit, reviewed, and separately represented in canonical records.
- Onboarding fixture lesson: verify fixtures through the same local parser before live use. Form normalization must preserve supported compound forms such as `eye drops`; singularize only when the singular value is itself a supported form, never by removing a trailing `s` indiscriminately.
- Paste onboarding lesson: preparing a fixture is insufficient unless the live entry route consumes owner input. Opening Paste list must start with an empty textarea, never silently preload example/catalog medicines. Parse only after an explicit Review list action, separate already-cataloged medicines from genuinely new rows, and require approval only for the reviewed new rows. Downloadable templates contain format instructions, not pharmacy data.

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

Independent batch voting is insufficient when a displaced batch has accumulated on the wrong medicine. Solve batch selection across the whole invoice: choose at most one batch per medicine and one medicine per batch while maximizing medicine-scoped observation support. For source order, allow a newest scan with one arithmetic-valid row per medicine and a line-total sum equal to the invoice total to override stale position votes; incomplete scans continue using accumulated position evidence.

Do not use isolated Tesseract token coordinates as the final order source on phone captures: coordinate groups can be unstable and rotate an otherwise correct table. Prefer medicine occurrence order from the primary whole-page OCR pass when it recognizes every extracted medicine. Use bounded medicine geometry only when the primary ordered text is incomplete. Ordering logic must never rewrite row values.

OCR review must have an exit from uncertainty. Preserve a canonical card's valid nonblank value when a new scan is blank, expose mobile row up/down controls, and recompute the completeness/approval gate immediately after every field edit or row move. Once the owner corrects a complete canonical review, preserve that verified order on matching rescans instead of allowing a weaker new scan to reorder it.
