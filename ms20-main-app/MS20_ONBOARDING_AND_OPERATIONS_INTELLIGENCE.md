# MS2.0 Onboarding And Operations Intelligence

Updated: 2026-07-10

This document records the current Main App direction after the messaging-first UI work and the local-first onboarding expansion.

## Product Rule

MS2.0 is a Pharmacy Operating Intelligence Platform. The Main App is the product surface. WhatsApp/Baileys remains preserved as an optional external channel adapter and is not part of the current live-test phase.

The first real workflow for a new pharmacy is medicine onboarding, not a sale demo.

## Owner Flow

Fresh owner flow:

1. Open MS2.0.
2. Tap the MS2.0 Assistant conversation.
3. Complete setup.
4. Add medicines by invoice/photo, scan, paste, CSV/text file, or sale-time fallback.
5. Review/edit.
6. Approve.

Daily sale tests resume only after the pharmacy catalog has approved medicines.

## Intelligence Separation

MS2.0 keeps four layers separate:

- Global Source Brain: shared medicine names, forms, units, aliases, and common packaging knowledge.
- Pharmacy Catalog: private stocked medicines, prices, stock, aliases, barcode, shelf, batches, expiry, supplier, and confirmed scan signatures.
- Global Brain Candidates: unknown medicines with evidence waiting for controlled promotion.
- Pharmacy Learning: local shorthand, aliases, supplier patterns, scan corrections, and owner preferences.

Do not promote owner typos or one-off local names directly into the source brain.

## Onboarding Methods

Supported in the Main App presentation/adapters layer:

- Invoice/photo: review-first InvoiceCard. Real OCR/PDF extraction remains adapter-ready, not falsely complete.
- Medicine/shelf/drawer/stockroom scan: VisualScanCard and PhotoReviewCard with barcode, batch, expiry, supplier, shelf, and price fields.
- Bulk paste: deterministic parsing into CatalogImportCard.
- CSV/text/POS export: deterministic parsing and mapping into CatalogImportCard. Binary Excel mapping is reserved for the adapter path.
- Add while selling: MedicineMatchCard saves a missing medicine locally, records the sale, and allows repeat sales without re-entering the price.

## Token Control

Normal operations remain zero-token:

- known sales
- catalog lookup
- source brain lookup
- barcode-ready scans
- CSV/text import
- bulk paste import
- stock/expiry notifications
- report and document export cards
- local text-to-speech read aloud

For photos/documents the intended order is:

1. local fingerprint
2. exact duplicate lookup
3. near duplicate lookup where practical
4. previous confirmed result lookup
5. pharmacy catalog lookup
6. source brain lookup
7. barcode lookup
8. supplier template lookup
9. local visual signature lookup
10. deterministic extraction
11. AI final fallback only when explicitly needed

The current Main App does not call OpenAI/API.

## Expiry And Batch

Onboarding cards now include optional batch and expiry fields. When provided, the catalog stores batch records with quantity, supplier, and expiry where available.

The Digital Operations Assistant creates local expiry notifications for expired, 7-day, 30-day, 60-day, and 90-day windows.

## Documents And Downloads

Current document support:

- CSV pharmacy catalog export
- bulk-paste template download
- DocumentExportCard after catalog approval

Reserved adapter path:

- PDF export
- Excel binary import/export
- purchase orders
- goods received notes
- supplier reports
- expiry reports
- reconciliation reports

These should generate from stored pharmacy data, not from manual technical formatting.

## Operations Chat And Notifications

The home has separate workspaces:

- MS2.0 Assistant: operations chat for setup, sales, scans, invoices, reports, corrections, and approvals.
- Notifications: persistent Digital Operations Assistant alerts.

Notifications must not interrupt Operations Chat. Successful sales stay in Operations Chat only and do not create notification noise.

## Digital Operations Assistant

The current assistant is deterministic and local:

- catalog needed
- low stock
- out of stock
- expiry windows
- scan/import pending review

Future rules can add missed demand, fast movers, slow movers, supplier order suggestions, finance reconciliation, and report readiness without using AI.

## Current Live-Test Pause

The original paused sale test was:

```text
Test 1.4: Panadol 2 cash
```

That test remains paused.

Replacement next test:

```text
Onboarding Test A.1: open MS2.0 Assistant and confirm the owner sees onboarding/catalog choices before any sale test.
```

After onboarding works and at least one medicine is approved into the pharmacy catalog, resume sale tests from the paused point.
