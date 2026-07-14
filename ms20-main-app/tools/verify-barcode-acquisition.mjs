import fs from "node:fs";

const source = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
const expect = (condition, message) => {
  if (!condition) throw new Error(message);
};

expect(source.includes('data-action="scan-barcode"'), "Barcode quick action must use the real acquisition action");
expect(source.includes('openLightweightCamera("barcode")'), "Barcode action must enter the shared camera lifecycle");
expect(source.includes('await readBarcodeCapture(file)'), "Captured barcode frames must enter local decoding");
expect(source.includes('"BarcodeDetector" in globalThis'), "Barcode decoding must remain local and zero-token");
expect(source.includes('pharmacyBrain.catalog.find'), "Decoded barcodes must match only against the saved Pharmacy Catalog");
expect(source.includes('enter the barcode manually; nothing has been saved'), "Unreadable barcodes must retain an honest unsaved fallback");
expect(!source.includes("Barcode scanner placeholder"), "Placeholder barcode cards must not remain reachable");

console.log("Barcode acquisition verification passed.");
