# MS2.0 Pharmacy Operating Intelligence Platform

## Permanent Production Sales Card standard

MS2.0 has exactly one authoritative Production Sales Card. Typed sales, voice sales, review/correction, payment verification, Payment Queue, failure recovery, notifications and future sale fixtures must use the shared `SaleCard` model in `ms20-main-app/src/services/productionSaleCard.js` and its single renderer in `ms20-main-app/src/app.js`. `VoiceReviewCard` and bespoke queue sale cards are retired.

Its permanent presentation is compact and progressive: the default cream Fast action surface contains only approval facts and actions; Stock & details and Traceability remain one tap away; full editable inputs appear only after Correct. Every Sale correction field uses the Catalog-proven contextual Mic pattern and shared voice-capture root.

Implementation handoffs stay short: what changed, commit hash, one combined Replit command, one focused owner live test, expected result, then wait for screenshots. Detailed engineering history belongs in repository documentation.

Inline editable/review-card updates must preserve the active card viewport. They never invoke chat-bottom auto-scroll or focus the composer; genuine appended conversation messages retain normal auto-scroll. This is one shared render/anchor rule, not a Sales- or Catalog-only patch.

The first view prioritizes canonical medicine, exact form, exact selling unit, quantity, unit-specific selling price, expected total and payment. It visibly preserves stock before/after and sale status. Ambiguous form/unit choices remain explicit; missing prices/conversions display as Unknown and block confirmation; unit/form/strength mismatches and insufficient stock are unsafe and block confirmation. Secondary traceability stays secondary. No typed sale may bypass review.

Owner live validation of this upgrade is pending. The launch-focused sequence is paused; MS2-LT-049 is identified but not started.

Owner evidence then rejected the first recovery because `paracetamol cash` was routed to medicine learning as one medicine string. The deterministic parser and canonical hydration roots are repaired, and the one shared card now implements the approved Fast action / Stock & details / Traceability structure. The recovery audit is recorded in `docs/engineering-memory/production-sales-card-standard.md`. It remains awaiting owner live test and is not approved or protected.

## Canonical live-validation authority

`MS2.0_MASTER_LIVE_TEST_SEQUENCE.md` is the single authoritative roadmap for every current and future owner live test. All checkpoint counts, order, prerequisites and status must be derived from it. Historical plans and embedded “next” notes are evidence only.

Active launch priority is governed by `docs/engineering-memory/launch-readiness-roadmap.md`. It classifies work as Launch Critical, Demo Mode or Continuous Improvement and owns the measurable Launch Gate. It changes priority only; the master still owns stable checkpoint IDs, prerequisites, status, protection and evidence. The former ascending sequence must not auto-resume.

The master’s repository completeness ledger classifies every discovered owner-facing domain, including evidence-backed deprecated and intentionally out-of-scope items. Bridges and synchronization packages must copy neither historical subsets nor independent counts; they must read the master at the current repository commit.

The master is also the engineering traceability index. Every checkpoint has a stable `MS2-LT-NNN` ID, evidence, implementation commits/files, owner proof, remaining work, prerequisites and dependents. After any checkpoint/evidence change, regenerate and verify it with `node scripts/update-master-traceability.mjs` and `node scripts/verify-master-traceability.mjs`; a future Codex or ChatGPT Bridge must derive its evidence chain from that generated index.

## Export Hub protected checkpoint (2026-07-27)

Excel Operations Workbook, PDF Professional Report, Word Owner Copy, Presentation Owner Briefing, CSV Technical Data Transfer and Print Working Inventory are owner-validated, permanently passed and regression-protected. The six-format Export Hub live-validation sequence is complete.

Notifications Quiet State, Pending Review Unread State, Review Import Action Routing, Low-Stock Alert and Out-of-Stock Alert via Catalog Mic are owner-validated, passed and regression-protected. Owner evidence proves the complete Cefixime `22 → 0 → 22` Mic-only round trip, exact single unread out-of-stock alert through refresh, 35-medicine preservation and final quiet-state restoration. Do not repeat it without a direct regression. Catalog Medicine Action Cards and Catalog Search reuse the shared microphone capture path; search transcripts filter the saved catalog locally and deterministically.

CODEX BRIDGE synchronization reports are permanently compact by default: `Repository`, `Checkpoint`, `Files changed`, `Commit`, and `Next owner action`, one line each. Add detail only for an error; never restate protected checkpoint history or completed validation procedures.

Catalog Search Mic is **OWNER-VALIDATED PASS / PROTECTED**. Owner evidence proves a visible Search Mic, truthful listening state, safe zero results for invalid speech, exact unique Paracetamol and Ibuprofen matches, clearing back to all 35 medicines, accurate repeated use and final Quiet Home with no operational mutation. Do not schedule it again unless its shared Search Mic feature changes. Every live-test handoff must include Objective, Expected behaviour, exact numbered owner steps with the expected result after each step, Required screenshots, PASS criteria and FAIL criteria; a checkpoint name alone is never sufficient.

Notifications Expiry Alert Lifecycle is **OWNER-VALIDATED PASS / FROZEN / PROTECTED**. Evidence proves the complete Ibuprofen `2028-12 → 2026-06 → 2028-12` expiry-only Mic workflow, one-field reviews, stock `27`, batch `IBU-200C`, 35 medicines, exactly one canonical local Expiry alert through refresh, and final Quiet restoration. Do not repeat it without a direct regression.

Routine approved Catalog saves use one pharmacy-scoped compact Activity status card and a separate deterministic Activity History. Catalog update prose is prohibited from the permanent operations feed; refresh removes only the exact legacy update messages. History is local, bounded, newest-first, idempotent, Africa/Nairobi-labelled and separate from sales and Notifications. Main Operations Chat Activity Compaction is owner-validated, passed and protected.

Shared Editable-Card Voice Viewport / Focus Preservation is **OWNER-VALIDATED PASS / PROTECTED**. Final evidence after `67cfcac` proves upper, middle, lower and Expiry contextual field voice retains the selected field through listening, transcript application, one-field validation and discard/restoration. The contextual session owns rendering and suppresses ordinary chat-bottom scrolling; earlier failed attempts remain preserved in Engineering Memory. Do not repeat this checkpoint without direct regression evidence.

Payment Failure/Cancellation Notification (MS2-LT-054) is **OWNER-VALIDATED PASS / PROTECTED**. The authoritative Septrin execution proves numeric stock `12 → 12`, M-Pesa quantity 1 at KES 180, Waiting → failed, zero waiting afterward, durable failed history, one actionable Sale 2 alert and Review payment routing to the same failed record. The earlier Zinc run is valid supporting flow evidence only because Zinc had blank Current stock; its Sale 1 alert and Septrin’s Sale 2 alert are distinct, not duplicates.

Every future sale-related owner test must pass the repository-backed preflight in `ms20-main-app/SALE_LIVE_TEST_FIXTURE_STANDARD.md`. Use the real shared SaleCard workflow, verify all scenario-critical catalog values before issuing instructions, capture exact numeric before/after stock when stock is relevant, and record incidental shared sale-card friction without discarding already-valid evidence.

The complete functional, intelligence, learning, reporting/export, financial/payment, integration, security/compliance and production programme is maintained only in the master sequence.

Routine Codex implementation and live-test reports are permanently compact: repository state, checkpoint, at most three change bullets, concise tests, commit/push, and the exact next owner action. Do not restate protected history or architecture unless an error or explicit owner request requires it.

Every export must answer: **Why would a pharmacy owner deliberately choose this format instead of every other available export?** A format is accepted only for a distinct operational workflow. All surfaces consume the shared `exportFormatMetadata.js` registry, and activity updates one persistent pharmacy-scoped Export Hub status card instead of adding chat-feed messages.

Owner evidence confirms the canonical UTF-8-without-BOM CSV opens in Google Sheets as a genuine 35-medicine, 12-column spreadsheet, begins with the exact `Medicine` header, and preserves aligned values and blanks. It is frozen and regression-protected; the unsupported generic Android document reader is outside the compatibility target. See `docs/engineering-memory/csv-compatibility-rules.md`.

Owner evidence confirms Print opens the complete 35-medicine working inventory and Android produces four readable native preview pages without requiring a printer. Opening the dialog is recorded truthfully and never treated as proof of physical printing.

## Current Product Direction

MS2.0 is now Main App-first. The primary product surface is the isolated app in:

```text
ms20-main-app/
```

The Main App is a Pharmacy Operating Intelligence Platform, not an AI chatbot. The first-run owner workflow is:

1. Open MS2.0.
2. Tap the single MS2.0 Assistant conversation.
3. Complete setup.

The daily owner workflow stays three steps or less:

1. Open the MS2.0 Assistant conversation.
2. Type, speak, scan, or upload naturally.
3. Get an instant receipt or review the editable card only when needed.

Complete sale commands record instantly through the existing safe queue path. Missing or ambiguous commands become editable cards. The owner home should stay free of backend, Sheets, queue, token, route, and adapter diagnostics. Those belong in Settings, Diagnostics, Admin, or Developer Mode.

The Main App uses real browser voice capture from the Mic button, direct camera/photo upload from the composer attach menu, quiet card cancellation with no extra chat noise, and persistent `-`/`+` text-size controls on editable cards.

WhatsApp/Baileys remains preserved in this repo as an optional external channel for later. Do not use WhatsApp live testing as proof of Main App readiness.

## Permanent Export Hub Format-Purpose Principle

Before implementing, redesigning or approving an export, answer: **Why would a pharmacy owner deliberately choose this format instead of every other available export?**

Every format must own a distinct pharmacy workflow, state that purpose directly in the Export Hub, and derive its data from the same immutable pharmacy-scoped snapshot. Excel is for analysis and operations; PDF is for professional read-only sharing; Word is for editable owner review and corrections; CSV is for machine data exchange; Presentation is for business and management briefings; Print is for an immediate physical working copy. A format whose distinct owner purpose cannot be stated and protected must be redesigned or rejected. See `docs/engineering-memory/export-format-purpose.md`.

## Replit Main App Live Testing

After pulling this update into Replit, verify the Main App:

```bash
cd ms20-main-app
npm run verify
npm run check
```

The Replit public URL is normally owned by the existing backend on port 5000. The backend now serves the Main App through a safe static adapter at:

```text
https://$REPLIT_DEV_DOMAIN/main-app/
```

Restart the Replit app after pulling so `app/main.py` loads the route. The bare Replit domain may still return backend status JSON; that is expected. Use `/main-app/` for phone testing.

Main App live testing rules:

- Main App only.
- No WhatsApp/Baileys live testing.
- No secrets changes.
- No OpenAI/API calls unless explicitly required.
- Keep local-first and queue-only behavior until live write sync is intentionally enabled.
- Preserve backend, offline app, Google Sheets, reports, stock/sales safety, and runtime config.
- Test one owner action at a time, record friction, fix root causes, verify, and resume.

For the full Main App/Replit handoff, read:

```text
MS20_REPLIT_MAIN_APP_UPDATE.md
ms20-main-app/REPLIT_WORKFLOW_HANDOFF.md
ms20-main-app/LIVE_APP_TEST_PLAN.md
```

# Legacy Backend And Optional WhatsApp Runtime

A simple MVP for pharmacy owners who only want to send WhatsApp text messages or WhatsApp voice notes.

The app receives a WhatsApp update, handles known pharmacy flows locally first, logs the event in Google Sheets, updates stock after sales, and generates daily WhatsApp reports for business decisions.

Default system display name: `MS2.0`.

## Baileys WhatsApp Bridge Mode

Baileys is the active WhatsApp bridge for the current production runtime.

Run the backend:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
```

Set these environment variables:

```text
WHATSAPP_BRIDGE_ENABLED=true
PHARMAREEN_BACKEND_URL=http://localhost:5000
OWNER_WHATSAPP_TO=whatsapp:+254700000000
OPENAI_API_KEY=
GOOGLE_SHEET_ID=
GOOGLE_SHEETS_CREDENTIALS=
PHARMACY_REGISTRY_AUTH_ENABLED=true
```

Baileys bridge endpoint URL:

```text
https://YOUR-DOMAIN/webhooks/baileys/whatsapp
```

Legacy Meta/Twilio environment variables may remain for compatibility, but they are not the active live messaging bridge.

## Pharmacy Registry

Production pharmacy numbers live in the Google Sheet `Pharmacies` registry, not permanently in Replit Secrets. `ALLOWED_WHATSAPP_NUMBERS` remains available only as a temporary development override for controlled testing. Registered active numbers are served normally; unregistered direct numbers can only start onboarding or receive the setup prompt.

## AI Safety Rules

Low-risk messages save automatically:

```text
Panadol sold 2
Panadol stock
report today
```

High-risk messages ask before saving:

```text
Panadol bad
Return Panadol
Panadol restocked 100 exp Jan 2027
```

Reply `YES` to confirm, `EDIT` to correct, or `CANCEL` to discard.

## Offline App

Open:

```text
/offline_app/index.html
```

The offline app saves sales/restocks locally when internet is poor. When the connection returns, it auto-syncs to:

```text
POST /sync/offline-actions
```

It retries every 30 seconds, tracks failed items, and keeps a visible status banner:

- Offline - saving safely
- Syncing...
- Synced
- Some items not synced yet

Images and voice files can be queued offline. They are uploaded and processed only after internet returns.

## Easiest Windows Setup

For beginner-friendly Windows setup, open:

```text
EASY_SETUP.md
```

Or double-click:

```text
start_here.bat
```

Common one-click scripts:

- `setup.bat`: create virtual environment, install requirements, and create `.env` if missing.
- `run.bat`: start the app at `http://localhost:8000`.
- `seed_prices.bat`: add sample testing prices to `Master_Stock`.
- `daily_report.bat`: generate today's report from the local app.
- `ngrok_start.bat`: start ngrok for local WhatsApp Web bridge testing.
- `test.bat`: run tests.

For production without ngrok, see `README_PRODUCTION.md`.

## FAST TEST

Use this when you want to prove the Windows installer build works.

1. Double-click `build_install_prove.bat`.
2. Install `dist\ZillaPharmacySetup.exe`.
3. Double-click `prove_app_works.bat`.
4. If `APP WORKING` appears, the app is running.

Installed app path:

```text
C:\Program Files (x86)\ZillaPharmacy\ZillaPharmacyApp.exe
```

If Google Sheets is not configured yet, the app still starts. `/health` should return:

```json
{"status":"ok","service":"MS2.0","version":"day-2"}
```

## What The System Does

- Accepts WhatsApp text messages.
- Accepts WhatsApp voice notes.
- Transcribes voice notes to text.
- Parses one or many pharmacy events from the text.
- Logs sales, missed demand, and lost opportunities.
- Looks up sale prices from `Master_Stock`.
- Reduces `Current Stock` after sales.
- Warns when stock reaches `Reorder Level`.
- Saves daily reports in `Daily_Reports`.
- Lets the owner fetch saved reports by WhatsApp command.

The owner never enters prices in WhatsApp and never uses forms.

## How The Owner Uses It

The owner sends short natural messages:

```text
Panadol sold 2
sold 2 panadol
Insulin no stock
3 people asked vitamin c
customer asked inhaler but left
cough syrup sold one
amoxyl asked not available
malaria tablets too expensive
paracetamol sold 2 packets
Panadol sold 2, insulin no stock, cough syrup sold 1
```

The owner can also send a voice note saying the same thing. Voice notes are only transcribed to text, then processed by the same logic as normal WhatsApp messages.

## Actions

- `Sold`: sale happened.
- `Out of Stock`: customer asked, but the pharmacy did not have it.
- `Not Sold`: customer asked, but did not buy because they left, price was too high, or another non-stock reason.

If quantity is missing, the app uses `1`.

## Google Sheets Setup

Create one Google Sheet and share it with your Google service account email.

The app creates or repairs these worksheets on startup.

### Master_Stock

| Drug Name | Selling Price | Cost Price | Current Stock | Reorder Level |
| --- | --- | --- | --- | --- |
| Panadol | 200 | 120 | 20 | 5 |

Only `Drug Name` and `Selling Price` are required for sales. `Current Stock` and `Reorder Level` are optional, but needed for stock updates and low-stock warnings.

### Daily_Log

| Date | Time | Drug Name | Action | Quantity | Price | Total Value | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |

For `Sold`, price and total value are filled from `Master_Stock`.

For `Out of Stock` and `Not Sold`, price and total value stay blank, even if the drug is not in `Master_Stock`.

### Daily_Reports

| Date | Total Sales | Total Items Sold | Most Requested Drugs | Most Sold Drugs | Missed Sales | Low Stock Warnings | AI Recommendation Summary | Full Report Text |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

`Full Report Text` is what the app sends back when the owner asks for an old report.

## Seeding Test Prices

You can fill `Master_Stock` with sample testing prices:

```powershell
python scripts/seed_test_prices.py
```

This adds missing sample drugs only. It does not replace existing owner-entered prices.

To overwrite the sample drugs during testing:

```powershell
python scripts/seed_test_prices.py --overwrite
```

Important:

- These prices are only for testing.
- They are not official or final pharmacy prices.
- The pharmacy owner should adjust prices in `Master_Stock` before real use.
- Use `--overwrite` only when you want to reset the sample testing rows.

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
PHARMACY_NAME=Zilla Pharmacy
TIMEZONE=Africa/Nairobi
PUBLIC_BASE_URL=https://your-public-url.example.com
WHATSAPP_PROVIDER=whatsapp_web
REPORT_TRIGGER_TOKEN=change-this-report-token

OPENAI_API_KEY=sk-your-openai-key
OPENAI_PARSE_MODEL=gpt-5
OPENAI_TRANSCRIPTION_MODEL=whisper-1

GOOGLE_SHEETS_SPREADSHEET_ID=your-google-sheet-id
GOOGLE_SERVICE_ACCOUNT_JSON=./service-account.json

WHATSAPP_NUMBER=2547XXXXXXXXxxx
PHARMAREEN_BACKEND_URL=http://localhost:5000
WHATSAPP_WEB_SESSION_PATH=.wwebjs_auth
OWNER_WHATSAPP_TO=whatsapp:+254700000000
```

`GOOGLE_SERVICE_ACCOUNT_JSON` can be a path to a service account JSON file or the raw JSON string.

If `PHARMACY_NAME` is missing, the app uses `Zilla Pharmacy`.

## Run Locally

Requires Python 3.10 or newer.

```powershell
cd "C:\Users\Pal\Documents\New project\pharmacy-intelligence-assistant"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Expose local server for WhatsApp Web bridge:

```powershell
ngrok http 8000
```

Set `PUBLIC_BASE_URL` to the ngrok HTTPS URL.

## Connect WhatsApp Web bridge

In WhatsApp Web bridge sandbox or sender settings, set the incoming message bridge endpoint to:

```text
POST https://your-public-url/bridge/whatsapp-web
```

Keep `WHATSAPP_PROVIDER=whatsapp_web` in production.

## Voice Notes

Voice note flow:

1. Owner sends WhatsApp voice note.
2. WhatsApp Web bridge sends the media URL to the bridge endpoint.
3. App downloads the audio from WhatsApp Web bridge.
4. OpenAI transcribes the audio to text.
5. The same parser handles the transcript.
6. One or multiple entries are logged.
7. The owner receives the same summary reply as text messages.

## Daily Report

Manual trigger:

```powershell
curl -X POST "https://your-public-url/reports/daily?send_whatsapp=true" -H "Authorization: Bearer change-this-report-token"
```

Trigger for a specific date:

```powershell
curl -X POST "https://your-public-url/reports/daily?report_date=2026-04-27&send_whatsapp=true" -H "Authorization: Bearer change-this-report-token"
```

Cron example:

```cron
0 21 * * * curl -X POST "https://your-public-url/reports/daily?send_whatsapp=true" -H "Authorization: Bearer change-this-report-token"
```

The report includes:

- `Zilla Pharmacy` at the top
- Sales summary
- Most requested drugs
- Most sold drugs
- Missed demand / out of stock
- Lost opportunities
- Low stock warnings
- AI recommendations

## Fetch Saved Reports By WhatsApp

The owner can send:

```text
report today
report yesterday
report 2026-04-27
show report 2026-04-27
```

If the report exists in `Daily_Reports`, the app sends the saved `Full Report Text`.
If an older saved report does not include the pharmacy name, the app adds `Zilla Pharmacy` before sending it.

If not found, the app replies:

```text
No report found for 2026-04-27.
```

## Expected Behaviour

Owner sends:

```text
Panadol sold 2
```

Reply:

```text
Logged sale: Panadol x2 = Ksh 400.
```

Owner sends:

```text
Insulin no stock
```

Reply:

```text
Logged missed demand: Insulin.
```

Owner sends:

```text
Panadol sold 2, insulin no stock, inhaler customer left
```

Reply:

```text
Logged 3 entries:

- Panadol sold 2
- Insulin missed demand
- Inhaler lost opportunity
```

## Testing

```powershell
pytest
```

Tests use fake services and do not call WhatsApp Web bridge, OpenAI, or Google Sheets.

## API Summary

- `GET /health`: health check.
- `POST /bridge/whatsapp-web`: WhatsApp Web bridge bridge endpoint.
- `POST /reports/daily`: generate, save, and optionally send the daily report.

## Presentation compatibility and export history

Presentation is a nine-slide owner/management decision briefing, not another inventory list. The production path validates the complete OOXML package before download, and the exact generated deck is application-tested in Microsoft PowerPoint.

Export activity updates one compact Export Hub card in the main chat. Newest-first pharmacy-isolated metadata history lives inside Export Hub; retries are deduplicated, failures can be generated again, and generated binaries are never retained in browser storage.

<!-- VALIDATION_CONTRACT_SYNC_START -->
## Generated validation-contract reference

- Authority: `MS2.0_MASTER_LIVE_TEST_SEQUENCE.md`
- Checkpoints: 84
- Current: MS2-LT-049 — Exact form/unit/pack/price truth
- Bridge manifest: `docs/engineering-memory/bridge-validation-contract.json`
- Token policy: ACTIVE — `docs/engineering-memory/token-execution-policy.md`
- Rule: Codex and ChatGPT Bridges load the master and Engineering Traceability Index; no parallel sequence is permitted.
<!-- VALIDATION_CONTRACT_SYNC_END -->
