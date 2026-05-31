from __future__ import annotations

import json
import re
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "universal_medicines.json"
CATALOG_METADATA_PATH = Path(__file__).resolve().parents[1] / "data" / "universal_medicines.metadata.json"
MEDICINE_MATCH_LOG: deque[dict[str, object]] = deque(maxlen=200)

UNIT_ALIASES = {
    "tabs": "tablet",
    "tab": "tablet",
    "caps": "capsule",
    "cap": "capsule",
    "amp": "ampoule",
    "amps": "ampoule",
    "ampule": "ampoule",
    "ampules": "ampoule",
    "inj": "injection",
    "injs": "injection",
    "syr": "syrup",
    "susp": "suspension",
}

CATEGORY_ALIASES = {
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


def medicine_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _clean_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(text for item in value if (text := str(item or "").strip()))


def _clean_scalar(value: object) -> str:
    return str(value or "").strip()


def _normalize_units(value: object) -> tuple[str, ...]:
    return tuple(dict.fromkeys(UNIT_ALIASES.get(item.lower(), item.lower()) for item in _clean_list(value)))


def migrate_catalog_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Upgrade old catalog rows in memory so deployed snapshots stay compatible."""
    registration_numbers = _clean_list(raw.get("registration_numbers"))
    ppb_registration_number = _clean_scalar(raw.get("ppb_registration_number"))
    if ppb_registration_number and ppb_registration_number not in registration_numbers:
        registration_numbers = (*registration_numbers, ppb_registration_number)
    sources = _clean_list(raw.get("sources"))
    source = _clean_scalar(raw.get("source"))
    if source and source not in sources:
        sources = (*sources, source)
    category = _clean_scalar(raw.get("category"))
    return {
        "canonical_name": _clean_scalar(raw.get("canonical_name")),
        "generic_name": _clean_scalar(raw.get("generic_name")),
        "aliases": _clean_list(raw.get("aliases")),
        "brand_names": _clean_list(raw.get("brand_names")),
        "misspellings": _clean_list(raw.get("misspellings")),
        "shorthands": _clean_list(raw.get("shorthand") or raw.get("shorthands")),
        "units": _normalize_units(raw.get("units")),
        "category": CATEGORY_ALIASES.get(category, category),
        "dosage_forms": _clean_list(raw.get("dosage_forms")),
        "strengths": _clean_list(raw.get("strengths")),
        "packaging": _clean_list(raw.get("packaging")),
        "manufacturer_importer": _clean_list(raw.get("manufacturer_importer")),
        "sources": sources,
        "source": source or (sources[0] if sources else ""),
        "source_last_updated": _clean_scalar(raw.get("source_last_updated")),
        "registration_numbers": registration_numbers,
        "ppb_registration_number": ppb_registration_number or (registration_numbers[0] if registration_numbers else ""),
        "human_or_veterinary": _clean_scalar(raw.get("human_or_veterinary")) or "unknown",
        "otc_or_prescription": _clean_scalar(raw.get("otc_or_prescription")) or "unknown",
        "combination_medicine_components": _clean_list(raw.get("combination_medicine_components")),
    }


@dataclass(frozen=True)
class MedicineCatalogEntry:
    canonical_name: str
    generic_name: str = ""
    aliases: tuple[str, ...] = ()
    brand_names: tuple[str, ...] = ()
    misspellings: tuple[str, ...] = ()
    shorthands: tuple[str, ...] = ()
    units: tuple[str, ...] = ()
    category: str = ""
    dosage_forms: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    packaging: tuple[str, ...] = ()
    manufacturer_importer: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    source: str = ""
    source_last_updated: str = ""
    registration_numbers: tuple[str, ...] = ()
    ppb_registration_number: str = ""
    human_or_veterinary: str = "unknown"
    otc_or_prescription: str = "unknown"
    combination_medicine_components: tuple[str, ...] = ()

    @property
    def terms(self) -> tuple[str, ...]:
        seen: set[str] = set()
        terms: list[str] = []
        for term in (
            self.canonical_name,
            self.generic_name,
            *self.aliases,
            *self.brand_names,
            *self.misspellings,
            *self.shorthands,
            *self.strengths,
        ):
            key = str(term or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                terms.append(term)
        return tuple(terms)


@dataclass(frozen=True)
class MedicineMatch:
    canonical_name: str = ""
    matched_term: str = ""
    source: str = ""
    confidence: float = 0
    choices: tuple[str, ...] = ()
    in_inventory: bool = False

    @property
    def matched(self) -> bool:
        return bool(self.canonical_name)

    @property
    def ambiguous(self) -> bool:
        return len(self.choices) > 1


@lru_cache(maxsize=1)
def load_medicine_catalog() -> tuple[MedicineCatalogEntry, ...]:
    try:
        raw_entries = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return ()
    entries: list[MedicineCatalogEntry] = []
    for raw in raw_entries if isinstance(raw_entries, list) else []:
        if not isinstance(raw, dict):
            continue
        migrated = migrate_catalog_record(raw)
        canonical_name = migrated["canonical_name"]
        if not canonical_name:
            continue
        entries.append(
            MedicineCatalogEntry(
                canonical_name=canonical_name,
                generic_name=migrated["generic_name"],
                aliases=migrated["aliases"],
                brand_names=migrated["brand_names"],
                misspellings=migrated["misspellings"],
                shorthands=migrated["shorthands"],
                units=migrated["units"],
                category=migrated["category"],
                dosage_forms=migrated["dosage_forms"],
                strengths=migrated["strengths"],
                packaging=migrated["packaging"],
                manufacturer_importer=migrated["manufacturer_importer"],
                sources=migrated["sources"],
                source=migrated["source"],
                source_last_updated=migrated["source_last_updated"],
                registration_numbers=migrated["registration_numbers"],
                ppb_registration_number=migrated["ppb_registration_number"],
                human_or_veterinary=migrated["human_or_veterinary"],
                otc_or_prescription=migrated["otc_or_prescription"],
                combination_medicine_components=migrated["combination_medicine_components"],
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def load_catalog_metadata() -> dict[str, object]:
    try:
        data = json.loads(CATALOG_METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def catalog_medicine_names() -> list[str]:
    return [entry.canonical_name for entry in load_medicine_catalog()]


def _ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = medicine_key(text)
        if key and key not in seen:
            seen.add(key)
            unique.append(text)
    return unique


@lru_cache(maxsize=1)
def _catalog_term_index() -> dict[str, list[str]]:
    terms: dict[str, list[str]] = {}
    for entry in load_medicine_catalog():
        for term in entry.terms:
            key = medicine_key(term)
            choices = terms.setdefault(key, [])
            if entry.canonical_name not in choices:
                choices.append(entry.canonical_name)
    return terms


@lru_cache(maxsize=1)
def _entries_by_key() -> dict[str, tuple[MedicineCatalogEntry, ...]]:
    grouped: dict[str, list[MedicineCatalogEntry]] = {}
    for entry in load_medicine_catalog():
        grouped.setdefault(medicine_key(entry.canonical_name), []).append(entry)
    return {key: tuple(entries) for key, entries in grouped.items()}


def _inventory_canonical_map(inventory_names: Iterable[str]) -> tuple[list[str], dict[str, str]]:
    names = _ordered_unique(inventory_names)
    return names, {medicine_key(name): name for name in names}


def _available_choices(canonical_names: Iterable[str], inventory_by_key: Mapping[str, str]) -> list[str]:
    if not inventory_by_key:
        return _ordered_unique(canonical_names)
    inventory_choices: list[str] = []
    for canonical_name in canonical_names:
        canonical_key = medicine_key(canonical_name)
        entries = _entries_by_key().get(canonical_key, ())
        candidate_keys = [canonical_key, *(medicine_key(term) for entry in entries for term in entry.terms)]
        for key in candidate_keys:
            if key in inventory_by_key:
                inventory_choices.append(inventory_by_key[key])
    return _ordered_unique(inventory_choices or canonical_names)


@lru_cache(maxsize=128)
def _catalog_unique_aliases_cached(inventory_names: tuple[str, ...], compact_keys: bool) -> tuple[tuple[str, str], ...]:
    _, inventory_by_key = _inventory_canonical_map(inventory_names)
    restrict_to_inventory = bool(inventory_by_key)
    result: dict[str, str] = {}
    term_index = _catalog_term_index()
    for entry in load_medicine_catalog():
        for alias in entry.terms:
            alias_key = medicine_key(alias)
            choices = _available_choices(term_index.get(alias_key, ()), inventory_by_key)
            if restrict_to_inventory:
                choices = [choice for choice in choices if medicine_key(choice) in inventory_by_key]
            if len(choices) == 1:
                result[alias_key if compact_keys else alias] = choices[0]
    return tuple(result.items())


def catalog_unique_aliases(inventory_names: Iterable[str] | None = None, *, compact_keys: bool = True) -> dict[str, str]:
    names = tuple(_ordered_unique(inventory_names or ()))
    return dict(_catalog_unique_aliases_cached(names, compact_keys))


def catalog_entries_payload() -> list[dict[str, object]]:
    return [
        {
            "canonical_name": entry.canonical_name,
            "generic_name": entry.generic_name,
            "aliases": list(entry.aliases),
            "brand_names": list(entry.brand_names),
            "misspellings": list(entry.misspellings),
            "shorthand": list(entry.shorthands),
            "shorthands": list(entry.shorthands),
            "units": list(entry.units),
            "category": entry.category,
            "dosage_forms": list(entry.dosage_forms),
            "strengths": list(entry.strengths),
            "packaging": list(entry.packaging),
            "manufacturer_importer": list(entry.manufacturer_importer),
            "sources": list(entry.sources),
            "source": entry.source,
            "source_last_updated": entry.source_last_updated,
            "registration_numbers": list(entry.registration_numbers),
            "ppb_registration_number": entry.ppb_registration_number,
            "human_or_veterinary": entry.human_or_veterinary,
            "otc_or_prescription": entry.otc_or_prescription,
            "combination_medicine_components": list(entry.combination_medicine_components),
        }
        for entry in load_medicine_catalog()
    ]


def search_catalog_entries(query: str, *, limit: int = 20) -> list[dict[str, object]]:
    query_key = medicine_key(query)
    if not query_key:
        return []
    scored: list[tuple[float, MedicineCatalogEntry]] = []
    for entry in load_medicine_catalog():
        term_keys = [medicine_key(term) for term in entry.terms if medicine_key(term)]
        if query_key in term_keys:
            score = 1
        elif any(query_key in term_key or term_key in query_key for term_key in term_keys):
            score = 0.96
        else:
            score = max((SequenceMatcher(None, query_key, term_key).ratio() for term_key in term_keys), default=0)
        if score >= 0.62:
            scored.append((score, entry))
    scored.sort(key=lambda item: (-item[0], item[1].canonical_name.lower(), item[1].generic_name.lower()))
    payload_by_key: dict[str, dict[str, object]] = {}
    for score, entry in scored:
        key = "|".join((medicine_key(entry.canonical_name), medicine_key(entry.generic_name), ",".join(entry.dosage_forms)))
        if key not in payload_by_key:
            payload_by_key[key] = {
                "canonical_name": entry.canonical_name,
                "generic_name": entry.generic_name,
                "aliases": list(entry.aliases),
                "brand_names": list(entry.brand_names),
                "units": list(entry.units),
                "category": entry.category,
                "dosage_forms": list(entry.dosage_forms),
                "strengths": list(entry.strengths),
                "packaging": list(entry.packaging),
                "manufacturer_importer": list(entry.manufacturer_importer),
                "ppb_registration_number": entry.ppb_registration_number,
                "source": entry.source,
                "source_last_updated": entry.source_last_updated,
                "human_or_veterinary": entry.human_or_veterinary,
                "otc_or_prescription": entry.otc_or_prescription,
                "combination_medicine_components": list(entry.combination_medicine_components),
                "confidence": round(score, 3),
                "ai_used": False,
            }
        if len(payload_by_key) >= max(1, min(limit, 100)):
            break
    return list(payload_by_key.values())


def _match_local_medicine(
    query: str,
    *,
    inventory_names: Iterable[str] = (),
    pharmacy_aliases: Mapping[str, str] | None = None,
) -> MedicineMatch:
    text = str(query or "").strip()
    text_key = medicine_key(text)
    if not text_key:
        return MedicineMatch()
    inventory, inventory_by_key = _inventory_canonical_map(inventory_names)
    pharmacy_aliases = {medicine_key(key): value for key, value in (pharmacy_aliases or {}).items() if medicine_key(key)}
    if text_key in inventory_by_key:
        return MedicineMatch(inventory_by_key[text_key], text, "inventory_exact", 1, in_inventory=True)

    alias_target = str(pharmacy_aliases.get(text_key) or "").strip()
    if alias_target:
        prefix_choices = [
            name for name in inventory
            if medicine_key(name).startswith(text_key) or text_key.startswith(medicine_key(name))
        ]
        if len(text_key) <= 3 and len(prefix_choices) > 1:
            return MedicineMatch(source="pharmacy_alias_ambiguous", confidence=1, choices=tuple(prefix_choices), in_inventory=True)
        resolved = inventory_by_key.get(medicine_key(alias_target), alias_target)
        return MedicineMatch(resolved, text, "pharmacy_alias", 1, in_inventory=medicine_key(resolved) in inventory_by_key)

    term_index = _catalog_term_index()
    if text_key in term_index:
        choices = _available_choices(term_index[text_key], inventory_by_key)
        if len(choices) > 1:
            return MedicineMatch(source="catalog_alias_ambiguous", confidence=1, choices=tuple(choices), in_inventory=any(medicine_key(choice) in inventory_by_key for choice in choices))
        if choices:
            choice = choices[0]
            return MedicineMatch(choice, text, "catalog_alias", 1, in_inventory=medicine_key(choice) in inventory_by_key)

    prefix_choices = [
        name for name in inventory
        if medicine_key(name).startswith(text_key) or text_key.startswith(medicine_key(name))
    ]
    if len(prefix_choices) == 1 and len(text_key) >= 4:
        return MedicineMatch(prefix_choices[0], text, "inventory_prefix", 0.94, in_inventory=True)
    if len(prefix_choices) > 1:
        return MedicineMatch(source="inventory_prefix_ambiguous", confidence=0.9, choices=tuple(prefix_choices[:3]), in_inventory=True)

    fuzzy_scores: dict[str, float] = {}
    for inventory_name in inventory:
        fuzzy_scores[inventory_name] = max(fuzzy_scores.get(inventory_name, 0), SequenceMatcher(None, text_key, medicine_key(inventory_name)).ratio())
    if inventory_by_key:
        for alias_key, choice in catalog_unique_aliases(inventory, compact_keys=True).items():
            score = SequenceMatcher(None, text_key, alias_key).ratio()
            fuzzy_scores[choice] = max(fuzzy_scores.get(choice, 0), score)
    else:
        for alias_key, canonical_names in term_index.items():
            score = SequenceMatcher(None, text_key, alias_key).ratio()
            for choice in canonical_names:
                fuzzy_scores[choice] = max(fuzzy_scores.get(choice, 0), score)
    scored = sorted(((score, name) for name, score in fuzzy_scores.items()), reverse=True)
    if not scored:
        return MedicineMatch()
    top_score, top_name = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0
    if top_score >= 0.82 and top_score - second_score >= 0.08:
        return MedicineMatch(top_name, text, "fuzzy", top_score, in_inventory=medicine_key(top_name) in inventory_by_key)
    if top_score >= 0.62:
        return MedicineMatch(source="fuzzy_ambiguous", confidence=top_score, choices=tuple(name for _, name in scored[:3]), in_inventory=any(medicine_key(name) in inventory_by_key for _, name in scored[:3]))
    return MedicineMatch()


def _log_medicine_match(query: str, match: MedicineMatch) -> None:
    MEDICINE_MATCH_LOG.append(
        {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "query": str(query or "")[:80],
            "matched": match.matched,
            "canonical_name": match.canonical_name,
            "source": match.source or "local_no_match",
            "confidence": round(float(match.confidence or 0), 3),
            "ambiguous": match.ambiguous,
            "choices": list(match.choices[:3]),
            "ai_used": False,
        }
    )


def match_local_medicine(
    query: str,
    *,
    inventory_names: Iterable[str] = (),
    pharmacy_aliases: Mapping[str, str] | None = None,
) -> MedicineMatch:
    match = _match_local_medicine(
        query,
        inventory_names=inventory_names,
        pharmacy_aliases=pharmacy_aliases,
    )
    _log_medicine_match(query, match)
    return match


def medicine_match_snapshot() -> dict[str, object]:
    recent = list(MEDICINE_MATCH_LOG)
    return {
        "total_logged": len(recent),
        "by_source": dict(Counter(str(item["source"]) for item in recent)),
        "recent": recent[-10:],
        "ai_used": False,
    }
