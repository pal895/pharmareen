const encoder = new TextEncoder();

export function buildStoredZip(entries) {
  const files = entries.map(({ name, contents }) => ({
    name: encoder.encode(name),
    data: contents instanceof Uint8Array ? contents : encoder.encode(String(contents)),
    crc: crc32(contents instanceof Uint8Array ? contents : encoder.encode(String(contents)))
  }));
  const localParts = [];
  const centralParts = [];
  let offset = 0;
  for (const file of files) {
    const local = concat(
      u32(0x04034b50), u16(20), u16(0), u16(0), u16(0), u16(0),
      u32(file.crc), u32(file.data.length), u32(file.data.length),
      u16(file.name.length), u16(0), file.name, file.data
    );
    localParts.push(local);
    centralParts.push(concat(
      u32(0x02014b50), u16(20), u16(20), u16(0), u16(0), u16(0), u16(0),
      u32(file.crc), u32(file.data.length), u32(file.data.length),
      u16(file.name.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(offset), file.name
    ));
    offset += local.length;
  }
  const central = concat(...centralParts);
  return concat(
    ...localParts,
    central,
    u32(0x06054b50), u16(0), u16(0), u16(files.length), u16(files.length),
    u32(central.length), u32(offset), u16(0)
  );
}

export function xml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function concat(...parts) {
  const length = parts.reduce((sum, part) => sum + part.length, 0);
  const result = new Uint8Array(length);
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }
  return result;
}

function u16(value) {
  return new Uint8Array([value & 255, (value >>> 8) & 255]);
}

function u32(value) {
  return new Uint8Array([value & 255, (value >>> 8) & 255, (value >>> 16) & 255, (value >>> 24) & 255]);
}

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}
