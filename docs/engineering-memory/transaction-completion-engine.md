# Transaction Completion Engine

Canonical live-validation authority: `../../MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`. This memory defines payment architecture and evidence, not checkpoint order.

## Permanent decision

MS2.0 completes financial and operational transactions through one Transaction Completion Engine (TCE). Payment is one part of transaction completion, not a separate product engine.

The TCE is the shared completion boundary for:

- medicine sales;
- supplier and restock payments;
- refunds, reversals and credits;
- monthly subscriptions;
- future insurance settlements and branch transfers.

No workflow may communicate directly with a payment provider. It must use a Payment Adapter registered with the TCE.

## Completion modes

Each pharmacy can choose in Setup:

- `Always Fast Record`: record the owner-confirmed transaction immediately;
- `Always Request & Verify`: request payment, continue serving, and complete after provider confirmation;
- `Always Ask`: choose per transaction.

Fast Record is the initial compatibility mode. Request & Verify must never block serving the next customer.

## Payment adapters and simulator

Supported adapter roles are:

- Cash;
- Manual payment recording;
- Simulator;
- future official M-PESA;
- future official card providers.

The simulator is mandatory before official-provider testing and reproduces success, timeout, cancellation, wrong PIN, insufficient balance, delayed confirmation, duplicate callback, failed payment, refund and reversal.

Changing adapters must not redesign sales, subscriptions, stock, receipts, reports or audit history.

## Merchant ownership and tenant isolation

For pharmacy customer sales, each pharmacy owns and directly receives money through its authorized Till, PayBill or other supported merchant account. MS2.0 coordinates the transaction and authenticated status; it must not hold, pool, reroute or onward-settle unrelated pharmacies' customer funds.

Pharmacy A's merchant configuration must never be usable by Pharmacy B. Merchant credentials must never appear in client-side code, logs, chat, Google Sheets or source control. Secrets require encrypted backend storage, rotation, revocation and strict tenant/environment isolation.

MS2.0 subscriptions use a separately authorized MS2.0 merchant account. A pharmacy merchant account must never collect MS2.0 subscription money.

## Future production connection models

The adapter architecture supports two models without changing the TCE:

1. **Direct merchant connection:** each pharmacy securely authorizes its own approved merchant integration, shortcode and credentials. This is the safest initial assumption pending provider confirmation.
2. **Approved platform or aggregator connection:** a future explicitly authorized Safaricom or licensed-partner arrangement may support centralized onboarding or delegated processing. This remains disabled until commercial, technical and regulatory approval exists.

MS2.0 does not claim aggregator status and must not simulate approval, pool pharmacy funds or use its subscription merchant account for unrelated pharmacy sales.

## Payment Adapter contract

Where supported, adapters expose:

- connect and disconnect merchant;
- validate merchant configuration;
- initiate a payment request;
- query status;
- receive and authenticate callbacks;
- expire or cancel a request;
- reconcile a transaction;
- process or record a refund;
- report provider capabilities.

Every request binds pharmacy tenant, branch, sale, receiving merchant account, amount, customer number where required, idempotency key and internal transaction reference. The adapter rejects cross-tenant, wrong-environment, wrong-merchant and mismatched-amount events.

## Provider capabilities

Capabilities are explicit per connected account. They include request-to-pay, verified callback, automatic refund, transaction lookup, required customer reference, merchant-owned credentials and offline completion. Till, PayBill, Pochi, Send Money and card methods must not be treated as interchangeable.

The UI offers only supported actions. Unsupported electronic methods may remain as clearly labelled manual-recording methods and must never appear provider-verified.

## Future merchant onboarding

1. Choose payment methods.
2. Identify the pharmacy-owned merchant account.
3. Explain that the pharmacy remains owner and direct recipient.
4. Authorize through a secure backend flow.
5. Validate merchant configuration.
6. Complete an appropriate sandbox or controlled low-value validation.
7. Store provider capabilities for that tenant.
8. Enable Request & Verify only after successful connection.
9. Keep Fast Record for supported manual workflows.
10. Allow disconnection without damaging historical records.

Owners must never paste production API secrets into chat or an ordinary client-side form.

## Completion and queue rules

- A request awaiting confirmation enters the Payment Queue.
- The owner can immediately serve the next customer.
- Confirmed completion updates sale, receipt, stock, reports and notifications once.
- Transaction IDs and provider callback keys are idempotent.
- A pending, failed or cancelled payment cannot mutate completed-sale stock or finance.
- Operational Confidence may preselect or suggest an action but never silently execute a financial action.
- Operational Confidence must never silently switch the receiving merchant, reuse another tenant's credentials, initiate a request without required owner action, mark an electronic payment paid without authenticated confirmation, learn raw secrets or bypass provider capabilities.
- Any receiving-account change is highly visible and requires confirmation.

## Identity, numbering and undo

- Every transaction has a globally unique permanent ID.
- Completed sales also receive `Sale 1`, `Sale 2`, and so on for the pharmacy business day.
- Daily numbering resets at the configured business-day boundary.
- Undo uses the visible sale number but creates a linked reversal; it never deletes history.
- Undo/reversal reconciliation must cover stock, finance, receipt, reports, transaction history and audit history.

## Subscription reuse

Monthly subscription renewal uses this same TCE and adapter boundary. It must not become a second payment system.

The transaction purpose and receiving merchant remain explicit: pharmacy sales use the pharmacy-owned account; subscriptions use the MS2.0-owned account.

## Simulator tenant scenarios

Before production integration, the simulator must cover isolated Pharmacy A Till, isolated Pharmacy B PayBill, MS2.0 subscription merchant, cross-tenant shortcode rejection, missing/revoked credentials, wrong environment, wrong-tenant callback, duplicate callback, mismatched amount, mismatched merchant, success, failure, delay and manual recording. No real credentials or money are required.

## Unresolved production question

> Does Safaricom support one approved multi-tenant SaaS platform integration through which independently owned pharmacies can authorize their own Tills or PayBills, or must every pharmacy complete a separate Daraja production application?

This does not block simulator or TCE development. It is not verified for production and requires direct confirmation from Safaricom or an authorized provider before choosing the final onboarding model. The repository must support either confirmed answer and must not guess.

## Engineering discipline

Classify friction before implementation: Product Decision, Domain Logic, Shared Service, Input Interpretation, Source Brain, Pharmacy Catalog, Transaction Completion Engine, Navigation, Rendering, Data Integrity, Security, Integration or UI Flow. Fix the earliest responsible reusable layer and protect every dependent workflow.

## Current implementation boundary

The repository contains the local single-context TCE foundation, Cash and Manual adapters, a production-shaped Simulator adapter, pending-payment queue state, daily numbering, idempotent provider events, duplicate-callback protection and linked undo/reversal records. Fast Record is wired into confirmed sales. Owners can select Fast Record or Request & Verify from a dedicated Payment Queue. In Request & Verify, non-cash sales use only the Simulator adapter, enter a non-blocking waiting queue, do not change stock while pending, and expose explicit simulated paid/failed controls. Confirmed pending stock application carries an idempotency marker so repeated callbacks cannot deduct twice. Tenant merchant onboarding, tenant-bound request fields, capability-driven provider UI, multi-tenant simulator scenarios, secure credential storage, reconciliation hooks and official provider adapters remain future live-tested stages. No production credentials or provider integration exist.

The 2026-07-18 navigation-protection live checkpoint passed: home retained MS2.0 Assistant, Notifications and Payment Queue with no redundant `SHOW ME` tile; the protected header icon opened all 35 saved medicines; closing caused no message, draft, approval, sale, catalog mutation, notification or waiting-payment change.

The 2026-07-18 quiet-concurrency live checkpoint also passed. Two waiting requests remained isolated, the second completed first without changing the first, each stock deduction occurred exactly once, the queue ended at zero, history and receipts remained truthful, and routine success created no Notification. Protected stock baselines are now Cefixime 23 and Losartan 37. This closes the current automatic-completion simulator live sequence; production provider work remains disabled future scope.

Sale numbers are daily display labels, not globally unique identifiers. They intentionally reset for each pharmacy business day; permanent transaction IDs remain the cross-day identity. Payment Queue history must therefore show the pharmacy day beside each sale label so `Sale 1` from different days is never presented as the same transaction.

Payment verification must expose the value being verified. A waiting request shows its expected amount with an explicit KES currency label. Recent history retains the pharmacy day, sale label, medicine, quantity, amount, payment method and status so the owner can distinguish similar daily sale numbers and audit what was completed without reopening another workspace.

Provider completion now enters one `providerEvent` boundary whether the event comes from the simulator or a future authenticated adapter. The boundary validates any supplied amount, pharmacy, branch, merchant-account and payment-request identity before changing state; duplicate keys are idempotent and terminal success or failure cannot be rewritten by a late out-of-order event. Concurrent requests remain independent. Simulator-origin events are rejected when the engine environment is production, and simulator controls are not rendered there. Confirmed completion applies deferred stock exactly once. Failure or cancellation applies no stock or paid receipt and creates a durable action-needed Notification. Production callback authentication and official provider adapters remain disabled future work.

Routine success stays calm: the normal receipt is the completion feedback. A concise remaining-count message appears only when another payment is still waiting. Failures and cancellations belong in Notifications rather than repeated operational chat messages.

Validation-plan reconciliation on 2026-07-28 places Payment Failure/Cancellation Action-Needed Notification immediately after the current shared-card viewport checkpoint. Official-provider validation remains a separate final production-hardening program after the functional and repository-defined audit programs. It includes direct confirmation of the merchant onboarding model, tenant-bound merchant/request identity, secure credentials, authenticated callbacks, reconciliation and official adapters; it remains disabled until the external provider gate is satisfied.
