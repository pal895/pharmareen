// Controlled live-test records only. Production shelf recognition remains adapter-owned.
const ShelfTestFixtures = Object.freeze([
  Object.freeze({
    fixtureId: "shelf-photo-b2",
    fileName: "shelf-photo-b2.png",
    items: Object.freeze([
      Object.freeze({ name: "Prednisolone", strength: "5 mg", form: "tablet", unit: "tablet", stock: "24", selling_price: "12", cost_price: "7", supplier: "MedSource Kenya Ltd", batch: "PRE-5T", expiry: "2028-11", shelf: "B2", source: "controlled_shelf_fixture" }),
      Object.freeze({ name: "Septrin", strength: "", form: "suspension", unit: "bottle", stock: "12", selling_price: "180", cost_price: "120", supplier: "MedSource Kenya Ltd", batch: "SEP-100S", expiry: "2028-09", shelf: "B2", source: "controlled_shelf_fixture" })
    ])
  })
]);

export function findShelfTestFixture(fileName) {
  const name = String(fileName || "").trim().toLowerCase();
  return ShelfTestFixtures.find((fixture) => fixture.fileName.toLowerCase() === name) || null;
}

export { ShelfTestFixtures };
