# Transaction Completion Engine

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

## Completion and queue rules

- A request awaiting confirmation enters the Payment Queue.
- The owner can immediately serve the next customer.
- Confirmed completion updates sale, receipt, stock, reports and notifications once.
- Transaction IDs and provider callback keys are idempotent.
- A pending, failed or cancelled payment cannot mutate completed-sale stock or finance.
- Operational Confidence may preselect or suggest an action but never silently execute a financial action.

## Identity, numbering and undo

- Every transaction has a globally unique permanent ID.
- Completed sales also receive `Sale 1`, `Sale 2`, and so on for the pharmacy business day.
- Daily numbering resets at the configured business-day boundary.
- Undo uses the visible sale number but creates a linked reversal; it never deletes history.
- Undo/reversal reconciliation must cover stock, finance, receipt, reports, transaction history and audit history.

## Subscription reuse

Monthly subscription renewal uses this same TCE and adapter boundary. It must not become a second payment system.

## Engineering discipline

Classify friction before implementation: Product Decision, Domain Logic, Shared Service, Input Interpretation, Source Brain, Pharmacy Catalog, Transaction Completion Engine, Navigation, Rendering, Data Integrity, Security, Integration or UI Flow. Fix the earliest responsible reusable layer and protect every dependent workflow.

## Current implementation boundary

The repository contains the local TCE foundation, Cash and Manual adapters, a production-shaped Simulator adapter, pending-payment queue state, daily numbering, idempotent provider events, duplicate-callback protection and linked undo/reversal records. Fast Record is wired into existing confirmed sales. Setup controls, owner-facing Request & Verify queue screens, reconciliation hooks and official provider adapters remain future live-tested stages.
