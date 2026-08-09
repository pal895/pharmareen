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
