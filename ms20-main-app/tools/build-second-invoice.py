from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
fixture = json.loads((ROOT / "fixtures" / "second-supplier-invoice.json").read_text(encoding="utf-8"))
out = ROOT / "fixtures" / "test-2-dawa-bora-invoice.png"
W, H = 1800, 1200
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
blue, pale, ink, grey = "#154C79", "#EAF3F8", "#102A3A", "#637684"
regular, bold = "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"

def f(size, is_bold=False): return ImageFont.truetype(bold if is_bold else regular, size)
def tx(x, y, value, size=28, is_bold=False, fill=ink, anchor=None):
    d.text((x, y), str(value), font=f(size, is_bold), fill=fill, anchor=anchor)

d.rectangle((0, 0, W, 150), fill=blue)
tx(70, 42, "DAWA BORA WHOLESALE LTD", 48, True, "white")
tx(70, 100, "Licensed pharmaceutical wholesaler | Nairobi, Kenya", 24, False, "white")
tx(1730, 55, "SUPPLIER INVOICE", 34, True, "white", "ra")
tx(70, 190, "Bill to: Zuri Pharmacy", 31, True)
tx(70, 235, "Delivery: Main branch, Nairobi", 25, False, grey)
tx(1120, 185, f"Invoice No:  {fixture['invoice_number']}", 28, True)
tx(1120, 228, f"Invoice Date:  {fixture['invoice_date']}", 27)
tx(1120, 268, "Currency:  KES", 27)
d.line((70, 315, 1730, 315), fill=blue, width=4)
cols = [(70,290,"Medicine / Strength"),(360,180,"Form"),(540,140,"Unit"),(680,170,"Pack size"),(850,90,"Qty"),(940,150,"Unit cost"),(1090,150,"Sell price"),(1240,170,"Line total"),(1410,170,"Batch"),(1580,150,"Expiry")]
header_y, row_h = 345, 145
d.rectangle((70, header_y, 1730, header_y + 65), fill=blue)
for x, _, label in cols: tx(x + 10, header_y + 18, label, 20, True, "white")
for i, item in enumerate(fixture["items"]):
    top = header_y + 65 + i * row_h
    if i % 2 == 0: d.rectangle((70, top, 1730, top + row_h), fill=pale)
    for x, _, _ in cols: d.line((x, top, x, top + row_h), fill="#A8BAC5", width=2)
    d.line((1730, top, 1730, top + row_h), fill="#A8BAC5", width=2)
    d.line((70, top + row_h, 1730, top + row_h), fill="#A8BAC5", width=2)
    vals=[(f"{item['medicine']}\n{item['strength']}",True),(item['form'],False),(item['unit'],False),(item['pack_size'],False),(item['quantity'],False),(f"{item['unit_cost']:.2f}",False),(f"{item['selling_price']:.2f}",False),(f"{item['line_total']:,.2f}",True),(item['batch'],False),(item['expiry'],False)]
    for (x, _, _), (value, strong) in zip(cols, vals):
        for n, line in enumerate(str(value).split("\n")): tx(x + 10, top + 31 + n * 34, line, 22, strong)
bottom = header_y + 65 + len(fixture["items"]) * row_h
d.rectangle((1190, bottom + 25, 1730, bottom + 190), outline=blue, width=3)
for n,(label,value) in enumerate([("Subtotal",fixture["subtotal"]),("VAT",fixture["vat"]),("INVOICE TOTAL",fixture["invoice_total"])]):
    y=bottom+37+n*51; tx(1220,y,label,24,n==2); tx(1695,y,f"KES {value:,.2f}",24,True,anchor="ra")
tx(70,bottom+48,"Payment terms: Net 30 days",23,True)
tx(70,bottom+88,"Delivery note: DB-DN-0713-42",23)
tx(70,bottom+128,"MS2.0 repeatability fixture — not for payment",21,False,grey)
d.rectangle((25,25,W-25,H-25),outline=blue,width=5)
img.save(out,"PNG",optimize=True)
print(out)
