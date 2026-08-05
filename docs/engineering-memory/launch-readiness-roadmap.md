# MS2.0 Launch Readiness Roadmap

> **OWNER APPROVAL — 2026-07-30:** The upgraded shared Production Sales Card passed owner validation and is protected exactly as implemented. The temporary hold is closed. Resume with the already-selected MS2-LT-049 only; do not repeat the protected Sales Card prerequisite.
>
> Earlier rejected evidence remains historical audit context. The repaired deterministic parser/hydration, compact three-tab renderer, shared voice/manual correction, viewport stability and safe pack clarification are now owner-approved regression requirements. This approval is not itself an MS2-LT-049 or Launch Gate pass.

Authority date: 2026-07-29

This document is the authoritative active-priority roadmap for the first MS2.0 pharmacy launch. `MS2.0_MASTER_LIVE_TEST_SEQUENCE.md` remains the canonical checkpoint/status/evidence registry and historical regression sequence. This roadmap changes active priority only: it does not delete, renumber, weaken, bypass, or falsely complete any checkpoint or prerequisite.

Launch readiness is determined only by the Launch Gate below. The number of remaining checkpoints is not a readiness measure. The former ascending checkpoint order is historical and must never auto-resume.

## Permanent work classes

- **Launch Critical:** mandatory before pharmacy visits and cold calling.
- **Demo Mode:** a small, polished, truthful route through real MS2.0 behavior.
- **Continuous Improvement:** preserved work that may continue after first launch.

Each active or historical non-protected legacy checkpoint appears exactly once in the migration table. Completed checkpoints retain their existing `PASS / PROTECTED` state in the master and are reused as gate evidence without retesting unless a real regression is found.

## Authoritative classification counts

| Class | Count | Composition |
|---|---:|---|
| Launch Critical | 24 | 17 migrated legacy checkpoints plus MS2-LT-077–082 and MS2-LT-084 |
| Demo Mode | 2 | Migrated MS2-LT-022 plus MS2-LT-083 certification |
| Continuous Improvement | 15 | Migrated legacy checkpoints, including two preserved deprecated compatibility checks |

The classification inventory contains **41** entries: all 33 non-protected/deprecated legacy checkpoints plus eight newly registered launch-program checkpoints. The two deprecated entries remain historical only, leaving 39 active incomplete items.

## MS2.0 Launch Gate

Allowed gate statuses are exactly `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `READY FOR OWNER TEST`, `PASS`, and `PROTECTED`.

MS2.0 may be declared launch-ready only when every mandatory row is `PASS` or `PROTECTED` and Demo Mode certification is `PASS` or `PROTECTED`. Automated evidence may move a row to `READY FOR OWNER TEST`; only owner evidence can move an owner-visible row to `PASS`, and protection remains governed by the master.

| Mandatory launch requirement | Checkpoint evidence | Status | Measurable exit condition |
|---|---|---|---|
| Core onboarding | MS2-LT-002–009, 011 | PROTECTED | A new owner can create the pharmacy and safely add/review medicines through the supported launch inputs without duplicate saves. |
| Medicine catalog integrity | MS2-LT-010–011, 031–032, 049 | NOT STARTED | Canonical identity, strength, form, unit, pack, price, stock and provenance remain correct across every launch input and consumer. |
| Fast sales recording | MS2-LT-014, 051–053 | PROTECTED | A known sale records once, receives a stable sale number, and applies stock/finance exactly once. |
| Payment failure/cancellation safety | MS2-LT-052–054 | PROTECTED | A waiting/failed payment leaves stock and paid truth unchanged, exits the queue, retains failed history and creates one actionable alert per failed sale. |
| Stock correctness | MS2-LT-015–020, 024–025, 049, 055–056 | NOT STARTED | Sale, restock, correction, return, refund and reversal preserve exact stock and financial truth without silent loss. |
| Search reliability | MS2-LT-010, 031 | PROTECTED | Typed and supported voice search resolve saved medicines locally, safely handle zero/ambiguous results and do not mutate records. |
| Editable-card reliability | MS2-LT-011, 013 | PROTECTED | Review, correction, validation, viewport focus, approve and discard remain stable on launch devices. |
| Voice reliability | MS2-LT-012–013 | PROTECTED | Permission, listening, transcript, retry and exact-field application work without hidden mutation. |
| Barcode/scanning demo reliability | MS2-LT-007, 081 | NOT STARTED | The selected demo scan/photo path resolves known evidence, marks uncertainty and never invents or silently saves critical values. |
| Reports and owner understanding | MS2-LT-021, 039, 071 | PROTECTED | The default report is concise, truthful, readable and explains only the actions needing attention; detail remains available. |
| Offline-first operations | MS2-LT-020, 061 | PROTECTED | Essential launch work continues locally and truthfully identifies cloud-only features as unavailable. |
| Synchronization and duplicate protection | MS2-LT-020, 061, 066 | PROTECTED | Queued work synchronizes idempotently with visible local/waiting/synchronizing/synchronized/needs-review state. |
| Data safety and recovery | MS2-LT-059, 068, 073, 076 | BLOCKED | Isolated persistence, backup/recovery, failed-onboarding recovery, retention and incident evidence are production-qualified. |
| Multiuser safety | MS2-LT-067, 077 | IN PROGRESS | MS2-LT-067-A has repository-tested first-owner activation and repeat phone-plus-PIN sign-in with durable hashed credentials and pharmacy-bound sessions; the physical-owner staging proof is still required before later staff invitations, shared truth, attribution, removal and device revocation. |
| Permission and audit reliability | MS2-LT-066–069 | IN PROGRESS | Minimum-necessary access and immutable audit history cover operational, billing, community and export actions. |
| Low-data operation | MS2-LT-080 | NOT STARTED | A recorded weak/intermittent-network session stays within documented request/byte budgets and recovers its queue safely. |
| Low-resource device operation | MS2-LT-080 | NOT STARTED | A documented older/low-memory phone session meets response, memory, heat and battery observation budgets without data loss. |
| Desktop/laptop usability | MS2-LT-080 | NOT STARTED | The same launch workflows pass at supported desktop viewport/input sizes without clipped or mobile-only controls. |
| Subscription and billing clarity | MS2-LT-074, 084 | BLOCKED | Packages, seats, active-device/replacement rules, expiry/grace behavior, renewal totals and provider responsibility are explicit and owner-approved. |
| Impala Loyalty Program Version 1 | MS2-LT-078 | NOT STARTED | Deterministic, capped, pharmacy-pooled earning/referral/redemption history and an owner-only renewal discount pass without unexplained coin changes. |
| Impala Community Version 1 | MS2-LT-079 | NOT STARTED | One pharmacy identity can safely post, comment, appreciate, report and be moderated under clear pharmacy-focused rules. |
| Demo Mode certification | MS2-LT-083 | NOT STARTED | The selected real 5–10-step walkthrough passes without hidden intervention, confusion, unacceptable delay or false data/functionality. |
| No launch-blocking regressions | MS2-LT-072 plus all protected prerequisites | READY FOR OWNER TEST | All automated architecture/contract/fixture/regression gates pass and the certified walkthrough shows no protected regression. |

**Launch Gate status: BLOCKED.** External production qualification and unimplemented mandatory launch work remain. No percentage is permitted.

## Locked improvements

### 1. Impala Loyalty Program Version 1 — Launch Critical

Impala Coins are in-app loyalty credit: not cryptocurrency, cash, tradable, transferable between unrelated pharmacies, user-purchased, or withdrawable.

Version 1 provides deterministic Learn & Earn rewards for meaningful first-time/productive workflows, unique pharmacy referral code/link attribution, pharmacy wallet balance, earning history, redemption history, progress to the next subscription discount, and renewal redemption showing coins used, discount received and remaining payable. Only the owner or an explicitly authorized billing administrator may redeem.

Rewards are pooled once per pharmacy. Staff contributions may be attributed individually, but extra phones or repeated observation cannot multiply value. Per-pharmacy eligibility, idempotency keys, genuine per-person contribution rules, daily/monthly caps and auditable explanations are mandatory. The business message is: **The more value you get from MS2.0 and the more you help it grow, the more it gives back to you.**

Advanced missions, badges, personalized challenges, seasonal campaigns, leaderboards and complex AI reward logic are Continuous Improvement.

### 2. Impala Community Version 1 — Launch Critical

Impala is a separate community area, never mixed into operational pharmacy chat. Onboarding assigns collision-safe sequential pharmacy/community IDs (`001`, `002`, `003`, …). Pharmacy identity is primary; permitted staff nicknames appear beneath it, for example `Mary · Impala Pharmacy 001`.

Deferred design-system direction: the owner selected the clear blue used by the catalog search-field clear icon as the future MS2.0 signature accent and the intended Impala Community identity accent. Preserve this request as a shared theme-token migration for the later UI/theming improvement programme; do not roll it out widget-by-widget or during the ordered MS2-LT-055 original sequence. Exact accessible token values and contrast states require dedicated owner validation before adoption.

Version 1 includes a pharmacy-focused feed, text/photo posts, questions/answers, appreciation, comments, business promotion, birthdays, MS2.0 usage milestones, referral recognition, clear rules, reporting, moderation, restriction and banning. Content remains centered on pharmacy operations, entrepreneurship, service, professional health discussion, motivation, celebrations, community support and business education.

Themes, streaks, AI prompts/missions, voice/video/live calls, events, mentorship, marketplace, regional groups, contact exchange/Impala Connect and community games are Continuous Improvement. Future owner community ideas remain under this improvement unless repository evidence places them elsewhere.

### 3. Multiuser Pharmacy Version 1 — Launch Critical

The owner creates the primary pharmacy and chooses single-user or multiuser; staff cannot self-select ownership. Secure invite links, QR codes or short codes let approved staff join the existing pharmacy without repeating onboarding. Fixed launch roles are Owner, Manager and Staff/Pharmacist/Cashier.

All authorized users share one pharmacy identity, catalog, stock, prices, suppliers, settings, operational truth, Impala wallet and Impala community identity. Individual attribution sits beneath pharmacy truth. Offline work queues safely; synchronization is idempotent; conflicts never silently overwrite valid work; visible states are local, waiting to sync, synchronizing, synchronized and needs review.

The owner can remove staff, disable lost devices, end sessions, view active devices/last activity, reset access, revoke invitations and control public posting. Historical attribution survives removal. Billing is by active staff seat rather than install count where commercially approved; replacement devices do not automatically consume a new paid seat. Included seats, additional-seat cost, expiry and grace/recovery rules must be explicit.

MS2-LT-067-A is the narrow active foundation: an admin-protected QR/link activates the first owner once, the owner creates a private PIN, and later access uses registered phone plus PIN. Activation values are digest-only, PINs are uniquely salted strong hashes in the protected admin workbook, sessions are opaque secure cookies, and messaging/platform bearer access is not a customer dependency. This remains `IN PROGRESS` until the controlled HTTPS staging journey passes on the physical owner phone; it does not authorize later staff or multiuser cases.

Default owner reporting is **summary first; details only when requested**: total sales; cash, M-Pesa, credit and mixed totals; key stock alerts; important exceptions; and only action-needed items. Drill-down preserves staff, shift, device, payment, cancellation/refund, stock-edit, audit and unusual-activity detail. Payroll, advanced scheduling/approvals, custom roles, staff scoring and workforce analytics are Continuous Improvement.

### 4. Intelligence + Reliability — Launch Critical core

- **Offline-first:** sales, catalog/search, stock, editable cards and safe local summaries continue without internet; queued changes preserve order/attribution, deduplicate, surface conflicts and synchronize automatically. Internet-dependent community, calls, remote AI/referrals and cloud billing show a truthful offline state.
- **Low-data/resource/desktop:** measure session bytes, background traffic, request count/size, response and recovery time, queue safety, battery observations, memory, heat, suspension/restart, polling and AI/API calls on weak networks, older phones and desktop/laptop layouts. Do not claim unsupported “100%” reliability.
- **Multi-medicine photo onboarding:** detect distinct packs, show one compact expandable review list, extract only readable name/strength/form/unit/pack/manufacturer/barcode/batch/expiry/price fields, mark uncertainty, deduplicate, and reuse the shared editable-card/catalog/Source Brain deterministic-first boundary.
- **Daily intelligent assistant:** a separate neutral assistant gives a concise morning recap/actions and evening summary with one feedback question. It does not assume religion, politics, gender, hardship or culture. Feedback retains necessary pharmacy context, minimizes sensitive data, groups repetition and suggests changes; only safe display preferences may apply automatically. Engineering, pricing, permission, workflow and data changes always require owner approval and repository-first validation.

Advanced personalization/prediction/OCR/vision, complex AI plans, automatic feature implementation and advanced feedback/behavior adaptation are Continuous Improvement. The permanent execution order remains deterministic local logic → Pharmacy Catalog → Source Brain → local OCR → verified cache → justified AI last.

## Demo Mode roadmap and certification

Demo Mode uses real MS2.0 behavior and truthful seed/setup state; it never substitutes fake functionality. The target certified route is nine concise demonstrations:

1. Open the pharmacy and compact catalog.
2. Add/review several medicines from one photo.
3. Find a medicine by search or barcode.
4. Record one fast sale and show the stock change.
5. Correct one field by voice in the shared editable card.
6. Record one offline sale, then show safe synchronization.
7. Join one staff user by QR/link and show the shared catalog.
8. Show Impala Coins progress and the truthful renewal discount.
9. Show the Impala pharmacy identity/community, then the concise owner report.

Certification requires plain-language prompts, no developer console/manual storage edits, real deterministic workflows, clear offline/cloud boundaries, acceptable measured response times, reversible demo preparation, no protected regression, and direct answers to: Is it faster? easier? reliable? usable by staff? usable with poor internet? worth the monthly subscription?

## Dependency map and milestone order

| Order | Milestone | Dependencies | Owner-visible value and reason |
|---:|---|---|---|
| Complete | MS2-LT-054 payment failure/cancellation notification | 052–053 protected | PASS / PROTECTED from Septrin 12-to-12 owner evidence; preserve without routine retest. |
| 2 | Exact transaction truth | 049 → 050 → 055 → 056 | Prevents unit/price, payment-mode, refund and reversal errors before new account layers amplify them. |
| 3 | Persistence, access and provisioning foundation | 059 + 067 + 068 + 069 + 072 + 073 | Establishes isolated durable data, permission, audit, privacy and regression boundaries. |
| 4 | Multiuser Pharmacy V1 | 077 after 059, 066–067, 073 | Shared catalog/stock, invitations, fixed roles, attribution and consolidated reporting are prerequisites for pooled loyalty/community identity. |
| 5 | Subscription and billing clarity | 084 with 050, 067, 074 | Makes seats, device replacement, renewal and provider limits explicit before loyalty redemption. |
| 6 | Impala Loyalty V1 | 078 after 077, 084 | Adds deterministic pooled rewards and renewal value without per-device abuse. |
| 7 | Impala Community V1 | 079 after 067, 077 | Adds one moderated pharmacy identity only after roles and posting authority exist. |
| 8 | Reliability qualification | 080 after 020, 061, 066, 072 | Measures weak-network, resource and desktop behavior at the shared sync/runtime roots. |
| 9 | Multi-medicine photo onboarding | 081 after 008–011, 031, 035–036 | Extends protected review roots with compact multi-pack acquisition and uncertainty safety. |
| 10 | Daily assistant V1 | 082 after 021, 024–025 | Adds concise deterministic morning/evening value from already protected operational truth. |
| 11 | External launch qualification | 074–076 | Closes provider, legal/regulatory and production recovery/scale blockers with external evidence. |
| 12 | Demo Mode certification | 083 after all mandatory Launch Gate rows | Certifies the smallest truthful walkthrough; only then may launch be declared ready. |

Only one milestone may be active. After automated validation, Codex provides exactly one focused owner live test and waits for evidence.

## Legacy incomplete-checkpoint migration

Migration count: **33** (31 active non-protected checkpoints plus 2 evidence-backed deprecated compatibility checkpoints).

| Checkpoint | New class | Reason |
|---|---|---|
| MS2-LT-022 Direct analytics commands | Demo Mode | Useful concise owner proof, but protected reports already satisfy core launch reporting. |
| MS2-LT-023 Decision-support summary | Continuous Improvement | Helpful interpretation beyond the protected truthful report baseline. |
| MS2-LT-026 Missed-demand intelligence | Continuous Improvement | Valuable optimization, not required for safe first operations. |
| MS2-LT-027 Movement intelligence | Continuous Improvement | Advanced inventory optimization depends on exact unit truth. |
| MS2-LT-028 Demand-risk prediction | Continuous Improvement | Predictive capability is explicitly advanced intelligence. |
| MS2-LT-029 Reorder/supplier intelligence | Continuous Improvement | Supplier automation follows safe core stock and launch. |
| MS2-LT-030 Dashboard/action prioritization | Continuous Improvement | Protected reports/alerts provide a sufficient first-launch baseline. |
| MS2-LT-033 Adaptive shorthand learning | Continuous Improvement | Manual/local matching is protected; adaptive learning can mature later. |
| MS2-LT-034 Operational memory | Continuous Improvement | Reuse convenience does not block safe core operations. |
| MS2-LT-035 Trusted-result/cache reuse | Launch Critical | Multi-photo and low-data behavior require safe verified reuse before AI. |
| MS2-LT-036 Media classification/routing | Launch Critical | The demo photo/scanning path must route evidence safely and truthfully. |
| MS2-LT-037 AI fallback approval boundary | Launch Critical | Any unresolved fallback must fail closed with privacy/cost controls before launch. |
| MS2-LT-038 Learning effectiveness/rollback | Continuous Improvement | Advanced learning measurement follows the focused deterministic launch. |
| MS2-LT-048 Future operational documents | Continuous Improvement | Protected exports cover first-launch owner needs. |
| MS2-LT-049 Exact form/unit/pack/price truth | Launch Critical | Incorrect unit or price can corrupt stock, sales and billing. |
| MS2-LT-050 Payment modes/splits/discounts | Launch Critical | Launch transactions must represent real pharmacy payment truth. |
| MS2-LT-054 Payment failure/cancellation notification | Launch Critical | Failure must not alter stock/paid truth and must remain visibly actionable. |
| MS2-LT-055 Refunds/returns/credits | Launch Critical | Real pharmacies need linked, non-destructive correction paths. |
| MS2-LT-056 Undo/reversal reconciliation | Launch Critical | Stock, finance, reports and audit must reconcile exactly once. |
| MS2-LT-057 Supplier/restock payments | Continuous Improvement | Supplier settlement follows launch sales/payment correctness. |
| MS2-LT-059 Google Sheets persistence | Launch Critical | Shared and recoverable pharmacy truth requires qualified persistence. |
| MS2-LT-060 WhatsApp/Baileys optional channel | Continuous Improvement | Main App is the launch proof surface; this remains optional. |
| MS2-LT-062 Meta/Twilio legacy channel | Continuous Improvement | Evidence-backed deprecated compatibility remains preserved, not active launch work. |
| MS2-LT-063 Local WhatsApp Web legacy bridge | Continuous Improvement | Evidence-backed deprecated compatibility remains preserved, not active launch work. |
| MS2-LT-064 Share/email delivery | Continuous Improvement | Device downloads already cover first launch; delivery automation may follow. |
| MS2-LT-067 Authentication/roles/access | Launch Critical | Multiuser and owner-only billing/community controls cannot be safe without it. |
| MS2-LT-068 Privacy/compliance safeguards | Launch Critical | Launch data and exports require fail-closed privacy/retention controls. |
| MS2-LT-069 Product-secrecy/quiet UI | Launch Critical | Pharmacy demos must expose necessary truth without internal implementation noise. |
| MS2-LT-072 Architecture/regression gate | Launch Critical | Protected behavior must remain intact through every launch milestone. |
| MS2-LT-073 Autonomous provisioning | Launch Critical | A new pharmacy must recover from failed setup without engineering intervention. |
| MS2-LT-074 Payment-provider qualification | Launch Critical | Production payment/subscription claims require official provider evidence. |
| MS2-LT-075 Legal/regulatory qualification | Launch Critical | Professional Kenya launch review is an explicit external safety gate. |
| MS2-LT-076 Channel/scale/recovery qualification | Launch Critical | Backup, recovery, monitoring and multi-pharmacy scale are launch safety requirements. |

## Continuous Improvement backlog

The primary legacy backlog is the Continuous Improvement set in the migration table. Locked deferred scope also includes advanced loyalty missions/badges/challenges/campaigns/leaderboards; community themes/streaks/prompts/calls/events/mentorship/marketplace/regional groups/Impala Connect/games; payroll/scheduling/custom roles/staff scoring/workforce analytics; and advanced personalization, prediction, OCR/vision, complex AI plans, automated feature changes and behavioral intelligence.

All backlog work keeps its canonical checkpoint/evidence relationship. New approved owner-visible work must be registered in the master before implementation.

## Active launch priority

Permanent launch interaction gate: every supported operational command follows **Voice first → fast tap/action second → typing last**, uses one shared deterministic router after transcription, retains typed fallback and stays within three steps where possible. Launch evidence and future live-test instructions must demonstrate voice first when the platform allows it; separate voice-only workflow logic and unnecessary AI routing fail this gate.

**MS2-LT-055 — Refunds, returns and credits**

Status: `IMPLEMENTED — STAGED OWNER VALIDATION`. Original MS2-LT-055 cases 055-A through 055-F are owner-verified passed/frozen/protected. The 2026-08-02 055-F evidence proves one offline Return persisted locally, restored stock once, retained reciprocal immutable linkage and survived a single reconnect/sync without duplication; the historical device queue synchronized from 53 to 0. The original programme is complete. MS2-LT-055 remains active only for the approved post-original shared status-card/layout and deterministic direct-command programme, tested one case at a time before checkpoint closure.

Post-original 055-G / Direct Command 1 is owner-verified passed/frozen/protected: direct Sale 1/Sale 4 navigation reuses persisted immutable ledger lookup, preserves linked adjustments and causes no mutation. Later 055 work inherits the permanent voice-first gate and remains owner-screenshot-gated one case at a time.
