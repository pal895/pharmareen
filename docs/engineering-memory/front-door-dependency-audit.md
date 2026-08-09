# MS2.0 beginning/front-door dependency audit

Date: 2026-08-09

Authority remains `MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`. This audit changes implementation order only. It does not change checkpoint IDs, prerequisites, acceptance criteria, status, owner-evidence requirements or Launch Gate classification.

## Repository-defined boundary

The beginning/front-door layer is the shared tenant entry architecture materially required by:

- MS2-LT-059 and 068: durable isolated state resolution, legitimate established-pharmacy recovery and fail-closed privacy.
- MS2-LT-067: protected first-owner activation, returning-owner authentication and tenant-bound sessions.
- MS2-LT-069 and 072: quiet customer entry plus architecture/regression protection.
- MS2-LT-073 and 076: autonomous provisioning, unified channel/QR/share-link adapters, failed-onboarding recovery, verified account recovery and production scale/incident recovery.
- MS2-LT-077: owner-approved staff invitations, fixed roles, shared tenant truth, attribution, device/session controls and owner-phone change.
- MS2-LT-078, 079 and 084: pharmacy-pooled loyalty identity, one pharmacy/community identity, posting/billing authority, seats and device replacement truth.
- MS2-LT-080: startup, offline/reconnect, suspension/restart and low-data state resolution.
- MS2-LT-083: real demo entry, staff QR/link join and shared catalog.

MS2-LT-081 and 082 consume established operational truth after entry but do not independently require a front-door implementation. Their original future tests remain unchanged.

## Shared contract and implementation order

1. Resolve a trusted request-scoped pharmacy and authenticate one actor.
2. Resolve durable pharmacy state before rendering onboarding or operations.
3. Fail closed when tenant, actor, role or durable state is unavailable.
4. Resume an established pharmacy directly. Never infer `new pharmacy` from an empty or failed state read.
5. If an authenticated owner has an empty tenant, require explicit restore-versus-genuinely-new classification. Staff cannot create or recover a tenant.
6. Feed authenticated channel, QR and share-link adapters into one short-lived signed tenant context. Reject tamper, expiry, mismatch and replay at durable acceptance.
7. Extend that tenant root with fixed memberships, attribution, invitations, devices, session revocation and owner-phone recovery without changing pharmacy identity.
8. Allocate one pharmacy/community identity and pooled loyalty/billing authority only after tenant and membership truth exist.
9. Preserve truthful offline/startup states and idempotent synchronization; cloud-only entry actions remain visibly unavailable offline.
10. Certify the existing Demo Mode route only at MS2-LT-083 after its authoritative prerequisites pass.

## Protection and pending evidence

Protected onboarding and MS2-LT-067-A remain closed. Zuri must not repeat setup. Checkpoints 068, 073, 076–080, 083 and 084 remain pending at their existing acceptance boundaries. Bringing their shared entry foundation forward is automated implementation evidence only and cannot mark them PASS.

The integrated contract is `app/front_door.py`, durably backed by `app/services/front_door_persistence.py`. It defines explicit entry states; new-versus-recovery classification; trusted offline resume; fixed roles; owner/staff membership; one-use invitation/QR/link entry; device binding, replacement and revocation; staff removal; verified owner-phone and account recovery transitions; disabled-by-default device-bound Quick PIN trust; failed-provisioning resume; versioned owner legal/privacy acceptance; collision-safe pharmacy/community identity; pharmacy-pooled Loyalty wallet, referral identity and one-time signed referral attribution; and seat/subscription/billing authority that does not count installs as seats. Main App consumes the decision through authenticated operations bootstrap. Setup cards are removed whenever durable resolution is unavailable or the tenant still needs explicit restore/new classification.

Every remaining Master checkpoint was audited, including Launch Critical, Demo Mode and Continuous Improvement entries. Checkpoints 022–048, 060, 064, 068–076 and 081–082 either consume an already resolved pharmacy/actor or do not introduce another entry identity. Their implementation cannot require a new front-door state model. Checkpoints 077–080, 083 and 084 consume the implemented membership, identity, device, offline-start, community, loyalty/referral and billing roots. Deeper transactions, feeds, rewards, resource measurement, package decisions and external qualification remain at their existing checkpoints. No remaining authoritative checkpoint requires an unimplemented beginning/front-door dependency.

The canonical owner actor is derived once from the trusted registry: an explicit provisioned owner ID when present, otherwise `owner_<normalized-registry-phone>`. Credentials, sessions, authenticated bootstrap and durable front-door membership use that same value. The one supported pre-canonical migration recognizes only the exact normalized phone-key owner form with a matching stored phone digest and valid active owner membership, rewrites all nested authority references atomically, and rejects every other mismatch.

## Owner-approved physical grouping

The 2026-08-09 execution correction groups the remaining entry-dependent physical slices without changing the Master: MS2-LT-060, 073, 076–080 and 084. MS2-LT-067 and the entry prerequisites already protected by MS2-LT-002, 059, 061, 065, 066, 070 and 071 are skipped absent regression; MS2-LT-072 remains automated. Compliance-version acceptance travels with new provisioning but does not replace export checkpoint 068 or professional checkpoint 075. The grouped run may establish entry evidence for checkpoints 078–080 and 084, but those checkpoints remain pending until their unchanged full Loyalty, Community, reliability and commercial acceptance boundaries pass.

The next implementation boundary is a generic customer-visible, verified new-pharmacy route that creates one isolated registry tenant, hands the same canonical registry owner into durable owner activation and front-door initialization, resumes failed provisioning safely and exposes no operator-only step. Existing durable pharmacies and credentials are never cleared or relabelled to manufacture this test state. Established/legacy recovery remains implemented and protected for its genuine later evidence boundary.

That internal boundary is now implemented through `app/front_door_workflows.py` and the `/api/ms20/front-door/*`, `/main-app/new-pharmacy`, `/main-app/join` and `/main-app/access` surfaces. Verified channel context, registry, owner credential/session, front-door membership, staff session/device state, operations bootstrap actor attribution, Community/Loyalty identity and billing authority converge on the same pharmacy ID. Secret-like values remain raw only on the client/request boundary; durable front-door state stores hashes/digests and bounded authority/audit data. Unknown, expired, replayed, cross-pharmacy, wrong-device, removed-member and unqualified-billing states fail closed.

## Direct customer entry clarification (2026-08-09)

The canonical web/PWA and future packaged-app entry is now `/start`: the owner opens MS2.0, supplies a phone, receives a six-digit verification code through the configured delivery adapter, verifies inside MS2.0, and continues into the existing one-use provisioning boundary. The customer neither initiates a WhatsApp conversation nor sees channel, provisioning, registry or developer concepts. `/landing` and the install manifest converge on `/start`; existing authenticated WhatsApp handoffs remain compatible as an optional adapter.

Verification challenges are durably digest-only, expiring, attempt-bounded, replay-safe and throttled. The verified phone is browser-session-prefilled into provisioning and remains server-bound to the signed one-use context. One verified identity may own more than one isolated pharmacy: durable credentials are keyed by pharmacy plus phone, while unrouted phone-only PIN sign-in fails closed when ambiguous. This removes the artificial second-phone requirement without weakening tenant sessions or established-pharmacy recovery. Staff share links retain the same signed, role-bound, one-use invitation contract. The APIs are presentation-independent for a later packaged client.
