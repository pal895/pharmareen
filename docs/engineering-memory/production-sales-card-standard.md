# Production Sales Card Standard and Recovery Audit

Authority date: 2026-07-29
Owner state: **IMPLEMENTED — AWAITING OWNER LIVE TEST; NOT APPROVED; NOT PROTECTED**

This is the reconciled engineering standard for the one shared MS2.0 Production Sales Card. It draws from `README.md`, `current-live-validation-state.md` (especially the approved improvement at line 468), `launch-readiness-roadmap.md`, `MS2.0_MASTER_LIVE_TEST_SEQUENCE.md` MS2-LT-049, `ms20-main-app/LIVE_APP_TEST_PLAN.md` lines 817–823, `CURRENT_ARCHITECTURE_SNAPSHOT.md`, `SALE_LIVE_TEST_FIXTURE_STANDARD.md`, and protected editable-card/voice-viewport evidence.

## Recovered requirement reconciliation

| Approved requirement | Source authority | Recovery state | Root |
|---|---|---|---|
| One shared Production `SaleCard` for typed, voice, compact commands, review, correction, payments and recovery | Project README; architecture snapshot; fixture standard | Implemented | `productionSaleCard.js`; `productionSaleCardBody` |
| Deterministic parser separates medicine, optional/default quantity and payment; compact commands supported | Protected voice-sale evidence; deterministic-first policy; owner recovery instruction | Implemented after failed `paracetamol cash` evidence | `parseSaleFacts` in `localIntelligence.js` |
| A payment word or quantity must never enter medicine identity | Medicine matcher and cross-input consistency rules | Implemented and regression-protected | `parseSaleFacts`; shared matcher |
| Quantity defaults to 1 only for a command with explicit payment and a medicine candidate | Historical fast-sale grammar plus owner recovery instruction | Implemented | `parseSaleFacts` |
| Catalog match hydrates canonical name, strength, form, unit, unit price, stock, cost and traceability without invention | Engineering Memory line 468; LATP 819–821; fixture standard | Implemented | `prepareProductionSaleCard`; `PharmacyBrain` |
| Fast action prioritizes medicine, exact form/unit, unit price, quantity, total, payment, stock consequence and Confirm/Read/Correct/Cancel | LATP 819; current live state 468 | Implemented | shared three-section renderer |
| Stock & details is secondary and does not block an ordinary valid sale | LATP 819; summary-first/rush-hour rule | Implemented | shared renderer; `productionSaleIssues` |
| Traceability holds supplier, barcode, batch, expiry, aliases and notes; absent optional values do not block | LATP 819; owner recovery instruction | Implemented | shared renderer; readiness policy |
| Ambiguous forms/units use an explicit choice; missing unit/price/conversion stays Unknown and blocks | LATP 819; architecture snapshot; fixture standard | Implemented at shared card boundary | `saleOptions`; `productionSaleIssues` |
| Unit/price/form/strength mismatch and insufficient stock are blocked with an exact explanation | LATP 819; Engineering Memory line 468 | Implemented | `productionSaleIssues` |
| Unit-specific price and conversion control total and stock consequence | LATP 819–823; MS2-LT-049 specification | Implemented in canonical model; owner validation pending | `unitPrices`; `unitConversions` |
| Corrections retain identity and viewport and immediately refresh total/readiness without rerendering the card | Protected editable-card viewport rule; Stock Fix control-drift lesson | Implemented | `refreshProductionSaleCardControls` |
| Read exposes the shared local segmented Read/Pause/Resume/Stop lifecycle | Protected generic editable-card narration | Reused; no new reader variant | `speechControlsTemplate` |
| Cancel causes no sale, stock, payment, sync or downstream reward action | Review-first/confirmation and TCE rules | Implemented and source-regression protected | `rejectCard`; `recordCard` only after Confirm |
| Pack-photo facts retain field provenance and never invent or duplicate | Protected medicine-pack onboarding; LATP 821 | Existing shared acquisition rule; not reimplemented in this recovery | visual/catalog pipeline |
| Typed/voice/barcode/camera/photo/file/catalog/quick-add and ledger/stock/report/history/undo/offline/export consumers retain exact truth | LATP 821–823; Engineering Memory line 468 | Shared canonical fields and transaction metadata implemented; the ordered MS2-LT-049 cross-input matrix remains not started | shared model, TCE metadata, queue/sync adapters |
| Multiuser attribution, loyalty triggers and Demo Mode must consume this same SaleCard | Launch roadmap | Architectural requirement preserved; those future milestones remain not started | integration adapters; no alternate SaleCard permitted |

## Failure and root correction

Owner evidence showed `paracetamol cash` becoming Medicine `paracetamol cash` with blank quantity, payment and catalog facts. The former grammar required an explicit quantity, so the command fell into `MedicineMatchCard` and the fallback treated the whole transcript as identity. The root correction parses the terminal payment first, resolves the remaining text catalog-first, safely defaults quantity to 1, then optionally extracts a separated or compact numeric quantity. Typed and voice paths both use this parser and the same catalog hydration before rendering.

The first recovery implementation also flattened the card. The authoritative design requires three sections, so the one shared renderer now owns Fast action, Stock & details and Traceability. A valid ordinary sale is confirmable entirely from Fast action; optional traceability never blocks it.

## Hold

This recovery does not pass or protect the Production Sales Card and does not start MS2-LT-049. Only complete owner evidence can approve the card. Until then, the launch sequence remains paused.

## Compact production presentation

The recovered information model remains unchanged, but its default presentation is now a compact cream approval surface. The first screen shows the exact identity summary, unit price, quantity, total, payment, stock before/after, status, quantity/payment shortcuts, and Confirm/Read/Correct/Cancel. Stock/detail and traceability facts remain one tap away as dense read-only lists.

Full inputs appear only after explicit **Correct**. Every editable Sale field then renders the same contextual field-heading/Mic pattern proven by Catalog Medicine Action Cards and delegates to the same `startVoiceCapture()` boundary. No second microphone service exists. Future work must not restore the long all-input default card.

## Shared viewport ownership — 2026-07-30

Owner evidence proved that quantity, payment, speech controls and correction rerenders were incorrectly entering the normal new-message `scrollChatToBottom()` branch. Inline interaction now captures the active card and its scroll-container coordinates before mutation. The shared render boundary restores that anchor without focusing the composer or reopening the keyboard. Catalog contextual voice retains its more precise field anchor; Sale and every other active card reuse the same anchor service. Only an actual appended feed/card or deliberate focus navigation releases inline ownership.

Sale correction microphones continue to use the shared contextual editable-field component and `startVoiceCapture()`, but receive a compact 44-pixel tap target and quiet cream styling. Computed total and stock-after remain read-only. Status remains awaiting owner live validation; this fix is not protected yet.

## Remaining-root implementation — 2026-07-30

Sales contextual voice now takes in-place render ownership for the exact selected input throughout permission, startup, listening, interim/final result, error and retry. It updates field/status controls without replacing the carousel DOM, scheduling focus, or changing `activeSlide`. A removed card whose visual anchor no longer exists deliberately returns the chat to the recent working end instead of leaving a rebuilt chat at scroll position zero.

Typed and voice sales now parse a requested selling unit independently from medicine and quantity. The shared Sale model consumes authoritative `baseStockUnit`, `unitConversions` and `unitPrices`; unknown conversion or price blocks confirmation and exposes only the required correction fields. See `medicine-pack-hierarchy-standard.md`. The checkpoint remains open pending owner screenshots.
