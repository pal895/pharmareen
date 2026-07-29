# MS2.0 Launch Fixture and Automated-Test Plan

Authority: `../MS2.0_MASTER_LIVE_TEST_SEQUENCE.md` for checkpoint identity/status and `../docs/engineering-memory/launch-readiness-roadmap.md` for active priority.

Fixtures must be deterministic, synthetic, pharmacy-scoped, safe to commit and explicit about uncertainty. They may never contain production credentials, personal data or hidden AI/API dependencies. Existing protected fixtures remain unchanged.

## Required fixture families

| Milestone | Planned deterministic fixtures | Minimum automated proof |
|---|---|---|
| MS2-LT-054 payment failure/cancellation | One pending M-Pesa sale with recorded baseline stock/finance; failed and cancelled provider events; duplicate and late-success events | One durable unread notification per terminal outcome; no chat-noise entry; no stock/paid receipt mutation; persistence through notification rebuild; idempotent duplicate/late event handling |
| MS2-LT-049–056 exact transaction truth | Same medicine in multiple strengths/forms/units/packs; mixed payments; linked refund/return/reversal | No unit/price leakage; exact one-time stock/finance/report/audit effects |
| MS2-LT-077 multiuser | One pharmacy owner, manager, two staff, revoked invite, lost device and conflicting offline sale | Fixed-role authorization; shared catalog/stock; attribution; revocation; conflict visibility; idempotent sync; consolidated summary plus drill-down |
| MS2-LT-078 loyalty | Eligible/ineligible first-use events, referral, repeated staff/device events, caps and renewal redemption | Pharmacy pooling; deterministic explanation; no multiplication; owner-only redemption; exact coin/discount/payable history |
| MS2-LT-079 community | Two pharmacies, staff nicknames, photo/question/comment/appreciation/report/moderation cases | Collision-safe identity; pharmacy-first attribution; isolation; posting permission; report/restrict/ban lifecycle |
| MS2-LT-080 reliability | Recorded request/byte envelopes, interrupted sync, suspension/restart and viewport matrix | Budget calculation; no unnecessary polling/AI; queue recovery; supported mobile/desktop layouts |
| MS2-LT-081 multi-photo | One image with several readable packs, duplicate pack, uncertain field and unknown medicine | Distinct detection; compact list; provenance/uncertainty; no silent critical save; canonical dedupe; shared-card reuse |
| MS2-LT-082 daily assistant | Morning/evening operational snapshots, no-data day, sensitive free text and repeated feedback | Neutral concise summary; deterministic source truth; one feedback question; minimization/grouping; no automatic product mutation |
| MS2-LT-083 Demo Mode | Reversible demo pharmacy snapshot and certified action/evidence manifest | Real workflows only; reset safety; no hidden intervention; timing/evidence capture; protected regression gate |
| MS2-LT-084 billing clarity | Single/multiuser packages, included/additional seats, lost-device replacement, expiry/grace and coin redemption | Exact displayed rules/totals; no install-count charge; owner-only billing; provider/external limits stated truthfully |

## Test discipline

For each milestone:

1. Add focused service tests at the shared owning boundary.
2. Add one UI/adapter verifier only where presentation or routing is part of the contract.
3. Run the focused suite, architecture check, validation-contract check and minimum protected regression coverage.
4. Record measured network/resource evidence for MS2-LT-080; never substitute a claim.
5. Keep owner validation at `READY FOR OWNER TEST` until explicit owner evidence exists.
6. Present one live test only, then stop.
