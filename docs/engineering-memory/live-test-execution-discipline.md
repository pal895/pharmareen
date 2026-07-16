# Live-test execution discipline

These rules are permanent for every MS2.0 live-validation cycle.

## Exact and self-contained instructions

Every response must give the exact command, route, link, fixture filename, and ordered owner action required for the next checkpoint. Never write only “pull and restart,” “run again,” “download the fixture,” or similar shorthand. When Replit must pull and restart, provide the complete copy-paste command in that response. If no pull or restart is needed, explicitly say so.

Use this response structure consistently:

1. Result analyzed
2. Friction found
3. Root cause
4. Fix applied
5. Regression protection
6. Commit and push
7. REPLIT COMMAND
8. LIVE TEST
9. Expected result
10. Exact approval/save instruction
11. Next action after evidence

Before sending, confirm that the response includes the executable command, exact fixture, exact owner action, approval boundary, expected result, preserved catalog baseline, and requested next evidence.

## Speed with accuracy

Start from the current live-validation state, recent relevant commit diff, and directly affected shared components. Run focused tests first and only the protected regressions needed for the confirmed shared root. Do not repeatedly rediscover the repository, reread validated architecture, rerun unrelated suites, or expand scope after the root cause is confirmed and protected. Implement the smallest sufficient inspection and the broadest correct shared fix.

If investigation genuinely becomes extended, state the concrete blocker and narrow the work instead of silently expanding into speculative repository-wide analysis. Speed never overrides evidence, safety, honesty, or regression protection.

## Token discipline

Local-first, deterministic-first, and zero-token-first remain mandatory. Reuse Engineering Memory and validated findings. Avoid duplicate reasoning, duplicate tests, broad rereads, regeneration of known context, rebuilding from scratch, and implementation loops. AI or API-token use remains allowed only when the established architecture says it is necessary.

## Consistency

Preserve validated command conventions, fixtures, expected results, catalog baselines, approval boundaries, and evidence requests unless a concrete technical reason requires a documented change. Every live-test response must be operationally complete on its own.

## Cross-input and active-feature coverage

For equivalent owner intent, validate that typed, microphone, camera, photo-library, shelf-photo, invoice, file, barcode, Paste List, selection, and other supported sources converge on the same shared interpretation, validation, approval, mutation, catalog, stock, traceability, and saved-result rules. Preserve meaningful medicine form, strength, quantity, unit, pricing, payment where relevant, supplier, bonus, discount, batch, and expiry values across source boundaries.

Use one representative equivalence comparison when the shared root is already protected. Do not duplicate an entire workflow for every source. Separately validate responsibilities unique to a source, including permission, acquisition, file format, recognition, extraction, failure recovery, offline behavior, and result rendering.

Before considering a feature area complete, maintain coverage for:

1. Entry point.
2. Input source.
3. Shared processing root.
4. Source-specific responsibility.
5. Expected visible result.
6. Expected mutation or explicit no-mutation.
7. Approval boundary.
8. Offline behavior.
9. Token expectation.
10. Regression protection.
11. Prior partial/full shared coverage.
12. Smallest remaining live test.

When evidence differs between attempts, record the visible input, active card, timing, connectivity, and any device/browser sound separately. Do not infer that an unexpected sound comes from MS2.0 until its words and trigger are proven. Do not implement a medicine-, phrase-, screen-, or source-specific patch; trace drift to the earliest responsible shared root.
