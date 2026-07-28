# Invoice table OCR engineering memory

Canonical live-validation authority: `../../MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`. This memory supplies checkpoint evidence only.

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
- Catalog recovery lesson: persistence is not a satisfactory owner experience when refresh only restores chat messages. Render one reusable catalog workspace directly from the canonical Pharmacy Catalog, never from copied onboarding rows. Deduplicate during recovery, preserve identity fields such as strength, provide immediate post-save and home-screen access, search locally, and use progressive disclosure with responsive mobile/desktop layouts.

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

## Catalog access and safe editing

Pharmacy owners must not need to remember chat commands to view their medicines. Keep a permanent `SHOW ME` workspace action outside Operations Chat and load its contents only from the persisted Pharmacy Catalog. Catalog rows open Medicine Action Cards whose edits remain drafts until explicit approval. Discard leaves persisted data untouched; approval updates the existing canonical record, and an identity change that collides with another catalog medicine is blocked rather than silently merged. Browsing, search, review, validation, and ordinary edits stay deterministic, local, and zero-token.

## Centralized medicine recognition and section-based testing

Medicine recognition must be centralized, local-first, confidence-ranked, and tolerant of normal human input. A friction found with one medicine represents a behavior class. Fix the shared recognition engine once, protect it with broad regression tests, and avoid repeating equivalent live tests with many medicines. Catalog search, chat, onboarding/import, sales, restock, stock enquiry, and speech-recognized text must use the same normalizer and ranked resolver; ordinary recognition remains deterministic, offline-capable, and zero-token. High-confidence matches may be surfaced prominently, close alternatives remain an explicit ranked choice, and low-confidence input must not silently change a canonical record.

Permanent test method: test in sections with representative examples; identify and fix the shared root cause; preserve passing behavior; add reusable regression coverage; verify confidence with one or two live examples; close the behavior class; then move to a different test section. Do not repeat the same class without new regression evidence.

Dynamic result lists must rebind their interactive actions after replacing HTML. A visually correct result is not complete unless its primary action remains operable after search, filtering, rescanning, or any other partial rerender.

Interactive actions belong at the stable rendering lifecycle boundary. Prefer one delegated `data-action` listener on the application root so composer sheets, filtered lists, refreshed reviews, and future dynamic controls inherit behavior without screen-specific rebinding. Long cards must also inherit the same safe close action at both their top and bottom; navigation improvements are shared card behavior, not per-workflow decoration.

Creating a review is not enough if the owner cannot see it. After opening or creating a card, focus that exact card rather than scrolling to an unrelated end of a long conversation. Idempotently reuse an existing blank draft for the same workflow and consolidate empty duplicates on resume; repeated taps caused by uncertain feedback must never multiply pending work or make the app appear hung.

An empty input card is not durable pharmacy data. If the app resumes with abandoned empty Paste drafts, discard them all rather than preserving a blocker that the owner cannot distinguish from saved work. Render durable cards through an isolation boundary so one malformed draft produces a closable recovery card instead of preventing Operations, SHOW ME, or the rest of the pharmacy interface from opening. Never delete an entered draft or an approved catalog record through this recovery path.

When resume detects an unreadable non-empty card, move its raw payload to bounded local quarantine before removing it from the active render path. This preserves evidence for diagnosis without forcing the owner to repeatedly close broken cards. Shared bottom navigation controls should remain visually compact on phones: show only `x`, retain the descriptive close action in `aria-label`, and inherit the same safe dismissal behavior as the top control.

Capability migrations must replace every renderer reference atomically. Parser tests alone cannot protect an import workflow: exercise a complete realistic card through body rendering and action rendering, because a stale workflow-local variable can leave parsing correct while making the review card unreadable. CSV, bulk paste, and invoice reviews must all render their actions from the same CatalogImport capability policy.

Successful duplicate prevention still requires visible owner feedback. Show partition outcomes in the main shared card note rather than only in collapsed diagnostics: this includes an intentional no-op when every proposed medicine exists and a mixed review where existing medicines are excluded while new rows proceed. A safe result that is visually silent looks like a broken control or unexplained data loss. Keep raw import controls owner-facing and phone-readable: use canonical labels such as `Medicine list` and let long text inputs fill the card width.

A single-medicine review must prioritize action over form length. Use progressive disclosure ordered from rush-hour actions, to stock and medicine details, to traceability and secondary details. Keep every canonical field available, but put medicine, selling price, one sale-quantity state, payment, and the primary actions in the first phone view. Distinguish sale quantity from current stock in the schema and labels; never render two controls with the same `Quantity` meaning. Implement this once in the shared single-medicine detail renderer, while multi-row CSV, Paste List, and invoice tables retain their own review layout.
Progressive panels must also translate internal field keys into owner-facing language and avoid desktop resize affordances that appear as visual debris on phones.

### Catalog multi-term search intent

Catalog filtering must require every normalized query term to match the same saved medicine. An average fuzzy score can otherwise admit an unrelated medicine because it shares a generic form such as `syrup`. Keep this strict browse-search constraint separate from the general medicine matcher, whose ranked alternatives are still needed for safe sale and restock ambiguity handling.

Delimited onboarding must preserve every supported identity field across all transformation boundaries: header mapping, normalized row objects, intermediate serialization, editable review, approval, and persistence. A field parsed from the source is not protected if an intermediate row format or shared review-column definition omits it. Extend persisted positional formats compatibly so active older review cards remain readable.

Medicine-card improvements belong in one canonical medicine field schema and reusable context-aware field sets, not in individual screens. Onboarding reviews, invoice/photo/scan cards, sale-time learning, restock, and Pharmacy Catalog editing should inherit the same field identity, labels, optionality, normalization, and persistence rules while retaining context-specific fields. Strength and barcode must survive review, approval, merge, refresh, and later Medicine Action Card edits; sparse repeat evidence must not erase stronger saved values.

Reusable editable-medicine behavior must follow the same rule as shared fields. Before adding a control or interaction, decide whether it belongs to the shared editable-card or editable-list system. If it does, implement one canonical capability and renderer inherited by every applicable workflow, with focused regression protection. An exception is allowed only for a documented, tested context-specific reason. Multi-row catalog reviews therefore share row movement across invoice, CSV, bulk paste, and future compatible imports; an incomplete invoice remains the deliberate safety-blocked exception, and single-medicine cards never receive meaningless ordering controls.

Expiry is canonical medicine data, not free-form display text. Normalize supported month inputs to `YYYY-MM` at every review and persistence boundary, interpret a pharmaceutical expiry month as valid through its final day, and generate alerts from that canonical value only. Never pass localized text such as `Oct-28` directly to JavaScript date parsing. Long durable lists should reuse synchronized navigation controls at both natural entry points instead of forcing phone users to traverse the whole list to search again.
### Barcode acquisition boundary

- A barcode action must acquire evidence before creating a review card. Never route an acquisition control directly to an empty placeholder review.
- Barcode capture reuses the shared camera lifecycle, decodes locally when the browser supports `BarcodeDetector`, and matches only against the saved Pharmacy Catalog.
- If decoding is unavailable or unclear, keep the draft unsaved and offer honest manual barcode entry; do not invent a code or use an AI/API fallback.
- Before every onboarding test that depends on external material, Codex prepares and verifies a realistic controlled fixture first. This includes invoices/photos, CSV, Excel, paste lists, manual and sale-time learning prompts, barcodes, shelf photos, and future external-input workflows; the owner should not be asked to manufacture technical test data.
- Controlled barcode mappings remain isolated fixture data, must resolve through Source Brain, must avoid the known Pharmacy Catalog, and never promote a medicine until the owner approves the shared review card.
