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
  })
]);

export function findBarcodeTestFixture(value) {
  const barcode = String(value || "").trim();
  return BarcodeTestFixtures.find((fixture) => fixture.barcode === barcode) || null;
}
