# Export format purpose

## Permanent engineering question

Before implementing, redesigning or approving any Export Hub format, answer:

> Why would a pharmacy owner deliberately choose this format instead of every other available export?

A format is justified only when it solves a distinct real pharmacy workflow. Multiple file extensions must not be used to disguise the same generic document.

## Shared contract

- The shared `EXPORT_FORMATS` registry carries a concise owner-facing explanation and a machine-readable unique purpose for every format.
- The Export Hub must make the choice understandable without separate documentation.
- Every renderer consumes the same immutable, validated, pharmacy-scoped canonical snapshot; purpose changes presentation and workflow, never source truth.
- New formats require a distinct purpose, focused regression coverage, deterministic generation, pharmacy isolation, zero routine AI formatting, and legal/IP-safe assets.
- If a distinct purpose cannot be stated clearly, redesign or reject the format.

## Current responsibilities

- **Excel:** inventory analysis, purchasing, reconciliation, calculations, filtering and pharmacy operations.
- **PDF:** professional read-only phone sharing, formal hand-offs and printing.
- **Word:** editable owner review, corrections, approval and typed or handwritten working notes.
- **CSV:** imports, exports, interoperability and machine-to-machine exchange.
- **Presentation:** management, staff, supplier, investor or lender briefings on a large screen.
- **Print:** an immediate physical working inventory produced from the browser.

Shared canonical parity does not mean identical design. Each format must prioritize the information and interaction needed for its own job. `ms20-main-app/src/services/exportFormatMetadata.js` is authoritative across cards, status, history, application guidance, regeneration and accessibility.

## Presentation Owner Briefing

Presentation exists for owner and management decisions, not for reproducing the inventory register. Its deterministic nine-slide sequence is title, baseline overview, inventory position, stock/value summary, low-stock attention, expiry outlook, supplier overview, owner actions and closing decision path. Detailed reconciliation remains in Excel and record corrections remain in Word.

Before download, the production path validates the PPTX container, required OOXML parts, content types, relationships and slide count. Owner evidence on 2026-07-27 confirmed download, detection and all nine readable slides in an Android standards-compatible reader, resolving the original Android `Error (4)` blocker. PowerPoint remains recommended; Google Slides and compatible readers are legitimate fallbacks. Presentation is OWNER-VALIDATED PASS.

## Current sequence

- Excel Operations Workbook: passed and protected.
- PDF Professional Report: passed and protected.
- Word Owner Copy: passed and protected.
- Presentation Owner Briefing: passed and protected.
- CSV Technical Data Transfer: passed and protected.
- Print Working Inventory: exact next live checkpoint.

## CSV compatibility checkpoint

CSV is the import/interchange copy, not a styled report. Its first row is the canonical field header and every later physical row is one medicine with the same 12-column shape. Pharmacy identity remains in the safe pharmacy-derived filename and pharmacy-scoped Export History instead of decorative pre-header rows that weaken automatic import detection. The production Blob is `text/csv; charset=utf-8`; the browser download attribute supplies one safe `.csv` filename. Microsoft Excel, Google Sheets and LibreOffice Calc are recommended; generic document readers are not compatibility authorities.

Owner evidence on 2026-07-27 confirms Google Sheets opens the final UTF-8-without-BOM file as a genuine 35-medicine, 12-column spreadsheet with A1 exactly `Medicine`, aligned values and preserved blanks. Generation, download, history, the one-card update and no message pileup also pass. CSV is OWNER-VALIDATED PASS and protected; the generic Android document reader is outside the supported spreadsheet ecosystem.
