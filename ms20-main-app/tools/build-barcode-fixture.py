from pathlib import Path
import json
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
manifest_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "fixtures" / "barcode-losartan-50mg.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
value = manifest["barcode"]
L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
G = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"]
R = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"]
PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]
first = int(value[0])
left = "".join((L if kind == "L" else G)[int(digit)] for kind, digit in zip(PARITY[first], value[1:7]))
right = "".join(R[int(digit)] for digit in value[7:])
bits = "101" + left + "01010" + right + "101"

image = Image.new("RGB", (3000, 1600), "white")
draw = ImageDraw.Draw(image)
bold = ImageFont.truetype("arialbd.ttf", 76)
regular = ImageFont.truetype("arial.ttf", 52)
draw.text((120, 70), "MS2.0 CONTROLLED BARCODE TEST FIXTURE", fill="black", font=bold)
draw.text((120, 185), f'{manifest["medicine"]} {manifest["strength"]} - {manifest["form"]}', fill="black", font=bold)
draw.text((120, 300), f'Expected barcode: {value} (EAN-13)', fill="black", font=regular)
module, start_x, top, bar_height = 24, 360, 430, 680
for index, bit in enumerate(bits):
    if bit == "1":
        guard = index < 3 or 45 <= index < 50 or index >= 92
        draw.rectangle((start_x + index * module, top, start_x + (index + 1) * module - 1, top + bar_height + (75 if guard else 0)), fill="black")
draw.text((1050, 1215), value, fill="black", font=bold)
draw.text((120, 1350), "Expected: one existing local Losartan result; no medicine is created or changed.", fill="black", font=regular)
draw.text((120, 1450), "Identity fixture only. Current fields come from the saved Pharmacy Catalog.", fill="black", font=regular)
image.save(manifest_path.with_suffix(".png"), optimize=True)

bars = "".join(
    f'<rect x="{index}" y="0" width="1" height="100" />'
    for index, bit in enumerate(bits) if bit == "1"
)
live_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MS2.0 Losartan barcode fixture</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#fff;color:#000;font-family:Arial,sans-serif}}
main{{min-height:100vh;display:grid;place-items:center;padding:1vh 2vw;text-align:center}}
.fixture{{width:min(94vw,1800px)}}h1{{margin:0 0 .5vh;font-size:clamp(26px,3.5vw,58px)}}p{{margin:.5vh 0;font-size:clamp(18px,2vw,34px)}}
svg{{display:block;width:100%;height:58vh;background:#fff;shape-rendering:crispEdges}}
.number{{font-size:clamp(28px,4vw,64px);font-weight:800;letter-spacing:.12em}}
</style></head><body><main><section class="fixture">
<h1>Losartan 50 mg — controlled MS2.0 barcode</h1>
<p>Hold this screen steady and scan the barcode only.</p>
<svg viewBox="-8 -8 111 116" preserveAspectRatio="none" role="img" aria-label="EAN-13 barcode {value}">{bars}</svg>
<div class="number">{value}</div>
</section></main></body></html>"""
manifest_path.with_name("barcode-losartan-50mg-live.html").write_text(live_html, encoding="utf-8")
