# MS2.0 API-token and execution policy

Canonical validation authority: `../../MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`.

Token policy: **ACTIVE**

## Product execution order

Every operational workflow must use this order:

1. Local deterministic logic.
2. Pharmacy Catalog.
3. Source Brain.
4. Local OCR.
5. Verified local cache.
6. AI or an external LLM only as a documented, justified last resort.

No routine operational workflow may invoke an LLM without a repository-recorded engineering justification, explicit approved boundary, privacy scope, fallback behavior and token expectation.

## Codex execution discipline

- Inspect targeted authoritative files first.
- Avoid rereading large files when a focused section is sufficient.
- Do not re-explain protected history or reproduce the master sequence in routine reports.
- Prefer focused checks plus minimum safety coverage over unrelated broad suites.
- Avoid duplicate searches, summaries, speculative loops and parallel implementations.
- Reuse existing shared roots and Engineering Memory.
- Keep routine owner reports compact.
- Stop and report a real blocker instead of consuming tokens indefinitely.
- Recommend a CODEX BRIDGE when a chat becomes slow, context-heavy, repetitive or abnormally long for focused work.

Every synchronization gate, CODEX BRIDGE and CHATGPT BRIDGE must state `Token policy: ACTIVE` and reference this file without copying its historical explanation.
