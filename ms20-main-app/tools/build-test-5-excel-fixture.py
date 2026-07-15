from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ["Medicine", "Strength", "Form", "Unit", "Selling Price", "Cost Price", "Stock", "Supplier", "Barcode", "Batch", "Expiry", "Pack Size", "Shelf"]
ROWS = [
    ["Cetirizine", "10 mg", "tablet", "tablet", 15, 8, 45, "EastCare Pharma", "", "CET-10A", "2029-04", "30 tablets", "D1"],
    ["Co-amoxiclav", "625 mg", "tablet", "tablet", 85, 60, 24, "EastCare Pharma", "", "COA-625B", "2028-11", "14 tablets", "D2"],
    ["Paracetamol", "500 mg", "tablet", "tablet", 10, 5, 100, "EastCare Pharma", "", "PAR-500C", "2029-06", "100 tablets", "D3"],
]

def col(index):
    value = ""
    while index:
        index, rem = divmod(index - 1, 26)
        value = chr(65 + rem) + value
    return value

def cell(row, column, value):
    ref = f"{col(column)}{row}"
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'

sheet_rows = []
for row_index, values in enumerate([HEADERS, *ROWS], 1):
    sheet_rows.append(f'<row r="{row_index}">' + "".join(cell(row_index, index, value) for index, value in enumerate(values, 1)) + "</row>")

files = {
    "[Content_Types].xml": '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
    "_rels/.rels": '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    "xl/workbook.xml": '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Medicines" sheetId="1" r:id="rId1"/></sheets></workbook>',
    "xl/_rels/workbook.xml.rels": '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
    "xl/worksheets/sheet1.xml": '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(sheet_rows) + '</sheetData></worksheet>',
}

with ZipFile(ROOT / "fixtures" / "test-5-excel-import.xlsx", "w", compression=ZIP_DEFLATED) as workbook:
    for name, body in files.items():
        workbook.writestr(name, body)
