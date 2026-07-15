export function matchesControlledImageFixture(fixture, identity = {}) {
  const name = String(identity?.fileName || "").trim().toLowerCase();
  const sha256 = String(identity?.sha256 || "").trim().toLowerCase();
  if (name && fixture.fileName.toLowerCase() === name) return true;
  if (sha256 && fixture.sha256 === sha256) return true;

  const inputHashes = (Array.isArray(identity?.perceptualHashes) ? identity.perceptualHashes : [identity?.perceptualHash])
    .map(normalizeHash)
    .filter(Boolean);
  if (!inputHashes.length) return false;
  const fixtureHashes = (Array.isArray(fixture?.perceptualHashes) ? fixture.perceptualHashes : [fixture?.perceptualHash])
    .map(normalizeHash)
    .filter(Boolean);
  const aspectRatio = Number(identity?.aspectRatio || 0);
  const aspectDistance = Math.min(
    Math.abs(aspectRatio - fixture.aspectRatio),
    Math.abs((1 / Math.max(aspectRatio, 0.0001)) - fixture.aspectRatio)
  );
  if (aspectDistance > (fixture.aspectTolerance || 0.15)) return false;
  return inputHashes.some((inputHash) => fixtureHashes.some((fixtureHash) =>
    hammingDistance(inputHash, fixtureHash) <= (fixture.visualTolerance || 12)
  ));
}

function normalizeHash(hash) {
  return String(hash || "").trim().toLowerCase();
}

function hammingDistance(left, right) {
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
}
