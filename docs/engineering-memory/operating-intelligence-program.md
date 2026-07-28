# MS2.0 Pharmacy Operating Intelligence programme

Reconciled: 2026-07-28

MS2.0 is not complete when it merely records, displays, alerts or exports. The operating-intelligence layer must detect or interpret a meaningful pharmacy pattern or risk, explain why it matters, recommend a safe next action, reuse approved pharmacy-specific learning, or measure whether an action helped. Routine operation remains deterministic/local-first and uses no LLM unless a separately approved boundary is justified.

## Evidence classification

| Capability | State | Repository evidence and validation boundary |
| --- | --- | --- |
| Daily report metrics: sales, payments, cost, gross profit, best seller, peak time, missed demand and low stock | A — implemented and owner live-tested / protected | `app/reports.py`; Main App report generation/read checkpoints in Current Live Validation State. This proves truthful metrics, not complete decision support. |
| Direct deterministic analytics commands: cash/M-Pesa today, payment breakdown/top payment, best seller, peak hours, missed demand and profit | B — implemented, not owner live-tested as the current Main App intelligence experience | `app/intake.py`, `operational_intelligence.py`, `test_intake_service.py`, token guardrails. |
| Decision-support summary: what happened, why it matters and what to do next | C — partial | `deterministic_recommendations()` exists, but the current owner summary renderer returns metrics without those recommendations. No owner evidence protects an interpreted next-action summary. |
| Basic pharmacy learning: approved catalog aliases and owner-controlled corrections | A — implemented and owner live-tested / protected | Catalog alias Activity Compaction evidence and shared catalog review/approval history. |
| Adaptive pharmacy-specific reuse: repeated confirmed shorthand, local operational memory and daily pattern reuse | C — partial | `OperationalMemory` is integrated; `AdaptiveAliasLearner` has automated tests but is not integrated into the owner workflow. No owner live checkpoint proves repeated safe learning. |
| Reorder level and deterministic low/out-of-stock alerts | A — implemented and owner live-tested / protected | Catalog reorder property, low-stock and out-of-stock notification evidence. Alerts alone are not predictive reorder intelligence. |
| Supplier/reorder intelligence: movement-aware risk, suggested quantity, owner-controlled order and truthful fulfilment | D — approved/planned, previously missing from the compact intelligence sequence | Ordered approved improvement 1 in `LIVE_APP_TEST_PLAN.md`. |
| Stock/expiry/demand intelligence: likely stock-outs, fast/slow/dead stock, expiry urgency/value at risk and prioritized action | D — approved/planned, previously missing from the compact sequence | Future deterministic rules in `MS20_ONBOARDING_AND_OPERATIONS_INTELLIGENCE.md`, plus the permanent Digital Operations Assistant/Operational Intelligence continuation. |
| Exact form/unit and pack/conversion truth needed by sales, margin, stock movement and reorder calculations | D — approved/planned functional prerequisite | Ordered approved improvement 2 in `LIVE_APP_TEST_PLAN.md`. |
| Export IP/privacy/compliance, quiet UI and production provider qualification | D / externally gated | Ordered improvement 3, post-validation audit, and Transaction Completion Engine provider gate. |
| General anomaly detection beyond the named stock, expiry, demand, payment and activity rules | F — not found as an approved standalone repository programme | Do not invent or schedule a generic anomaly engine without a later explicit product decision. |

## Authoritative remaining order

1. Close Shared Editable-Card Voice Viewport / Focus Preservation.
2. Validate Payment Failure/Cancellation Action-Needed Notification.
3. Validate the Exact Form/Unit Sales and Complete Pack Data prerequisite programme.
4. Live-validate deterministic operational analytics commands in the Main App.
5. Complete and validate decision-support summaries and deterministic next actions.
6. Complete and validate pharmacy-specific learning and safe repeated reuse.
7. Complete and validate stock, expiry and demand risk prioritization.
8. Complete and validate Supplier Ordering and Truthful Fulfilment, including suggested reorder quantities and sourced statuses.
9. Complete Export IP, Privacy and Compliance Safeguards.
10. Complete the Product-Secrecy and Quiet-UI Audit.
11. Complete Production Payment-Provider Qualification only after the external provider gate is resolved.

Where older documents place supplier ordering before exact form/unit work, this reconciliation preserves supplier ordering as the approved intelligence programme but moves the canonical unit/conversion prerequisite first. Without it, reorder quantities and order costs cannot be truthful. Historical checkpoint notes remain evidence and do not override this dependency correction.
