// Controlled live-test records only. Production shelf recognition remains adapter-owned.
const ShelfTestFixtures = Object.freeze([
  Object.freeze({
    fixtureId: "shelf-photo-b2",
    fileName: "shelf-photo-b2.png",
    sha256: "b85b153d614a27be5f584b2718cc9e3ec1b3adba574a24cb9c36c9cb0b22fd53",
    items: Object.freeze([
      Object.freeze({ name: "Prednisolone", strength: "5 mg", form: "tablet", unit: "tablet", stock: "24", selling_price: "12", cost_price: "7", supplier: "MedSource Kenya Ltd", batch: "PRE-5T", expiry: "2028-11", shelf: "B2", source: "controlled_shelf_fixture" }),
      Object.freeze({ name: "Septrin", strength: "", form: "suspension", unit: "bottle", stock: "12", selling_price: "180", cost_price: "120", supplier: "MedSource Kenya Ltd", batch: "SEP-100S", expiry: "2028-09", shelf: "B2", source: "controlled_shelf_fixture" })
    ])
  })
]);

export function findShelfTestFixture(identity = {}) {
  const input = typeof identity === "string" ? { fileName: identity } : identity;
  const name = String(input?.fileName || "").trim().toLowerCase();
  const sha256 = String(input?.sha256 || "").trim().toLowerCase();
  return ShelfTestFixtures.find((fixture) =>
    (name && fixture.fileName.toLowerCase() === name)
    || (sha256 && fixture.sha256 === sha256)
  ) || null;
}

export { ShelfTestFixtures };
