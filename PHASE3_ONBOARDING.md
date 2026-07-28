# PharMareen Phase 3 Onboarding

Historical phase evidence only. Canonical MS2.0 checkpoint order and status live in `MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`.

Phase 3 adds pharmacy database onboarding without breaking the WhatsApp bridge.

## Admin Page

Open:

```text
/admin/onboard
```

Use it to:

- Create one pharmacy.
- Bulk-create many pharmacies.
- View onboarded pharmacies.
- Open the generated spreadsheet URL.

## API Endpoints

Create one pharmacy:

```http
POST /admin/create-pharmacy
```

Bulk create:

```http
POST /admin/create-pharmacies-bulk
```

List pharmacies:

```http
GET /admin/pharmacies
```

Show one pharmacy:

```http
GET /admin/pharmacy/{pharmacy_id}
```

Photo onboarding placeholder:

```http
POST /admin/photo-onboard-placeholder
```

## Google Sheets

Set these environment variables:

```text
GOOGLE_SHEETS_CREDENTIALS={service account JSON}
PHARMAREEN_ADMIN_SHEET_ID=optional admin registry sheet
PHARMAREEN_DEFAULT_PHARMACY_ID=optional default pharmacy
```

If `PHARMAREEN_ADMIN_SHEET_ID` is present, new pharmacy records are appended to its `Pharmacies` tab.

If Google Sheets is not configured, PharMareen falls back to:

```text
data/pharmacies_registry.json
```

This keeps onboarding testable without crashing.

## New Pharmacy Tabs

Each live pharmacy database gets:

- Inventory
- Sales
- Restocks
- Reports
- Settings
- Suppliers
- Supplier_Prices
- Low_Stock
- Audit_Log

The system also creates legacy compatibility tabs used by the current WhatsApp commands:

- Master_Stock
- Daily_Log
- Daily_Reports
- Transactions
- Request_Log

## WhatsApp Speed Rule

WhatsApp messages remain independent and fast:

1. Receive message.
2. Parse command.
3. Read/write required rows.
4. Reply.

No long chat history is sent to AI.
