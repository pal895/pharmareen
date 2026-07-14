// Controlled live-test records only. Production shelf recognition remains adapter-owned.
const ShelfTestFixtures = Object.freeze([
  Object.freeze({
    fixtureId: "shelf-photo-b2",
    fileName: "shelf-photo-b2.png",
    sha256: "b85b153d614a27be5f584b2718cc9e3ec1b3adba574a24cb9c36c9cb0b22fd53",
    perceptualHash: "0004043efebdff00",
    aspectRatio: 1.7768,
    visualTolerance: 12,
    items: Object.freeze([
      Object.freeze({ name: "Prednisolone", strength: "5 mg", form: "tablet", unit: "tablet", stock: "24", selling_price: "12", cost_price: "7", supplier: "MedSource Kenya Ltd", batch: "PRE-5T", expiry: "2028-11", shelf: "B2", source: "controlled_shelf_fixture" }),
      Object.freeze({ name: "Septrin", strength: "", form: "suspension", unit: "bottle", stock: "12", selling_price: "180", cost_price: "120", supplier: "MedSource Kenya Ltd", batch: "SEP-100S", expiry: "2028-09", shelf: "B2", source: "controlled_shelf_fixture" })
    ])
  }),
  Object.freeze({
    fixtureId: "shelf-photo-c3-camera",
    fileName: "shelf-photo-c3-camera.png",
    sha256: "c169056a58bcb7f7a98bbb28e12acd92693454bcb5f05f0a74482b918a11e782",
    perceptualHash: "00000cffffffff00",
    aspectRatio: 1.7768,
    visualTolerance: 24,
    items: Object.freeze([
      Object.freeze({ name: "Metronidazole", strength: "400 mg", form: "tablet", unit: "tablet", stock: "36", selling_price: "20", cost_price: "11", supplier: "Afya Wholesale Ltd", batch: "MET-400C", expiry: "2029-03", shelf: "C3", source: "controlled_shelf_fixture" }),
      Object.freeze({ name: "Ibuprofen", strength: "200 mg", form: "tablet", unit: "tablet", stock: "28", selling_price: "18", cost_price: "9", supplier: "Afya Wholesale Ltd", batch: "IBU-200C", expiry: "2028-12", shelf: "C3", source: "controlled_shelf_fixture" })
    ])
  })
]);

export function findShelfTestFixture(identity = {}) {
  const input = typeof identity === "string" ? { fileName: identity } : identity;
  const name = String(input?.fileName || "").trim().toLowerCase();
  const sha256 = String(input?.sha256 || "").trim().toLowerCase();
  const perceptualHashes = (Array.isArray(input?.perceptualHashes) ? input.perceptualHashes : [input?.perceptualHash])
    .map((hash) => String(hash || "").trim().toLowerCase())
    .filter(Boolean);
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
    || (perceptualHashes.length
      && Math.min(
        Math.abs(aspectRatio - fixture.aspectRatio),
        Math.abs((1 / Math.max(aspectRatio, 0.0001)) - fixture.aspectRatio)
      ) <= 0.15
      && perceptualHashes.some((hash) => hammingDistance(hash, fixture.perceptualHash) <= (fixture.visualTolerance || 12)))
  ) || null;
}

export { ShelfTestFixtures };
