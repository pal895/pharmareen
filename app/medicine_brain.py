from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.training_store import TrainingStore


MATCHED = "matched"
AMBIGUOUS = "ambiguous"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class MedicineBrainResult:
    raw_text: str
    normalized_text: str
    status: str
    medicine_name: str | None
    canonical_id: str | None
    candidates: list[str]
    confidence: float
    quantity: int | None = None
    payment: str | None = None
    form: str | None = None
    unit: str | None = None
    dose: str | None = None
    packaging: str | None = None
    action: str | None = None
    ai_calls_used: bool = False
    token_safe: bool = True

    @property
    def matched(self) -> bool:
        return self.status == MATCHED

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "status": self.status,
            "medicine_name": self.medicine_name,
            "canonical_id": self.canonical_id,
            "candidates": self.candidates,
            "confidence": self.confidence,
            "quantity": self.quantity,
            "payment": self.payment,
            "form": self.form,
            "unit": self.unit,
            "dose": self.dose,
            "packaging": self.packaging,
            "action": self.action,
            "ai_calls_used": self.ai_calls_used,
            "token_safe": self.token_safe,
        }


@dataclass(frozen=True)
class _MedicineProfile:
    canonical_id: str
    name: str
    aliases: tuple[str, ...]


class MedicineBrain:
    def __init__(self, store: TrainingStore | None = None) -> None:
        self.store = store or TrainingStore()
        self.forms_units = self.store.forms_units()
        self.aliases = self.store.aliases()
        self.profiles = self._load_profiles()
        self.profile_by_name = {normalize_key(profile.name): profile for profile in self.profiles}

    def analyze(self, text: str) -> MedicineBrainResult:
        raw_text = text or ""
        normalized = normalize_text(raw_text)
        working_compact = compact_key(normalized)

        payment, working_compact = self._extract_payment(working_compact)
        dose, unit, working_compact = self._extract_dose(normalized, working_compact)
        action, working_compact = self._extract_action(working_compact)
        form, working_compact = self._extract_named_item("forms", working_compact)
        packaging, working_compact = self._extract_named_item("packaging", working_compact)
        quantity, working_compact = self._extract_quantity(working_compact)
        medicine_key = compact_key(working_compact)

        status, medicine_name, canonical_id, candidates, confidence = self._resolve_medicine(
            medicine_key
        )

        return MedicineBrainResult(
            raw_text=raw_text,
            normalized_text=normalized,
            status=status,
            medicine_name=medicine_name,
            canonical_id=canonical_id,
            candidates=candidates,
            confidence=confidence,
            quantity=quantity,
            payment=payment,
            form=form,
            unit=unit,
            dose=dose,
            packaging=packaging,
            action=action,
            ai_calls_used=False,
            token_safe=True,
        )

    def _load_profiles(self) -> list[_MedicineProfile]:
        data = self.store.medicine_profiles()
        profiles: list[_MedicineProfile] = []
        for item in data.get("medicines", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            canonical_id = str(item.get("canonical_id") or compact_key(name)).strip()
            aliases = [name]
            aliases.extend(str(alias) for alias in item.get("aliases", []) if str(alias).strip())
            if name and canonical_id:
                profiles.append(
                    _MedicineProfile(
                        canonical_id=canonical_id,
                        name=name,
                        aliases=tuple(dict.fromkeys(aliases)),
                    )
                )
        return profiles

    def _extract_payment(self, working_compact: str) -> tuple[str | None, str]:
        payment_aliases = self._payment_aliases()
        for alias, payment in sorted(payment_aliases.items(), key=lambda item: len(item[0]), reverse=True):
            alias_key = compact_key(alias)
            if not alias_key:
                continue
            if working_compact.endswith(alias_key) and (
                len(alias_key) > 1 or re.search(r"\d" + re.escape(alias_key) + r"$", working_compact)
            ):
                return payment, working_compact[: -len(alias_key)]
        return None, working_compact

    def _extract_dose(
        self,
        normalized: str,
        working_compact: str,
    ) -> tuple[str | None, str | None, str]:
        unit_aliases = self._unit_aliases()
        if not unit_aliases:
            return None, None, working_compact

        alias_pattern = "|".join(
            re.escape(alias).replace("\\ ", r"\s+") for alias in sorted(unit_aliases, key=len, reverse=True)
        )
        match = re.search(rf"\b(\d+(?:\.\d+)?)\s*({alias_pattern})\b", normalized)
        if not match:
            return None, None, working_compact

        amount = match.group(1)
        matched_alias = match.group(2)
        unit = unit_aliases[normalize_key(matched_alias)]
        dose = f"{amount}{unit}"
        working_compact = strip_once(working_compact, compact_key(amount + matched_alias))
        return dose, unit, working_compact

    def _extract_action(self, working_compact: str) -> tuple[str | None, str]:
        action_aliases = {
            "stock": "stock_check",
            "stockcheck": "stock_check",
            "checkstock": "stock_check",
            "bei": "price_check",
            "price": "price_check",
        }
        for alias, action in sorted(action_aliases.items(), key=lambda item: len(item[0]), reverse=True):
            if alias in working_compact:
                return action, strip_once(working_compact, alias)
        return None, working_compact

    def _extract_named_item(self, section: str, working_compact: str) -> tuple[str | None, str]:
        data = self.forms_units.get(section, {})
        aliases: dict[str, str] = {}
        for canonical, details in data.items():
            aliases[compact_key(canonical)] = canonical
            for alias in details.get("aliases", []):
                aliases[compact_key(alias)] = canonical

        memory_key = {
            "forms": "form_aliases",
            "packaging": "packaging_aliases",
        }.get(section)
        if memory_key:
            memory = self.store.pharmacy_memory()
            for alias, canonical in memory.get(memory_key, {}).items():
                aliases[compact_key(alias)] = str(canonical)

        for alias, canonical in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
            if alias and alias in working_compact:
                return canonical, strip_once(working_compact, alias)
        return None, working_compact

    def _extract_quantity(self, working_compact: str) -> tuple[int | None, str]:
        match = re.search(r"\d+", working_compact)
        if not match:
            return None, working_compact
        quantity = int(match.group(0))
        return quantity, working_compact[: match.start()] + working_compact[match.end() :]

    def _resolve_medicine(
        self,
        medicine_key: str,
    ) -> tuple[str, str | None, str | None, list[str], float]:
        if not medicine_key:
            return UNKNOWN, None, None, [], 0.0

        memory_targets = self._pharmacy_medicine_alias_targets()
        if medicine_key in memory_targets:
            targets = memory_targets[medicine_key]
            if len(targets) > 1:
                return AMBIGUOUS, None, None, sorted(targets), 0.55
            return self._matched_profile(next(iter(targets)), 0.99)

        shorthand_candidates = self.aliases.get("shorthand_candidates", {})
        if medicine_key in shorthand_candidates:
            candidates = [str(name) for name in shorthand_candidates[medicine_key]]
            return AMBIGUOUS, None, None, candidates, 0.35

        alias_targets = self._medicine_alias_targets()
        if medicine_key in alias_targets:
            targets = alias_targets[medicine_key]
            if len(targets) > 1:
                return AMBIGUOUS, None, None, sorted(targets), 0.55
            return self._matched_profile(next(iter(targets)), 0.97)

        short_candidates = self._prefix_candidates(medicine_key)
        if len(short_candidates) > 1:
            return AMBIGUOUS, None, None, short_candidates, 0.4
        if len(short_candidates) == 1 and len(medicine_key) <= 2:
            return self._matched_profile(short_candidates[0], 0.74)

        fuzzy_matches = self._fuzzy_candidates(medicine_key)
        if not fuzzy_matches:
            return UNKNOWN, None, None, [], 0.0

        best_name, best_score = fuzzy_matches[0]
        tied = [name for name, score in fuzzy_matches if abs(score - best_score) < 0.03]
        if len(tied) > 1:
            if best_score < 0.7:
                return UNKNOWN, None, None, [], round(best_score, 2)
            return AMBIGUOUS, None, None, sorted(dict.fromkeys(tied)), round(best_score, 2)
        if best_score >= 0.82:
            return self._matched_profile(best_name, round(best_score, 2))
        return UNKNOWN, None, None, [], round(best_score, 2)

    def _matched_profile(
        self,
        medicine_name: str,
        confidence: float,
    ) -> tuple[str, str | None, str | None, list[str], float]:
        profile = self.profile_by_name.get(normalize_key(medicine_name))
        canonical_id = profile.canonical_id if profile else compact_key(medicine_name)
        name = profile.name if profile else medicine_name
        return MATCHED, name, canonical_id, [name], confidence

    def _pharmacy_medicine_alias_targets(self) -> dict[str, set[str]]:
        targets: dict[str, set[str]] = {}
        memory = self.store.pharmacy_memory()
        for alias, medicine_name in memory.get("medicine_aliases", {}).items():
            targets.setdefault(compact_key(alias), set()).add(str(medicine_name))
        return targets

    def _medicine_alias_targets(self) -> dict[str, set[str]]:
        targets: dict[str, set[str]] = {}
        for profile in self.profiles:
            for alias in profile.aliases:
                targets.setdefault(compact_key(alias), set()).add(profile.name)

        for alias, medicine_name in self.aliases.get("medicine_aliases", {}).items():
            targets.setdefault(compact_key(alias), set()).add(str(medicine_name))

        memory = self.store.pharmacy_memory()
        for alias, medicine_name in memory.get("medicine_aliases", {}).items():
            targets.setdefault(compact_key(alias), set()).add(str(medicine_name))

        return targets

    def _payment_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for canonical, details in self.forms_units.get("payments", {}).items():
            aliases[canonical] = canonical
            for alias in details.get("aliases", []):
                aliases[str(alias)] = canonical

        for alias, canonical in self.aliases.get("payment_aliases", {}).items():
            aliases[str(alias)] = str(canonical)

        memory = self.store.pharmacy_memory()
        for alias, canonical in memory.get("payment_aliases", {}).items():
            aliases[str(alias)] = str(canonical)
        return aliases

    def _unit_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for canonical, details in self.forms_units.get("units", {}).items():
            aliases[normalize_key(canonical)] = canonical
            for alias in details.get("aliases", []):
                aliases[normalize_key(alias)] = canonical
        memory = self.store.pharmacy_memory()
        for alias, canonical in memory.get("unit_aliases", {}).items():
            aliases[normalize_key(alias)] = str(canonical)
        return aliases

    def _prefix_candidates(self, medicine_key: str) -> list[str]:
        if len(medicine_key) > 2:
            return []
        candidates: list[str] = []
        for profile in self.profiles:
            keys = [compact_key(profile.name), *(compact_key(alias) for alias in profile.aliases)]
            if any(key.startswith(medicine_key) for key in keys):
                candidates.append(profile.name)
        return sorted(dict.fromkeys(candidates))

    def _fuzzy_candidates(self, medicine_key: str) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for profile in self.profiles:
            for alias in profile.aliases:
                alias_key = compact_key(alias)
                if not alias_key:
                    continue
                score = SequenceMatcher(None, medicine_key, alias_key).ratio()
                scores[profile.name] = max(scores.get(profile.name, 0.0), score)
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def normalize_text(value: str) -> str:
    text = str(value or "").lower().strip()
    text = text.replace("m-pesa", "mpesa").replace("m pesa", "mpesa")
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    text = re.sub(r"([a-z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([a-z])", r"\1 \2", text)
    return " ".join(text.split())


def normalize_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def compact_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def strip_once(value: str, needle: str) -> str:
    if not needle:
        return value
    index = value.find(needle)
    if index == -1:
        return value
    return value[:index] + value[index + len(needle) :]
