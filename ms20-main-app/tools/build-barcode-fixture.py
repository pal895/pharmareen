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

image = Image.new("RGB", (1400, 760), "white")
draw = ImageDraw.Draw(image)
bold = ImageFont.truetype("arialbd.ttf", 38)
regular = ImageFont.truetype("arial.ttf", 26)
draw.text((70, 45), "MS2.0 CONTROLLED BARCODE TEST FIXTURE", fill="black", font=bold)
draw.text((70, 105), f'{manifest["medicine"]} {manifest["strength"]} - {manifest["form"]}', fill="black", font=bold)
draw.text((70, 160), f'Expected barcode: {value} (EAN-13)', fill="black", font=regular)
module, start_x, top, bar_height = 10, 225, 225, 330
for index, bit in enumerate(bits):
    if bit == "1":
        guard = index < 3 or 45 <= index < 50 or index >= 92
        draw.rectangle((start_x + index * module, top, start_x + (index + 1) * module - 1, top + bar_height + (35 if guard else 0)), fill="black")
draw.text((500, 590), value, fill="black", font=bold)
draw.text((70, 650), "Expected: one existing local Losartan result; no medicine is created or changed.", fill="black", font=regular)
draw.text((70, 700), "Identity fixture only. Current stock and commercial fields come from the saved Pharmacy Catalog.", fill="black", font=regular)
image.save(manifest_path.with_suffix(".png"), optimize=True)
