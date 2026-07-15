// Local XLSX reader. The first worksheet converges into the existing delimited
// inventory parser, so Excel and CSV share normalization, review and approval.
export async function readXlsxInventory(fileOrBuffer) {
  const buffer = fileOrBuffer instanceof ArrayBuffer ? fileOrBuffer : await fileOrBuffer.arrayBuffer();
  const entries = await unzipEntries(new Uint8Array(buffer));
  const workbook = textEntry(entries, "xl/workbook.xml");
  const relations = textEntry(entries, "xl/_rels/workbook.xml.rels");
  const relationId = firstMatch(workbook, /<sheet\b[^>]*\br:id=["']([^"']+)["']/i);
  if (!relationId) throw new Error("No worksheet was found in this Excel file.");
  const target = firstMatch(relations, new RegExp(`<Relationship\\b[^>]*\\bId=["']${escapeRegex(relationId)}["'][^>]*\\bTarget=["']([^"']+)["']`, "i"));
  if (!target) throw new Error("The first Excel worksheet could not be opened.");
  const sheet = textEntry(entries, normalizeZipPath(`xl/${target}`));
  const shared = entries.has("xl/sharedStrings.xml") ? parseSharedStrings(textEntry(entries, "xl/sharedStrings.xml")) : [];
  const rows = parseSheetRows(sheet, shared);
  if (rows.length < 2) throw new Error("This Excel sheet has no medicine rows.");
  return rows.map((row) => row.map(tsvCell).join("\t")).join("\n");
}

async function unzipEntries(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let eocd = -1;
  for (let at = bytes.length - 22; at >= Math.max(0, bytes.length - 65557); at -= 1) {
    if (view.getUint32(at, true) === 0x06054b50) { eocd = at; break; }
  }
  if (eocd < 0) throw new Error("This is not a readable XLSX file.");
  const count = view.getUint16(eocd + 10, true);
  let offset = view.getUint32(eocd + 16, true);
  const decoder = new TextDecoder();
  const entries = new Map();
  for (let index = 0; index < count; index += 1) {
    if (view.getUint32(offset, true) !== 0x02014b50) throw new Error("The XLSX file directory is damaged.");
    const method = view.getUint16(offset + 10, true);
    const size = view.getUint32(offset + 20, true);
    const nameLength = view.getUint16(offset + 28, true);
    const extraLength = view.getUint16(offset + 30, true);
    const commentLength = view.getUint16(offset + 32, true);
    const localOffset = view.getUint32(offset + 42, true);
    const name = normalizeZipPath(decoder.decode(bytes.slice(offset + 46, offset + 46 + nameLength)));
    const start = localOffset + 30 + view.getUint16(localOffset + 26, true) + view.getUint16(localOffset + 28, true);
    const compressed = bytes.slice(start, start + size);
    entries.set(name, method === 0 ? compressed : await inflateEntry(compressed, method));
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
}

async function inflateEntry(bytes, method) {
  if (method !== 8 || typeof DecompressionStream !== "function") throw new Error("This Excel compression is not supported on this device.");
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

function parseSharedStrings(xml) {
  return Array.from(xml.matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>/gi), (match) =>
    Array.from(match[1].matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/gi), (text) => decodeXml(text[1])).join(""));
}

function parseSheetRows(xml, shared) {
  return Array.from(xml.matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/gi), (rowMatch) => {
    const cells = [];
    for (const match of rowMatch[1].matchAll(/<c\b([^>]*)>([\s\S]*?)<\/c>/gi)) {
      const ref = firstMatch(match[1], /\br=["']([A-Z]+)\d+["']/i) || "A";
      const type = firstMatch(match[1], /\bt=["']([^"']+)["']/i);
      const raw = firstMatch(match[2], /<v\b[^>]*>([\s\S]*?)<\/v>/i);
      const inline = firstMatch(match[2], /<t\b[^>]*>([\s\S]*?)<\/t>/i);
      cells[columnIndex(ref)] = type === "s" ? (shared[Number(raw)] ?? "") : decodeXml(inline || raw || "");
    }
    return cells.map((value) => String(value ?? "").trim());
  }).filter((row) => row.some(Boolean));
}

function columnIndex(ref) { return String(ref).toUpperCase().split("").reduce((value, letter) => (value * 26) + letter.charCodeAt(0) - 64, 0) - 1; }
function textEntry(entries, name) { const bytes = entries.get(normalizeZipPath(name)); if (!bytes) throw new Error(`The Excel file is missing ${name}.`); return new TextDecoder().decode(bytes); }
function normalizeZipPath(value) { const parts = []; for (const part of String(value).replace(/\\/g, "/").split("/")) { if (!part || part === ".") continue; if (part === "..") parts.pop(); else parts.push(part); } return parts.join("/"); }
function decodeXml(value) { return String(value).replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&"); }
function tsvCell(value) { return String(value ?? "").replace(/[\t\r\n]+/g, " ").trim(); }
function firstMatch(value, pattern) { return String(value || "").match(pattern)?.[1] || ""; }
function escapeRegex(value) { return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
