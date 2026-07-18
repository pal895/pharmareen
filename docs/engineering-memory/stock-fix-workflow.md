# Stock Fix workflow engineering memory

## Shared architecture

Typed/manual, Pharmacy Catalog, picture-assisted and microphone-guided Stock Fix entry all create or hydrate one `StockCorrectionCard`. Every source converges before validation on the same fields: canonical medicine, trusted current stock, requested corrected stock and audit reason. The shared policy owns catalog matching, whole non-negative stock validation, stale-current rejection, no-op rejection, signed adjustment and `queued_not_applied` truth. The safe offline action queue is authoritative at this stage; Stock Fix does not directly mutate Pharmacy Catalog stock.

## Live failure and root cause — 2026-07-18

The first manual live test visibly retained Losartan, current 37, corrected 36 and reason `Physical count test` across all three slides, but Confirm remained disabled and the card continued saying the medicine was missing. The authoritative draft was updating correctly. The defect was the shared editable-card control lifecycle: confirmation readiness and owner guidance were rendered once from the initial blank card and were never refreshed after input because field edits intentionally persist without rerendering the whole card. This created visible-value/control-state drift. Mobile touch hover also made a previously touched slide tab look selected alongside the real active tab.

The shared fix updates readiness, button disabled/title state and owner guidance directly whenever an editable Stock Fix field changes, while preserving the authoritative draft and active slide. Active slide is persisted in card UI state, restored after rerender and is the only tab with selected styling; hover styling is restricted to fine-pointer devices.

The second manual live attempt exposed two additional shared-root facts. First, canonical saved Pharmacy Catalog records expose transaction-updated stock as `stockLeft`; the Stock Fix trusted-stock reader omitted that canonical shape and therefore falsely reported that both Losartan and Cefixime had no trusted stock, leaving Confirm disabled. One shared `trustedCatalogStock` reader now covers `stock`, `stockLeft`, `current_stock` and legacy `quantity` without inventing a value. Second, Android/Chrome did not reliably resume the single long Web Speech utterance and speech had no visual slide synchronization. Stock Fix Read is now three deterministic local utterance segments. Each segment moves to its matching slide on `onstart`; Pause cancels safely while retaining the segment index, Resume restarts that segment and continues, Stop ends the session, and Read starts again from slide 1. This keeps visible review and speech aligned without AI calls.

## Reusable interaction behavior

- Confirm reads the complete authoritative draft across all slides, uses a submitting guard, then queues one idempotent action. Cancellation removes the draft without mutation.
- Result copy shows medicine, previous stock, requested stock, reason and `Pending sync`, and repeats that saved stock has not changed.
- Read uses three local device speech-synthesis segments and speaks only the concise owner fields. The active slide follows the segment being spoken. Pause, Resume, Stop and replay through Read make no AI call.
- Stock Fix Camera and Photo reuse the existing acquisition pipeline. A locally recognized controlled package is matched against the active Pharmacy Catalog before it can prefill canonical medicine/current stock. Unknown or uncertain images fill nothing and ask for the missing identity. Image audit metadata remains local runtime state and is never a Git asset.
- The microphone routes into the active Stock Fix draft before general command parsing. It supports medicine, current/correct stock, reason, back/change-field, Read/Repeat, Confirm and Cancel. Confident fields advance only in voice mode; manual editing never triggers surprise slide movement. A complete voice draft performs a three-slide review pass and concise local Read summary.
- Medicine resolution remains catalog-first, alias/fuzzy/phonetic aware and ambiguity-safe. A short choice is required when confidence is insufficient. Confirmed pronunciation mappings are pharmacy-scoped, correctable and never replace canonical medicine names or leak to another tenant.

## Regression protection

`npm run verify:stock-fix` protects visible-draft/control synchronization, cross-slide persistence, active-tab truth, canonical validation, stale/current/no-op safeguards, concise Read behavior, photo/voice convergence, spoken Confirm/Cancel and change-field commands, safe ambiguity, pharmacy-isolated pronunciation memory, duplicate queue idempotency and queued-not-applied result truth.

## Live discipline

Keep the original manual checkpoint open until new screenshots pass. Resume one test at a time: first manual with a different saved medicine, then picture-assisted with another medicine, then voice-guided with a harder name. Do not combine them and do not repeat Losartan unless regression evidence specifically requires it.
