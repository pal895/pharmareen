# Stock Fix workflow engineering memory

## Shared architecture

Typed/manual, Pharmacy Catalog, picture-assisted and microphone-guided Stock Fix entry all create or hydrate one `StockCorrectionCard`. Every source converges before validation on the same fields: canonical medicine, trusted current stock, requested corrected stock and audit reason. One shared execution policy owns catalog matching, whole non-negative stock validation, stale-current rejection, no-op rejection, signed adjustment, immediate online application and the automatic offline fallback.

Online Confirm updates the durable local Pharmacy Catalog immediately, writes one audit completion and creates no pending duplicate. When the device is offline or durable local storage is unavailable, the same idempotent action is retained once in the offline queue; startup or the browser `online` event retries it automatically and applies it once. Ordinary Stock Fix never requires a separate Sync tap.

## Live failure and root cause — 2026-07-18

The first manual live test visibly retained Losartan, current 37, corrected 36 and reason `Physical count test` across all three slides, but Confirm remained disabled and the card continued saying the medicine was missing. The authoritative draft was updating correctly. The defect was the shared editable-card control lifecycle: confirmation readiness and owner guidance were rendered once from the initial blank card and were never refreshed after input because field edits intentionally persist without rerendering the whole card. This created visible-value/control-state drift. Mobile touch hover also made a previously touched slide tab look selected alongside the real active tab.

The shared fix updates readiness, button disabled/title state and owner guidance directly whenever an editable Stock Fix field changes, while preserving the authoritative draft and active slide. Active slide is persisted in card UI state, restored after rerender and is the only tab with selected styling; hover styling is restricted to fine-pointer devices.

The second manual live attempt exposed two additional shared-root facts. First, canonical saved Pharmacy Catalog records expose transaction-updated stock as `stockLeft`; the Stock Fix trusted-stock reader omitted that canonical shape and therefore falsely reported that both Losartan and Cefixime had no trusted stock, leaving Confirm disabled. One shared `trustedCatalogStock` reader now covers `stock`, `stockLeft`, `current_stock` and legacy `quantity` without inventing a value. Second, Android/Chrome did not reliably resume the single long Web Speech utterance and speech had no visual slide synchronization. Stock Fix Read is now three deterministic local utterance segments. Each segment moves to its matching slide on `onstart`; Pause cancels safely while retaining the segment index, Resume restarts that segment and continues, Stop ends the session, and Read starts again from slide 1. This keeps visible review and speech aligned without AI calls.

## Reusable interaction behavior

- Confirm reads the complete authoritative draft across all slides, uses a submitting guard, then queues one idempotent action. Cancellation removes the draft without mutation.
- Result copy shows medicine, previous stock, requested stock and reason, says it is waiting to sync, and repeats that saved stock has not changed.
- Read uses three local device speech-synthesis segments and speaks only the concise owner fields. The active slide follows the segment being spoken. Pause, Resume, Stop and replay through Read make no AI call.
- The owner path shows only three main choices: Confirm, one Read/Pause/Resume control, and More. More holds optional tools. The three sections use the short labels Medicine, Stock, and Reason.
- Stock Fix Camera and Photo reuse the existing acquisition pipeline. A locally recognized controlled package is matched against the active Pharmacy Catalog before it can prefill canonical medicine/current stock. Unknown or uncertain images fill nothing and ask for the missing identity. Image audit metadata remains local runtime state and is never a Git asset.
- The microphone routes into the active Stock Fix draft before general command parsing. It supports medicine, current/correct stock, reason, back/change-field, Read/Repeat, Confirm and Cancel. Confident fields advance only in voice mode; manual editing never triggers surprise slide movement. A complete voice draft performs a three-slide review pass and concise local Read summary.
- Medicine resolution remains catalog-first, alias/fuzzy/phonetic aware and ambiguity-safe. A short choice is required when confidence is insufficient. Confirmed pronunciation mappings are pharmacy-scoped, correctable and never replace canonical medicine names or leak to another tenant.

## Regression protection

`npm run verify:stock-fix` protects visible-draft/control synchronization, cross-slide persistence, active-tab truth, canonical validation, stale/current/no-op safeguards, concise Read behavior, photo/voice convergence, spoken Confirm/Cancel and change-field commands, safe ambiguity, pharmacy-isolated pronunciation memory, duplicate queue idempotency and queued-not-applied result truth.

It now also protects immediate online saved-stock application, no online pending duplicate, one offline fallback, duplicate-Confirm safety and idempotent automatic replay. Online result copy says `Stock updated`; offline copy plainly says the saved fix will update automatically.

## Live discipline

Keep the original manual checkpoint open until new screenshots pass. Resume one test at a time: first manual with a different saved medicine, then picture-assisted with another medicine, then voice-guided with a harder name. Do not combine them and do not repeat Losartan unless regression evidence specifically requires it.

Latest live evidence passes the segmented Read behavior: speech follows the three visible sections and pause/resume works as requested. It also shows the repaired ready state with an active Confirm button. No screenshot yet proves the queued result, so manual Stock Fix remains open only at Confirm. Do not repeat Read. Resume with the existing Cefixime 23 to 22 draft, tap Confirm once, and verify the simple waiting-to-sync result while saved stock stays 23.

## Corrected online checkpoint — 2026-07-18

The Cefixime 23 to 22 screenshot proves only that the former queue-first mechanism accepted the draft, left it pending and retained saved stock 23. It is product friction under the corrected owner intent, not a completed online Stock Fix. The shared execution repair supersedes the queue-first acceptance wording above.

Next live test: after pull/restart, note Losartan's saved stock, open Stock Fix and enter a different correct whole-number quantity with a short reason, then Confirm once. Pass only if the result says `Stock updated` and Pharmacy Catalog immediately shows the corrected saved quantity. Do not test Read again or begin picture assistance yet.

The corrected online checkpoint passed after `9deb92f`. Startup automatically applied the retained Cefixime 23 to 22 fallback once. A separate manual Losartan correction then changed saved stock immediately from 37 to 39; the result said `Stock updated`, and the independently reopened Medicine Action Card showed Current stock 39 with `No changes yet`. Manual Stock Fix is complete.

Next stage is picture-assisted Stock Fix with a different catalog medicine. Prepare and protect one realistic non-overlapping controlled package plus its exact trusted saved-stock baseline before asking the owner to test it; do not reuse the completed Amoxicillin onboarding fixture because it has no trusted saved stock.

The picture checkpoint is prepared with `fixtures/stock-fix-prednisolone-5mg.png` and its manifest. The package itself supports only Prednisolone 5 mg tablet identity, pack size, batch and expiry; current stock 24 comes exclusively from the matched saved Pharmacy Catalog record. A separate Stock Fix-only controlled registry prevents this fixture from changing ordinary medicine-photo onboarding. Filename, SHA-256 and bounded perceptual identity stay local and zero-token; unknown content fills no medicine or stock.

Focused protection covers the committed bitmap and manifest hash, isolated registry, safe unknown image, blank fixture stock, Source/Catalog identity convergence, trusted current-stock validation and the shared immediate online execution policy. Live test only Photo selection with corrected stock 23 and reason `Picture count test`; do not repeat manual or Read behavior.

Initial live evidence showed More appearing inert because its absolute options panel was clipped by the shared progressive-card carousel. Open More now spans the action row and expands its options in normal flow inside the card's vertical scroll area; this preserves one compact main choice while making Camera, Photo, Stop reading and Cancel reachable on mobile.

The next mobile selection proved More and Photo acquisition, then exposed a bounded Google Photos representation mismatch. Verified selection-composition hashes are now fixture-specific with the existing aspect gate and tolerance, while unrelated hashes remain rejected. Photo-specific success/failure guidance also overrides generic blank-card readiness so safe failure is visible instead of appearing to do nothing.
