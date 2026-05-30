from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "universal_medicines.json"


def medicine_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _clean_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(text for item in value if (text := str(item or "").strip()))


@dataclass(frozen=True)
class MedicineCatalogEntry:
    canonical_name: str
    aliases: tuple[str, ...] = ()
    misspellings: tuple[str, ...] = ()
    shorthands: tuple[str, ...] = ()
    units: tuple[str, ...] = ()
    category: str = ""

    @property
    def terms(self) -> tuple[str, ...]:
        seen: set[str] = set()
        terms: list[str] = []
        for term in (self.canonical_name, *self.aliases, *self.misspellings, *self.shorthands):
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
        canonical_name = str(raw.get("canonical_name") or "").strip()
        if not canonical_name:
            continue
        entries.append(
            MedicineCatalogEntry(
                canonical_name=canonical_name,
                aliases=_clean_list(raw.get("aliases")),
                misspellings=_clean_list(raw.get("misspellings")),
                shorthands=_clean_list(raw.get("shorthands")),
                units=_clean_list(raw.get("units")),
                category=str(raw.get("category") or "").strip(),
            )
        )
    return tuple(entries)


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


def _catalog_term_index() -> dict[str, list[str]]:
    terms: dict[str, list[str]] = {}
    for entry in load_medicine_catalog():
        for term in entry.terms:
            key = medicine_key(term)
            choices = terms.setdefault(key, [])
            if entry.canonical_name not in choices:
                choices.append(entry.canonical_name)
    return terms


def _inventory_canonical_map(inventory_names: Iterable[str]) -> tuple[list[str], dict[str, str]]:
    names = _ordered_unique(inventory_names)
    return names, {medicine_key(name): name for name in names}


def _available_choices(canonical_names: Iterable[str], inventory_by_key: Mapping[str, str]) -> list[str]:
    entries_by_key = {medicine_key(entry.canonical_name): entry for entry in load_medicine_catalog()}
    inventory_choices: list[str] = []
    for canonical_name in canonical_names:
        canonical_key = medicine_key(canonical_name)
        entry = entries_by_key.get(canonical_key)
        candidate_keys = [canonical_key, *(medicine_key(term) for term in entry.terms)] if entry else [canonical_key]
        for key in candidate_keys:
            if key in inventory_by_key:
                inventory_choices.append(inventory_by_key[key])
    return _ordered_unique(inventory_choices or canonical_names)


def catalog_unique_aliases(inventory_names: Iterable[str] | None = None, *, compact_keys: bool = True) -> dict[str, str]:
    _, inventory_by_key = _inventory_canonical_map(inventory_names or ())
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
    return result


def catalog_entries_payload() -> list[dict[str, object]]:
    return [
        {
            "canonical_name": entry.canonical_name,
            "aliases": list(entry.aliases),
            "misspellings": list(entry.misspellings),
            "shorthands": list(entry.shorthands),
            "units": list(entry.units),
            "category": entry.category,
        }
        for entry in load_medicine_catalog()
    ]


def match_local_medicine(
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
    for alias_key, canonical_names in term_index.items():
        score = SequenceMatcher(None, text_key, alias_key).ratio()
        for choice in _available_choices(canonical_names, inventory_by_key):
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
