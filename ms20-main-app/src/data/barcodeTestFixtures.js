// Controlled live-test records only. Production barcode knowledge remains catalog-owned.
export const BarcodeTestFixtures = Object.freeze([
  Object.freeze({
    fixtureId: "barcode-losartan-50mg",
    barcode: "6161109876546",
    name: "Losartan",
    strength: "50 mg",
    form: "tablet",
    unit: "tablet",
    selling_price: "25",
    cost_price: "15",
    stock: "40",
    supplier: "Dawa Bora Wholesale Ltd",
    batch: "LOS-50T",
    expiry: "2029-06",
    source: "controlled_barcode_fixture"
  }),
  Object.freeze({
    fixtureId: "barcode-loperamide-2mg",
    barcode: "6161109876553",
    name: "Loperamide",
    strength: "2 mg",
    form: "capsule",
    unit: "capsule",
    selling_price: "15",
    cost_price: "8",
    stock: "30",
    supplier: "MedSource Kenya Ltd",
    batch: "LOP-2C",
    expiry: "2028-12",
    source: "controlled_barcode_fixture"
  })
]);

export function findBarcodeTestFixture(value) {
  const barcode = String(value || "").trim();
  return BarcodeTestFixtures.find((fixture) => fixture.barcode === barcode) || null;
}
