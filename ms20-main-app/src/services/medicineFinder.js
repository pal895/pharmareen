import { normalizeMedicineText } from "./medicineMatcher.js";
import { normalizeExpiryValue, expiryEndDate } from "./medicineFieldSchema.js";

export function buildMedicineFinderIndex(items = [], { now = new Date() } = {}) {
  const unique = new Map();
  for (const [position, item] of items.entries()) {
    const name = String(item.name || item.medicine || "").trim();
    const canonical = normalizeMedicineText(name);
    if (!canonical || unique.has(canonical)) continue;
    const aliases = [...(item.aliases || []), ...(item.brandNames || []), ...(item.genericNames || [])].filter(Boolean);
    const expiry = normalizeExpiryValue(item.batches?.[0]?.expiry || item.expiry || "");
    const stock = finiteOrNull(item.stockLeft ?? item.stock ?? item.current_stock);
    const reorderLevel = finiteOrNull(item.reorderLevel ?? item.reorder_level);
    const fields = {
      canonical, aliases: aliases.map(normalizeMedicineText),
      strength: normalizeMedicineText(item.strength),
      form: normalizeMedicineText(item.form || item.forms?.[0]),
      unit: normalizeMedicineText(item.unit || item.units?.[0]),
      barcode: normalizeIdentifier(item.barcode), supplier: normalizeMedicineText(item.supplier),
      shelf: normalizeMedicineText(item.shelf || item.location),
      batch: normalizeMedicineText(item.batches?.[0]?.batch || item.batch)
    };
    const expiryDate = expiryEndDate(expiry);
    const daysToExpiry = expiryDate ? Math.ceil((expiryDate.getTime() - now.getTime()) / 86400000) : null;
    unique.set(canonical, Object.freeze({
      id: String(item.id || `medicine-${position}`), position, item, name, fields,
      searchable: Object.values(fields).flat().filter(Boolean).join(" "),
      flags: Object.freeze({
        outOfStock: stock === 0,
        lowStock: stock !== null && reorderLevel !== null && stock <= reorderLevel,
        expiringSoon: daysToExpiry !== null && daysToExpiry >= 0 && daysToExpiry <= 90
      })
    }));
  }
  return Object.freeze([...unique.values()]);
}

export function searchMedicineFinder(index = [], query = "", { filter = "all", limit = index.length } = {}) {
  const wanted = normalizeMedicineText(query);
  return index
    .filter((entry) => filter === "all" || filter === "az" || entry.flags[filter] === true)
    .map((entry) => ({ entry, score: wanted ? finderScore(entry, wanted) : 1 }))
    .filter(({ score }) => score >= (wanted ? 0.54 : 0))
    .sort((left, right) => right.score - left.score || left.entry.name.localeCompare(right.entry.name))
    .slice(0, limit)
    .map(({ entry }) => entry);
}

export function medicineFinderClientScript(index, { bridgeId = "" } = {}) {
  const data = index.map((entry) => ({
    id: entry.id, name: entry.name, canonical: entry.fields.canonical, aliases: entry.fields.aliases,
    search: entry.searchable, flags: entry.flags
  }));
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  const bridge = JSON.stringify(String(bridgeId || ""));
  return `(()=>{const index=${json},bridgeId=${bridge},input=document.querySelector("#medicine-search"),count=document.querySelector("#review-count"),status=document.querySelector("#finder-status"),filter=document.querySelector("#medicine-filter"),cards=new Map([...document.querySelectorAll(".medicine-card")].map(card=>[card.dataset.finderId,card]));const norm=value=>String(value||"").normalize("NFKD").replace(/[\\u0300-\\u036f]/g,"").toLowerCase().replace(/[^a-z0-9%]+/g," ").trim();const distance=(a,b)=>{const row=Array.from({length:b.length+1},(_,i)=>i);for(let i=1;i<=a.length;i++){let previous=row[0];row[0]=i;for(let j=1;j<=b.length;j++){const saved=row[j];row[j]=Math.min(row[j]+1,row[j-1]+1,previous+(a[i-1]===b[j-1]?0:1));previous=saved}}return row[b.length]};const score=(entry,wanted)=>{if(!wanted)return 1;if(entry.canonical===wanted)return 100;if(entry.canonical.startsWith(wanted))return 90;if(entry.aliases.includes(wanted))return 85;if(entry.search.includes(wanted))return 75;const terms=entry.search.split(" "),queries=wanted.split(" ");if(queries.some(query=>/\\d/.test(query)&&!terms.includes(query)))return 0;return queries.every(query=>terms.some(term=>query.length>=4&&distance(query,term)<=Math.max(1,Math.ceil(query.length*.2))))?60:0};const apply=()=>{const wanted=norm(input.value),selected=filter.value;const scored=index.filter(entry=>selected==="all"||selected==="az"||entry.flags[selected]).map(entry=>({entry,value:score(entry,wanted)})).filter(result=>wanted?result.value>=54:result.value>0).sort((a,b)=>selected==="az"?a.entry.name.localeCompare(b.entry.name):b.value-a.value||a.entry.name.localeCompare(b.entry.name));const visible=new Set(scored.map(result=>result.entry.id));cards.forEach((card,id)=>card.hidden=!visible.has(id));count.textContent=scored.length+" of "+index.length+" medicines shown · Tap a medicine to view every field."};const receive=data=>{if(data?.type!=="ms20:finder-result"||data.bridgeId!==bridgeId)return;if(data.message)status.textContent=data.message;if(data.query){input.value=data.query;filter.value="all";apply();input.scrollIntoView({behavior:"smooth",block:"center"})}};let channel=null;if(bridgeId&&"BroadcastChannel" in window){channel=new BroadcastChannel("ms20-finder-"+bridgeId);channel.addEventListener("message",event=>receive(event.data))}const request=action=>{status.textContent=action==="barcode"?"Opening the shared barcode scanner…":"Starting shared voice capture…";const message={type:"ms20:finder-request",action,bridgeId};if(channel)channel.postMessage(message);else if(window.opener)window.opener.postMessage(message,"*");else status.textContent="Return to MS2.0 and reopen Print. The finder connection is unavailable."};input.addEventListener("input",()=>{status.textContent="";apply()});input.addEventListener("search",()=>{if(!input.value){filter.value="all";status.textContent="";apply()}});filter.addEventListener("change",apply);document.querySelector("#finder-scan").addEventListener("click",()=>request("barcode"));document.querySelector("#finder-voice").addEventListener("click",()=>request("voice"));window.addEventListener("message",event=>{if(event.source===window.opener)receive(event.data)});apply()})()`;
}

function finderScore(entry, wanted) {
  if (entry.fields.canonical === wanted || entry.fields.barcode === normalizeIdentifier(wanted)) return 1;
  if (entry.fields.canonical.startsWith(wanted)) return 0.93;
  if (entry.fields.aliases.includes(wanted)) return 0.9;
  if (entry.searchable.includes(wanted)) return 0.82;
  const wantedTerms = wanted.split(" ");
  const terms = entry.searchable.split(" ");
  if (wantedTerms.some((term) => /\d/.test(term) && !terms.includes(term))) return 0;
  return wantedTerms.every((query) => terms.some((term) => query.length >= 4 && editDistance(query, term) <= Math.max(1, Math.ceil(query.length * 0.2)))) ? 0.62 : 0;
}

function editDistance(left, right) {
  const row = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let i = 1; i <= left.length; i += 1) {
    let previous = row[0]; row[0] = i;
    for (let j = 1; j <= right.length; j += 1) {
      const saved = row[j];
      row[j] = Math.min(row[j] + 1, row[j - 1] + 1, previous + (left[i - 1] === right[j - 1] ? 0 : 1));
      previous = saved;
    }
  }
  return row[right.length];
}

function normalizeIdentifier(value) { return String(value || "").replace(/\s+/g, "").toLowerCase(); }
function finiteOrNull(value) { if (value === "" || value == null) return null; const number = Number(value); return Number.isFinite(number) ? number : null; }
