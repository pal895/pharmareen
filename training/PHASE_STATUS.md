# PharMareen Training Phase Status

Historical implementation-phase evidence. Canonical MS2.0 owner checkpoint IDs, order and status live only in `../MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`.

## Phase 1 - Training Infrastructure + Medicine Brain

Status: PASS

- [x] training files created
- [x] medicine brain created
- [x] forms/units supported
- [x] aliases supported
- [x] typo handling supported
- [x] shorthand supported
- [x] ambiguity handling supported
- [x] missing medicines report generated
- [x] zero AI calls proven
- [x] tests pass
- [x] existing WhatsApp/offline/Sheets/report flows untouched

## Notes

- Phase 1 is isolated and does not wire into WhatsApp, offline app, Sheets, reports, or intake.
- Required focused tests passed with `python -m pytest tests/test_medicine_brain.py tests/test_training_store.py tests/test_missing_medicine_report.py -p no:cacheprovider`.
- `pytest` was not on PATH in this shell, so `python -m pytest` was used.
- `MISSING_MEDICINES_REPORT.txt` generated with a copy-paste list for onboarding.

## Phase 2 - Local-First Parser Wrapper

Status: PASS

- [x] local parser wrapper created
- [x] known/common commands do not call AI
- [x] AI fallback still preserved for messy unknown input
- [x] ambiguity asks once
- [x] typo correction works locally
- [x] shorthand works locally
- [x] stock check detected locally
- [x] restock detected locally
- [x] insufficient stock sale blocks and logs missed demand
- [x] existing intake/report/config/sheets tests pass
- [x] tests pass

## Phase 2 Notes

- Added `LocalFirstParser` wrapper around the existing parser contract.
- Known local commands return `ParseResult` without fallback/API use.
- Payment/form/package/dose metadata is carried in `ParsedEvent.notes`; no Sheets schema change.
- Phase 2 eval passed with `python scripts/run_phase2_local_parser_eval.py`.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.

## Phase 3 - Owner Correction + Learning Memory

Status: PASS

- [x] correction storage created
- [x] correction updates alias memory
- [x] correction affects future parsing
- [x] ambiguity reduces after owner approval
- [x] pharmacy-specific learning supported
- [x] payment alias learning supported
- [x] form/package/unit alias learning supported
- [x] owner/staff trace fields stored where provided
- [x] no Google Sheets schema change
- [x] no AI needed
- [x] tests pass
- [x] no production break

## Phase 3 Notes

- Added file-backed correction learning in `training/corrections.json` pharmacy namespaces.
- Correction commands use explicit teaching syntax like `amox means amoxicillin`, `k means cash`, or `sleeve means strip`.
- Learned memory is reloaded into the local-first parser immediately after approval.
- Phase 3 eval passed with `python scripts/run_phase3_correction_eval.py`.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.

## Phase 4 - Pharmacy Workflow Brain

Status: PASS

- [x] workflow evals created
- [x] sale behavior tested
- [x] stock behavior tested
- [x] restock behavior tested
- [x] undo/correction behavior tested
- [x] no-stock behavior tested
- [x] payment behavior tested
- [x] report behavior tested
- [x] supplier/expiry/batch placeholders ready
- [x] short operational replies preserved
- [x] no unnecessary AI calls
- [x] tests pass

## Phase 4 Notes

- Added local workflow recognition for undo, operational correction, expiry, supplier, and batch placeholder commands.
- Undo/correction by sale number is recognized but safely staged for Phase 5 daily sale numbering.
- Supplier/expiry/batch commands are recognized and return short staged replies without changing Sheets schema.
- Report metrics ignore workflow tracking rows unless later phases explicitly assign report semantics.
- Phase 4 eval passed with `python scripts/run_phase4_workflow_eval.py`.
- Regression evals passed for Phase 2, Phase 3, and Phase 4.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.

## Phase 5 - Daily Sale Numbering Engine

Status: PASS

- [x] daily sale numbering implemented safely
- [x] reset by date works
- [x] daily sale numbering still resets correctly by date after undo/edit coverage
- [x] undo last sale restores stock correctly
- [x] undo by sale number tested
- [x] duplicate reversal is blocked
- [x] duplicate reversal does not restore stock twice
- [x] correction by sale number tested
- [x] wrong medicine correction restores old stock and deducts corrected medicine stock
- [x] wrong quantity correction reconciles stock and total value
- [x] wrong payment correction supports Cash, M-Pesa, and Credit
- [x] finance totals reverse safely after undo
- [x] Cash/M-Pesa/Credit totals reconcile after undo/edit
- [x] reports reflect corrected ledger totals
- [x] audit/history keeps created, corrected, and undone trace
- [x] show sale by number tested
- [x] today sale count tested
- [x] reports/logs can reference sale numbers through sale notes
- [x] multi-owner/staff safety considered through pharmacy namespaces and actor audit fields
- [x] all known Phase 5 flows run without AI/OpenAI fallback
- [x] existing intake/report/config/sheets tests pass
- [x] tests pass

## Phase 5 Notes

- Added file-backed daily sale ledger in `training/sale_ledger.json`.
- Sales receive `Sale #N` per pharmacy/day and reset on the next date.
- Sale numbers are written into daily log notes without changing the Google Sheets schema.
- Undo by sale number and undo-last mark the ledger record undone and restore stock when possible.
- Duplicate undo is blocked at the ledger before stock restore, preventing duplicate reversal.
- Correction by sale number updates ledger audit data for supported fields such as medicine, quantity, payment, price, and total.
- Wrong-medicine correction restores the original medicine stock and deducts the corrected medicine stock.
- Wrong-quantity correction adjusts stock delta and recalculates total value.
- Payment correction supports Cash, M-Pesa, and Credit and feeds finance summaries.
- Daily reports can use ledger finance summaries so corrected/undone sales drive totals and payment reconciliation.
- `show sale N` and `today sale count` are recognized locally.
- Strengthened Phase 5 eval passed with `python scripts/run_phase5_sale_numbering_eval.py`.
- Regression evals passed for Phase 2, Phase 3, Phase 4, and Phase 5.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.
- Focused Phase 5 tests passed with `python -m pytest tests/test_sale_numbering.py tests/test_intake_service.py tests/test_report_service.py tests/test_local_first_parser.py -p no:cacheprovider`.
- No OpenAI/API calls were used during Phase 5 tests/evals.

## Phase 6 - Multi-Owner / Staff Learning Safety

Status: PASS

- [x] pharmacy namespace exists
- [x] owner/staff identity supported
- [x] correction approval can be owner-scoped
- [x] staff/cashier corrections are held pending owner approval
- [x] owner-approved corrections become pharmacy-wide memory
- [x] pharmacy-specific learning remains isolated between pharmacies
- [x] staff actions are traceable in sale audit history
- [x] owner corrections/reversals are traceable in sale audit history
- [x] reports remain accurate from active ledger state
- [x] stock/payment/report behavior remains synchronized
- [x] Phase 2-5 regression evals still pass
- [x] tests pass
- [x] no AI/OpenAI calls used for known Phase 6 flows

## Phase 6 Notes

- Added `ActorContext` for owner, staff, cashier, source, and pharmacy identity.
- Existing no-identity/single-owner flows remain backward compatible.
- Explicit staff/cashier learning corrections now save as pending corrections instead of immediately changing pharmacy memory.
- Owner approval commits pending corrections into pharmacy-wide memory with staff and owner trace.
- Training memory now stores actors and pending correction decisions inside each pharmacy namespace.
- Intake can accept optional actor context and writes actor identity/role/source to sale ledger audit.
- Sale ledger audit now records actor role for created, corrected, and undone sale events.
- Report totals continue to come from active ledger state, so staff/owner audit metadata does not change finance behavior.
- Phase 6 eval passed with `python scripts/run_phase6_multi_owner_eval.py`.
- Regression evals passed for Phase 2, Phase 3, Phase 4, and Phase 5.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.
- Stop before Phase 7 personality/owner experience until explicitly instructed.

## Phase 7 - Personality + Owner Experience Engine

Status: PASS

- [x] morning greeting logic staged/tested
- [x] end-of-day message logic staged/tested
- [x] personality remains short
- [x] no spam through once-per-day state
- [x] no unnecessary AI calls
- [x] owner can disable/tune later
- [x] pharmacy-specific personality settings supported
- [x] rush-hour/workday interruption avoided by time windows
- [x] existing intake/report/sale flows untouched
- [x] Phase 2-6 regression evals still pass
- [x] tests pass

## Phase 7 Notes

- Added deterministic `OwnerExperienceEngine` for short morning and end-of-day owner messages.
- Added `training/personality_settings.json` for default and pharmacy-specific tuning.
- Added `training/personality_state.json` for once-per-day no-spam state.
- Morning greeting is generated only inside the configured morning window.
- End-of-day message is generated only inside the configured end-of-day window.
- Owner/pharmacy can disable or tune templates through settings without changing code.
- Phase 7 is staged and tested but not injected into live sale intake, so rush-hour operational replies stay unchanged.
- Phase 7 eval passed with `python scripts/run_phase7_personality_eval.py`.
- Regression evals passed for Phase 2, Phase 3, Phase 4, Phase 5, and Phase 6.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.
- Stop before Phase 8 eval runner/training dashboard until explicitly instructed.

## Phase 8 - Eval Runner + Training Dashboard

Status: PASS

- [x] eval runner created
- [x] all phase evals included
- [x] PASS/FAIL output clear
- [x] failed cases saved as training examples when failures exist
- [x] unresolved issues listed
- [x] ready/not-ready decision shown
- [x] medicine matching covered
- [x] typos covered
- [x] shorthand covered
- [x] forms/units covered
- [x] payments covered
- [x] ambiguity covered
- [x] corrections covered
- [x] workflow commands covered
- [x] sale numbering covered
- [x] multi-owner behavior covered
- [x] personality rules covered
- [x] zero-token proof covered
- [x] Phase 2-7 regression evals still pass
- [x] tests pass

## Phase 8 Progress Board

- [x] training infrastructure
- [x] medicine brain
- [x] local parser wrapper
- [x] correction memory
- [x] workflow brain
- [x] daily sale numbering
- [x] multi-owner sync
- [x] personality engine
- [x] eval runner
- [x] missing medicines report
- [x] zero-token proof
- [x] ready for Phase 9 review

## Phase 8 Notes

- Added unified training eval runner at `scripts/run_pharmacy_training_eval.py`.
- Added generated training dashboard at `training/TRAINING_DASHBOARD.md`.
- Added unresolved issue report at `training/UNRESOLVED_EVAL_ISSUES.md`.
- Added failed eval training examples file at `training/eval_failed_training_examples.jsonl`.
- The unified runner includes Phase 1 medicine-brain eval plus Phase 2-7 eval scripts.
- The unified runner writes PASS/FAIL, coverage, unresolved issues, failure examples, and ready/not-ready decision.
- Phase 8 unified eval passed with `python scripts/run_pharmacy_training_eval.py`.
- Regression evals passed for Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, and Phase 7.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.
- Stop before Phase 9 controlled live test preparation until explicitly instructed.

## Phase 9 - Controlled Live Test Preparation

Status: PASS

- [x] WhatsApp deterministic sale prepared
- [x] typo sale prepared
- [x] shorthand sale prepared
- [x] ambiguous medicine prepared
- [x] no-stock block prepared
- [x] stock check prepared
- [x] undo by sale number prepared
- [x] correction by sale number prepared
- [x] report today prepared
- [x] multi-owner/staff simulated test prepared
- [x] offline Tap & Talk online prepared
- [x] offline Tap & Talk offline prepared
- [x] offline media queue online/offline prepared
- [x] WhatsApp invoice/photo prepared for later controlled live test
- [x] offline invoice/photo prepared for later controlled live test
- [x] editable approval card prepared
- [x] token usage preservation prepared
- [x] one-test-at-a-time rule documented
- [x] stop/fix/eval/retest rule documented
- [x] evidence fields documented
- [x] live execution remains not started
- [x] Phase 2-8 regression evals still pass
- [x] tests pass

## Phase 9 Notes

- Added machine-readable controlled live test plan at `training/live_test_plan.json`.
- Added human runbook at `training/LIVE_TEST_PLAN.md`.
- Added Phase 9 readiness eval at `scripts/run_phase9_live_readiness_eval.py`.
- Added Phase 9 eval cases at `training/evals/phase9_live_readiness_cases.jsonl`.
- Added Phase 9 tests at `tests/test_phase9_live_readiness.py`.
- Live test execution status is explicitly `not_started`.
- Paused offline/photo/editable-card surfaces are prepared only; no live test was started.
- Known deterministic live checklist items declare zero/no-unnecessary AI expectations.
- Phase 9 readiness eval passed with `python scripts/run_phase9_live_readiness_eval.py`.
- Regression evals passed for Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, Phase 7, and Phase 8 unified runner.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.
- Stop before Phase 10 or any live execution until explicitly instructed.

## Phase 10 - Production Reliability + Offline Recovery Engine

Status: PASS

- [x] offline queue resilience implemented
- [x] WhatsApp/offline synchronization safety supported
- [x] duplicate prevention implemented
- [x] reconnect recovery implemented
- [x] failed-sync retry safety implemented
- [x] grouped confirmation handling implemented
- [x] low-network pharmacy behavior implemented
- [x] no-data-loss guarantees implemented
- [x] conflict evidence retained
- [x] retry/dead-letter audit retained
- [x] Phase 2-9 regression evals still pass
- [x] tests pass

## Phase 10 Notes

- Phase 10 is officially locked as `Production Reliability + Offline Recovery Engine`.
- Added reliability policy at `training/reliability_policy.json`.
- Added file-backed reliability ledger at `training/reliability_ledger.json`.
- Added deterministic reliability engine at `app/reliability.py`.
- Added Phase 10 eval cases at `training/evals/phase10_reliability_cases.jsonl`.
- Added Phase 10 eval runner at `scripts/run_phase10_reliability_eval.py`.
- Added Phase 10 tests at `tests/test_production_reliability.py`.
- Extended unified training eval runner to include Phase 9 and Phase 10.
- The reliability engine keeps idempotent sync records for offline/WhatsApp sources.
- Duplicate payloads with the same idempotency key are blocked without creating extra applied work.
- Conflicting payloads with the same idempotency key are retained for review instead of overwriting data.
- Stale inflight and due retry items are recovered on reconnect.
- Failed syncs retry safely and move to dead-letter after max attempts while retaining payload/audit evidence.
- Grouped confirmations summarize synced, waiting, and review-needed items.
- Low-network mode returns a short offline-safe acknowledgement and preserves backlog.
- Phase 10 eval passed with `python scripts/run_phase10_reliability_eval.py`.
- Regression evals passed for Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, Phase 7, Phase 8 unified runner, and Phase 9.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.
- Stop before Phase 11 until explicitly instructed.

## Phase 11 - Live Pharmacy Pilot Execution Engine

Status: PASS

- [x] controlled real-pharmacy pilot handling implemented
- [x] one-pharmacy-at-a-time rollout safety implemented
- [x] live issue capture pipeline implemented
- [x] live correction/retraining loop implemented
- [x] production telemetry logging implemented
- [x] pharmacy-specific adaptation learning implemented
- [x] live token-usage monitoring implemented
- [x] live rollback/recovery safety implemented
- [x] owner feedback capture implemented
- [x] real-world workflow friction tracking implemented
- [x] pilot stability scoring implemented
- [x] production readiness validation implemented
- [x] zero-token known-medicine flow protection preserved
- [x] audit/reversal/reliability protections preserved
- [x] offline recovery guarantees preserved
- [x] duplicate-prevention guarantees preserved
- [x] grouped confirmation protections preserved
- [x] pilot pharmacy isolation preserved
- [x] live errors generate retraining examples
- [x] pilot evidence is logged safely
- [x] Phase 2-10 regression evals still pass
- [x] tests pass

## Phase 11 Notes

- Phase 11 is officially locked as `Live Pharmacy Pilot Execution Engine`.
- Added live pilot policy at `training/live_pilot_policy.json`.
- Added file-backed live pilot ledger at `training/live_pilot_ledger.json`.
- Added deterministic live pilot engine at `app/live_pilot.py`.
- Added Phase 11 eval cases at `training/evals/phase11_live_pilot_cases.jsonl`.
- Added Phase 11 eval runner at `scripts/run_phase11_live_pilot_eval.py`.
- Added Phase 11 tests at `tests/test_live_pharmacy_pilot.py`.
- Extended unified training eval runner to include Phase 11.
- The pilot engine supports one active pilot pharmacy at a time and blocks concurrent rollout.
- Live telemetry records evidence, token observations, reliability idempotency results, and workflow source.
- Live issues and token violations generate retraining examples in `training/live_retraining_examples.jsonl`.
- Owner-approved corrections learn only inside the active pharmacy namespace.
- Rollback points retain reliability no-data-loss snapshots plus duplicate/offline/grouped confirmation guarantees.
- Stability scoring and production readiness validation are deterministic and local-first.
- Phase 11 eval passed with `python scripts/run_phase11_live_pilot_eval.py`.
- Regression evals passed for Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, Phase 7, Phase 8 unified runner, Phase 9, and Phase 10.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.
- Stop before Phase 12 until explicitly instructed.

## Phase 12 - Pharmacy Deployment + Onboarding System

Status: PASS

- [x] pharmacy onboarding workflow implemented
- [x] pharmacy profile/bootstrap setup implemented
- [x] medicine import/bootstrap tools implemented
- [x] owner setup assistant implemented
- [x] onboarding checklist automation implemented
- [x] deployment readiness verification implemented
- [x] live monitoring dashboard implemented
- [x] pharmacy recovery/support tools implemented
- [x] multi-pharmacy isolation protections implemented
- [x] onboarding speed optimization implemented
- [x] deployment rollback safety implemented
- [x] pharmacy activation/deactivation handling implemented
- [x] branch registration handling implemented
- [x] deployment audit logging implemented
- [x] production deployment scoring implemented
- [x] zero-token known-medicine flow protection preserved
- [x] offline reliability protections preserved
- [x] rollback/recovery protections preserved
- [x] pilot safety protections preserved
- [x] duplicate-prevention guarantees preserved
- [x] grouped confirmation protections preserved
- [x] pharmacy isolation guarantees preserved
- [x] token monitoring protections preserved
- [x] onboarding failures are recoverable safely
- [x] deployment actions are fully auditable
- [x] Phase 2-11 regression evals still pass
- [x] tests pass

## Phase 12 Notes

- Phase 12 is officially locked as `Pharmacy Deployment + Onboarding System`.
- Added deployment policy at `training/deployment_policy.json`.
- Added file-backed deployment ledger at `training/deployment_ledger.json`.
- Added deterministic deployment/onboarding engine at `app/deployment.py`.
- Added Phase 12 eval cases at `training/evals/phase12_deployment_cases.jsonl`.
- Added Phase 12 eval runner at `scripts/run_phase12_deployment_eval.py`.
- Added Phase 12 tests at `tests/test_pharmacy_deployment.py`.
- Extended unified training eval runner to include Phase 12.
- The deployment engine bootstraps pharmacy profiles, owner setup, branch registration, and medicine imports in isolated pharmacy namespaces.
- Checklist automation verifies profile, owner, branch, medicine, reliability, pilot safety, rollback, monitoring, and audit readiness.
- Monitoring dashboard exposes checklist progress, reliability state, token monitoring, support tickets, rollback availability, audit, and deployment score.
- Onboarding failures create support tickets and rollback snapshots so failed setup can be recovered safely.
- Activation is blocked unless readiness, token, reliability, pilot, rollback, monitoring, audit, and scoring protections pass.
- Deactivation and deployment rollback are file-backed and fully audited.
- Phase 12 eval passed with `python scripts/run_phase12_deployment_eval.py`.
- Regression evals passed for Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, Phase 7, Phase 8 unified runner, Phase 9, Phase 10, and Phase 11.
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.
- Stop before Phase 13 until explicitly instructed.

## Phase 13 - Autonomous Onboarding + Provisioning Engine

Status: PASS

- [x] central provisioning engine implemented
- [x] one-click pharmacy infrastructure creation implemented
- [x] three-step pharmacy-owner onboarding implemented
- [x] unknown-number auto-onboarding implemented
- [x] admin review controls for unknown numbers implemented
- [x] auto infrastructure generation implemented
- [x] pharmacy profile namespace generation implemented
- [x] Google Sheets setup config generation implemented
- [x] isolated medicine database/bootstrap generation implemented
- [x] isolated medicine alias/search namespace generation implemented
- [x] offline sync queue config generation implemented
- [x] WhatsApp routing config generation implemented
- [x] deployment config generation implemented
- [x] rollback/recovery config generation implemented
- [x] monitoring/dashboard config generation implemented
- [x] onboarding stress test engine implemented
- [x] 10/50/100/500/1000 pharmacy stress scales covered
- [x] namespace-isolation stress proof implemented
- [x] offline queue and sync-safety stress proof implemented
- [x] duplicate-prevention proof implemented
- [x] activation/readiness gate implemented
- [x] Phase 12 deployment readiness gate reused
- [x] zero-token known-flow protection preserved
- [x] offline reliability protections preserved
- [x] sync reliability protections preserved
- [x] grouped confirmation protections preserved
- [x] retry safety protections preserved
- [x] recovery/rollback protections preserved
- [x] Phase 1-12 regression evals still pass
- [x] tests pass

## Phase 13 Notes

- Phase 13 is officially locked as `Autonomous Onboarding + Provisioning Engine`.
- Added provisioning policy at `training/provisioning_policy.json`.
- Added provisioning templates at `training/provisioning_templates.json`.
- Added file-backed provisioning ledger at `training/provisioning_ledger.json`.
- Added deterministic autonomous provisioning engine at `app/provisioning.py`.
- Added Phase 13 eval cases at `training/evals/phase13_provisioning_cases.jsonl`.
- Added Phase 13 eval runner at `scripts/run_phase13_provisioning_eval.py`.
- Added Phase 13 tests at `tests/test_autonomous_provisioning.py`.
- Extended unified training eval runner to include Phase 13.
- The provisioning engine creates isolated pharmacy infrastructure records with profile, owner, branch, Sheets, medicine, alias, queue, WhatsApp routing, deployment, rollback, recovery, monitoring, dashboard, audit, and token-safety config.
- Owner onboarding is capped to three sequenced steps: profile, medicine import, and readiness validation.
- Unknown-number onboarding opens a temporary namespace and requires admin approval before provisioning.
- Repeated provisioning for the same phone is idempotent and returns the existing pharmacy instead of creating a duplicate.
- Activation gate requires Phase 12 deployment readiness plus provisioning-level offline sync, duplicate prevention, rollback, medicine database, token, onboarding, WhatsApp, and report health.
- Stress testing generates 10, 50, 100, 500, and 1000 pharmacy records and checks namespace isolation, queue safety, sync safety, duplicate prevention, rollback, and recovery.
- Phase 13 eval passed with `python scripts/run_phase13_provisioning_eval.py`.
- Unified Phase 1-13 eval passed with `python scripts/run_pharmacy_training_eval.py`.
- Required Phase 2-12 regression evals passed:
  - `python scripts/run_phase2_local_parser_eval.py`
  - `python scripts/run_phase3_correction_eval.py`
  - `python scripts/run_phase4_workflow_eval.py`
  - `python scripts/run_phase5_sale_numbering_eval.py`
  - `python scripts/run_phase6_multi_owner_eval.py`
  - `python scripts/run_phase7_personality_eval.py`
  - `python scripts/run_phase9_live_readiness_eval.py`
  - `python scripts/run_phase10_reliability_eval.py`
  - `python scripts/run_phase11_live_pilot_eval.py`
  - `python scripts/run_phase12_deployment_eval.py`
- Full local tests passed with `python -m pytest tests -p no:cacheprovider`.
- Stop before Phase 14 until explicitly instructed.
