from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "app" / "data" / "universal_medicines.json"
DEFAULT_METADATA = PROJECT_ROOT / "app" / "data" / "universal_medicines.metadata.json"
DEFAULT_SEEDS = PROJECT_ROOT / "app" / "data" / "kenya_common_medicine_seeds.json"
PPB_REGISTERED_PRODUCTS_URL = (
    "https://products.pharmacyboardkenya.org/ppb_admin/pages/"
    "public_view_retention_products.php"
)
PPB_XCRUD_URL = "https://products.pharmacyboardkenya.org/ppb_admin/xcrud/xcrud_ajax.php"
KEML_2023_URL = "https://kemsa.go.ke/download/file/8e7d9c438ecc1a468d9d7615a87688df.pdf"
WHO_KEML_2023_URL = (
    "https://www.who.int/publications/m/item/"
    "kenya--essential-medicines-list-2023-%28english%29"
)

REQUESTED_UNITS = (
    "tablet",
    "tab",
    "capsule",
    "cap",
    "strip",
    "box",
    "bottle",
    "vial",
    "ampoule",
    "syrup",
    "cream",
    "ointment",
    "gel",
    "drops",
    "eye drops",
    "ear drops",
    "sachet",
    "pack",
    "tube",
    "inhaler",
    "injection",
    "suspension",
)

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pain/fever", ("paracetamol", "ibuprofen", "diclofenac", "aspirin", "naproxen", "celecoxib", "ketoprofen", "tramadol")),
    ("antibiotics", ("amoxic", "clavulan", "azithro", "cef", "cipro", "doxy", "metronidazole", "penicillin", "gentamicin", "erythro", "cotrimox", "co-trimox")),
    ("malaria", ("artem", "lumefantrine", "artesunate", "quinine", "piperaquine", "antimalarial")),
    ("cough/cold", ("cough", "dextromethorphan", "guaifenesin", "ambroxol", "bromhexine", "pseudoephedrine", "phenylephrine")),
    ("allergy", ("cetirizine", "loratadine", "chlorpheniramine", "fexofenadine", "antihistamine")),
    ("stomach/ulcer", ("omeprazole", "pantoprazole", "esomeprazole", "antacid", "magnesium hydroxide", "aluminium hydroxide")),
    ("diarrhea/ORS", ("oral rehydration", "ors", "loperamide", "diarrhea", "diarrhoea", "zinc sulphate", "zinc sulfate")),
    ("vitamins", ("vitamin", "multivitamin", "folic acid", "ascorbic", "cyanocobalamin")),
    ("antifungals", ("clotrimazole", "fluconazole", "ketoconazole", "terbinafine", "nystatin", "miconazole")),
    ("skin creams", ("cream", "ointment", "lotion", "topical", "hydrocortisone")),
    ("eye/ear medicines", ("ophthalmic", "otic", "eye drop", "ear drop")),
    ("diabetes", ("insulin", "metformin", "gliclazide", "glibenclamide")),
    ("hypertension", ("losartan", "amlodipine", "nifedipine", "telmisartan", "hydrochlorothiazide", "enalapril", "valsartan")),
    ("asthma", ("salbutamol", "montelukast", "budesonide", "inhaler")),
    ("antiseptics", ("povidone", "iodine", "chlorhexidine", "cetrimide", "antiseptic", "sanitizer")),
    ("dewormers", ("albendazole", "mebendazole", "praziquantel")),
    ("pregnancy supplements", ("prenatal", "pregnancy", "iron folic")),
    ("baby medicines", ("paediatric", "pediatric", "infant", "baby")),
    ("family planning", ("contraceptive", "levonorgestrel", "ethinylestradiol", "medroxyprogesterone")),
    ("emergency medicines", ("adrenaline", "epinephrine", "atropine")),
    ("nutrition", ("glucose", "nutrition", "electrolyte")),
    ("injections", ("injection", "injectable", "vial", "ampoule")),
)

LEGACY_CATEGORY_ALIASES = {
    "pain relief": "pain/fever",
    "antibiotic": "antibiotics",
    "rehydration": "diarrhea/ORS",
    "digestive health": "stomach/ulcer",
    "diabetes care": "diabetes",
    "cough and cold": "cough/cold",
    "topical": "skin creams",
    "water treatment": "antiseptics",
    "general retail": "OTC/common counter medicines",
    "medical supplies": "OTC/common counter medicines",
}


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_tbody = False
        self.in_row = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tbody":
            self.in_tbody = True
        elif self.in_tbody and tag == "tr":
            self.in_row = True
            self.row = []
        elif self.in_row and tag == "td":
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            self.in_cell = False
            self.row.append(clean_text(" ".join(self.cell_parts)))
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if self.row:
                self.rows.append(self.row)
        elif tag == "tbody":
            self.in_tbody = False


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip(" \t\r\n.,;")


def unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        key = re.sub(r"[^a-z0-9]+", "", text.lower())
        if text and key and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def parse_rows(html: str) -> list[dict[str, str]]:
    parser = TableParser()
    parser.feed(html)
    records: list[dict[str, str]] = []
    for cells in parser.rows:
        cells = cells[-11:]
        if len(cells) < 10:
            continue
        if len(cells) == 11:
            cells = cells[1:]
        records.append(
            {
                "registration_number": cells[0],
                "trade_name": cells[1],
                "generic_name": cells[2],
                "dosage_form": cells[3],
                "country_of_origin": cells[4],
                "local_foreign": cells[5],
                "mah_company": cells[6],
                "local_representative": cells[7],
                "registration_date": cells[8],
                "expiry_date": cells[9],
            }
        )
    return records


def hidden_value(html: str, name: str) -> str:
    match = re.search(rf'name="{re.escape(name)}"\s+value="([^"]*)"', html)
    return unescape(match.group(1)) if match else ""


def max_start(html: str) -> int:
    starts = [int(value) for value in re.findall(r'data-start="(\d+)"', html)]
    return max(starts or [0])


def fetch_ppb_products(*, max_pages: int = 0) -> list[dict[str, str]]:
    session = requests.Session()
    response = session.get(PPB_REGISTERED_PRODUCTS_URL, timeout=45)
    response.raise_for_status()
    html = response.text
    records = parse_rows(html)
    final_start = max_start(html)
    page_starts = list(range(10, final_start + 1, 10))
    if max_pages:
        page_starts = page_starts[: max(max_pages - 1, 0)]
    for index, start in enumerate(page_starts, start=2):
        payload = {
            "xcrud[key]": hidden_value(html, "key"),
            "xcrud[orderby]": hidden_value(html, "orderby") or "tbl_vw_all_items_prims_gbt.registrationdate",
            "xcrud[order]": hidden_value(html, "order") or "desc",
            "xcrud[start]": str(start),
            "xcrud[limit]": hidden_value(html, "limit") or "10",
            "xcrud[instance]": hidden_value(html, "instance"),
            "xcrud[task]": "list",
        }
        response = session.post(PPB_XCRUD_URL, data=payload, timeout=45)
        response.raise_for_status()
        html = response.text
        if "xcrud-error" in html:
            raise RuntimeError(clean_text(re.sub(r"<[^>]+>", " ", html)))
        records.extend(parse_rows(html))
        if index % 25 == 0 or index == len(page_starts) + 1:
            print(f"PPB pages imported: {index}/{len(page_starts) + 1}", file=sys.stderr)
    by_registration: dict[str, dict[str, str]] = {}
    for record in records:
        key = record["registration_number"] or f"{record['trade_name']}|{record['generic_name']}|{record['dosage_form']}"
        by_registration[key.lower()] = record
    return list(by_registration.values())


def source_checksum(url: str) -> str:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return hashlib.sha256(response.content).hexdigest()


def stripped_product_name(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|kg|ml|iu|%|w/v|v/v)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text


def inferred_units(dosage_forms: Iterable[str]) -> list[str]:
    text = " ".join(dosage_forms).lower()
    units: list[str] = []
    if "tablet" in text or "pessar" in text or "lozenge" in text:
        units += ["tablet", "tab", "strip", "box"]
    if "capsule" in text:
        units += ["capsule", "cap", "strip", "box"]
    if "syrup" in text:
        units += ["syrup", "bottle"]
    if "suspension" in text:
        units += ["suspension", "bottle"]
    if "cream" in text:
        units += ["cream", "tube"]
    if "ointment" in text:
        units += ["ointment", "tube"]
    if "gel" in text:
        units += ["gel", "tube"]
    if "ophthalmic" in text or "eye" in text:
        units += ["eye drops", "drops", "bottle"]
    if "otic" in text or "ear" in text:
        units += ["ear drops", "drops", "bottle"]
    if "drop" in text and not any("drops" in unit for unit in units):
        units += ["drops", "bottle"]
    if "vial" in text:
        units += ["vial", "injection", "box"]
    if "ampoule" in text or "ampule" in text:
        units += ["ampoule", "injection", "box"]
    if "inject" in text or "solution for infusion" in text:
        units += ["injection", "vial", "ampoule", "box"]
    if "inhal" in text:
        units += ["inhaler", "pack", "box"]
    if "sachet" in text or "granule" in text or "powder" in text:
        units += ["sachet", "pack", "box"]
    if "solution" in text or "liquid" in text or "emulsion" in text:
        units += ["bottle"]
    return unique(units or ["pack", "box"])


def category_for(*values: str) -> str:
    text = " ".join(values).lower()
    for category, keywords in CATEGORY_RULES:
        if any(keyword in text for keyword in keywords):
            return category
    return "other registered medicine"


def seed_entries(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def ppb_entry(record: dict[str, str]) -> dict[str, Any] | None:
    trade_name = clean_text(record["trade_name"])
    generic_name = clean_text(record["generic_name"])
    canonical_name = stripped_product_name(trade_name) or stripped_product_name(generic_name)
    if not canonical_name:
        return None
    dosage_form = clean_text(record["dosage_form"])
    aliases = unique([trade_name, stripped_product_name(trade_name), generic_name, stripped_product_name(generic_name)])
    return {
        "canonical_name": canonical_name,
        "generic_name": generic_name,
        "aliases": aliases,
        "brand_names": unique([trade_name]),
        "misspellings": [],
        "shorthand": [],
        "units": inferred_units([dosage_form]),
        "category": category_for(trade_name, generic_name, dosage_form),
        "dosage_forms": unique([dosage_form]),
        "sources": ["PPB registered products public registry"],
        "registration_numbers": unique([record["registration_number"]]),
    }


def merge_entry(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key in ("aliases", "brand_names", "misspellings", "shorthand", "units", "dosage_forms", "sources", "registration_numbers"):
        target[key] = unique([*target.get(key, []), *incoming.get(key, [])])
    if not target.get("generic_name") and incoming.get("generic_name"):
        target["generic_name"] = incoming["generic_name"]
    if target.get("category") in {"", "other registered medicine"} and incoming.get("category"):
        target["category"] = incoming["category"]


def normalize_seed(seed: dict[str, Any]) -> dict[str, Any]:
    dosage_forms = unique(seed.get("dosage_forms", []))
    return {
        "canonical_name": clean_text(seed.get("canonical_name")),
        "generic_name": clean_text(seed.get("generic_name")),
        "aliases": unique(seed.get("aliases", [])),
        "brand_names": unique(seed.get("brand_names", [])),
        "misspellings": unique(seed.get("misspellings", [])),
        "shorthand": unique(seed.get("shorthand", seed.get("shorthands", []))),
        "units": unique(seed.get("units", [])),
        "category": LEGACY_CATEGORY_ALIASES.get(
            clean_text(seed.get("category")),
            clean_text(seed.get("category")) or category_for(seed.get("canonical_name", "")),
        ),
        "dosage_forms": dosage_forms,
        "sources": unique([*seed.get("sources", []), "Curated Kenyan retail pharmacy seed"]),
        "registration_numbers": unique(seed.get("registration_numbers", [])),
    }


def build_catalog(products: Iterable[dict[str, str]], seeds: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for raw in seeds:
        entry = normalize_seed(raw)
        if entry["canonical_name"]:
            entries[f"seed|{entry['canonical_name'].lower()}"] = entry
    for product in products:
        entry = ppb_entry(product)
        if not entry:
            continue
        key = "|".join(
            (
                entry["canonical_name"].lower(),
                entry["generic_name"].lower(),
                ",".join(value.lower() for value in entry["dosage_forms"]),
            )
        )
        existing = entries.get(key)
        if existing:
            merge_entry(existing, entry)
        else:
            entries[key] = entry
    return sorted(entries.values(), key=lambda item: (item["canonical_name"].lower(), item["generic_name"].lower()))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build PharMareen's local Kenya-first medicine catalog.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata-output", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--max-pages", type=int, default=0, help="Limit PPB pages for importer smoke tests only.")
    parser.add_argument("--skip-keml-checksum", action="store_true")
    args = parser.parse_args()

    products = fetch_ppb_products(max_pages=args.max_pages)
    seeds = seed_entries(args.seeds)
    catalog = build_catalog(products, seeds)
    generated_at = datetime.now(timezone.utc).isoformat()
    categories = Counter(entry["category"] for entry in catalog)
    metadata = {
        "generated_at": generated_at,
        "catalog_entry_count": len(catalog),
        "ppb_registered_product_count": len(products),
        "curated_seed_count": len(seeds),
        "categories": dict(sorted(categories.items())),
        "required_unit_vocabulary": list(REQUESTED_UNITS),
        "sources": [
            {"name": "PPB registered products public registry", "url": PPB_REGISTERED_PRODUCTS_URL, "imported_rows": len(products)},
            {"name": "Kenya Essential Medicines List 2023", "url": KEML_2023_URL, "sha256": "" if args.skip_keml_checksum else source_checksum(KEML_2023_URL)},
            {"name": "WHO KEML 2023 publication page", "url": WHO_KEML_2023_URL},
            {"name": "Curated Kenyan retail pharmacy aliases", "path": str(args.seeds.relative_to(PROJECT_ROOT)), "entries": len(seeds)},
        ],
        "notes": [
            "Runtime medicine matching is local-only and does not call OpenAI.",
            "The PPB public registry supplies registered product trade names, APIs, and dosage forms.",
            "KEML 2023 is recorded as the official essential-medicines baseline; PPB API names provide the importable product-level generic coverage.",
        ],
    }
    write_json(args.output, catalog)
    write_json(args.metadata_output, metadata)
    print(json.dumps({"catalog_entries": len(catalog), "ppb_products": len(products), "categories": len(categories)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
