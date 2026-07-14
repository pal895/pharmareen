// Controlled live-test records only. Production shelf recognition remains adapter-owned.
const ShelfTestFixtures = Object.freeze([
  Object.freeze({
    fixtureId: "shelf-photo-b2",
    fileName: "shelf-photo-b2.png",
    sha256: "b85b153d614a27be5f584b2718cc9e3ec1b3adba574a24cb9c36c9cb0b22fd53",
    perceptualHash: "0004043efebdff00",
    aspectRatio: 1.7768,
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
  const perceptualHash = String(input?.perceptualHash || "").trim().toLowerCase();
  const aspectRatio = Number(input?.aspectRatio || 0);
  const hammingDistance = (left, right) => {
    if (!left || !right || left.length !== right.length) return Infinity;
    let distance = 0;
    for (let index = 0; index < left.length; index += 1) {
      let value = Number.parseInt(left[index], 16) ^ Number.parseInt(right[index], 16);
      while (value) {
        distance += value & 1;
        value >>>= 1;
      }
    }
    return distance;
  };
  return ShelfTestFixtures.find((fixture) =>
    (name && fixture.fileName.toLowerCase() === name)
    || (sha256 && fixture.sha256 === sha256)
    || (perceptualHash
      && Math.abs(aspectRatio - fixture.aspectRatio) <= 0.08
      && hammingDistance(perceptualHash, fixture.perceptualHash) <= 12)
  ) || null;
}

export { ShelfTestFixtures };
