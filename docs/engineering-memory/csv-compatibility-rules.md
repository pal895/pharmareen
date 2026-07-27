# CSV compatibility rules

## Purpose and canonical shape

CSV is MS2.0's technical data-transfer format. It is selected for import, interoperability and machine processing, while XLSX remains the normal owner-analysis workbook.

The one production CSV has:

- first row: the canonical 12-field header;
- later rows: exactly one canonical medicine per physical row;
- stable order: Medicine, Strength, Form, Unit, Selling price (KES), Cost price (KES), Stock, Supplier, Barcode, Batch, Expiry, Shelf;
- no title, decorative metadata, debug field or blank preamble before the header;
- pharmacy identity in the pharmacy-derived filename and pharmacy-scoped Export History.

## Encoding and serialization

- Encoding: UTF-8 without BOM. Owner evidence showed Google Sheets importing the BOM as visible `ï»¿` text before the first header.
- Delimiter: comma.
- Record ending: CRLF, including the final record.
- Quoting: fields containing comma or double quote use RFC-style double-quote wrapping; internal double quotes are doubled.
- Embedded CR/LF: normalized to one space so every medicine remains one physical record.
- Numbers: invariant decimal text; zero is preserved; missing values are empty.
- Dates: canonical stored values are retained without locale rewriting.
- Leading-zero barcodes: prefixed with a visible apostrophe so spreadsheet software retains the digits.
- Formula safety: text beginning, after optional spaces/tabs, with `=`, `+`, `-` or `@` is prefixed with an apostrophe. Numeric canonical fields remain numeric and contain no formulas or macros.

## Download contract

The Main App generates the file locally. It creates a Blob with `text/csv; charset=utf-8` and an anchor download name ending once in `.csv`. Because no CSV HTTP request is made, this route has no HTTP `Content-Disposition` response header; the HTML download attribute is the filename authority.

Recommended opening applications are Microsoft Excel, Google Sheets and LibreOffice Calc. Generic document readers are not promised to support CSV.

## Current owner checkpoint

Evidence on 2026-07-27 passes generation, one-file download, the 35-medicine newest history entry, the single concise Export Hub card, removal of duplicate guidance and no new permanent export message. The repaired header-first CSV still stalled indefinitely in the tested generic Android document reader. Microsoft Word displayed the expected raw comma-separated text because Word is a document/text viewer for this route, not a spreadsheet renderer.

Google Sheets owner evidence confirms the final file opens as a genuine spreadsheet with cell A1 exactly `Medicine`, 35 medicines, one medicine per row, 12 separated and aligned columns, and blank values that do not shift later fields. The generic Android document reader remains unsupported.

CSV is OWNER-VALIDATED PASS and frozen. Its UTF-8-without-BOM, CRLF, structural, escaping, security, deterministic, pharmacy-isolation and zero-AI contracts are regression-protected. Do not change this subsystem without intentional CSV scope and new regression evidence.
