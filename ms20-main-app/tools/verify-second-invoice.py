from pathlib import Path
import json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
m=json.loads((ROOT/"fixtures"/"second-supplier-invoice.json").read_text(encoding="utf-8"))
s=(ROOT/"src"/"data"/"sourceMedicines.js").read_text(encoding="utf-8")
p=ROOT/"fixtures"/"test-2-dawa-bora-invoice.png"
assert p.exists() and p.stat().st_size>50000
with Image.open(p) as image: assert image.format=="PNG" and image.size==(1800,1200)
existing={x.casefold() for x in m["existing_zuri_catalog_excluded"]}; selected=[x["medicine"] for x in m["items"]]
assert len(selected)==len(set(selected))==4
assert all(x.casefold() not in existing for x in selected)
assert all(f'medicine("{x}"' in s for x in selected)
assert all(x["quantity"]*x["unit_cost"]==x["line_total"] for x in m["items"])
assert sum(x["line_total"] for x in m["items"])==m["subtotal"]
assert m["subtotal"]+m["vat"]==m["invoice_total"]
assert m["supplier"]!="AfyaLink Medical Supplies Ltd" and "landscape" in m["layout"]
print("PASS: asset, Source Brain membership, catalog exclusion, different layout, fields, and arithmetic verified")
