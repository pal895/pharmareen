from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from app.training_store import TrainingStore


PERSONALITY_SETTINGS_FILE = "personality_settings.json"
PERSONALITY_STATE_FILE = "personality_state.json"


DEFAULT_PERSONALITY_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "morning_greeting_enabled": True,
    "end_of_day_enabled": True,
    "morning_window_start": "06:00",
    "morning_window_end": "11:30",
    "end_of_day_window_start": "23:30",
    "end_of_day_window_end": "23:59",
    "morning_template": "Morning {name}. Ready for another strong pharmacy day?",
    "morning_template_no_name": "Morning. Ready for another strong pharmacy day?",
    "end_of_day_template": "Great work today. You handled {sales_count} sales with clear records.",
    "end_of_day_template_no_sales": "Great work today. Your pharmacy records are safely saved.",
    "max_message_length": 120,
}


@dataclass(frozen=True)
class PersonalityMessage:
    kind: str
    text: str
    ai_calls_used: bool = False


class OwnerExperienceEngine:
    def __init__(self, store: TrainingStore | None = None) -> None:
        self.store = store or TrainingStore()

    def morning_greeting(
        self,
        *,
        owner_name: str | None = None,
        now: datetime | None = None,
    ) -> PersonalityMessage | None:
        current = now or datetime.now()
        settings = self.settings()
        if not settings.get("enabled", True) or not settings.get("morning_greeting_enabled", True):
            return None
        if not in_time_window(
            current.time(),
            str(settings.get("morning_window_start") or "06:00"),
            str(settings.get("morning_window_end") or "11:30"),
        ):
            return None
        if self._sent(current, "morning_greeting_sent"):
            return None

        name = clean_name(owner_name)
        template_key = "morning_template" if name else "morning_template_no_name"
        text = str(settings.get(template_key) or DEFAULT_PERSONALITY_SETTINGS[template_key]).format(
            name=name or "there"
        )
        message = self._message("morning_greeting", text, settings)
        if message is None:
            return None
        self._mark_sent(current, "morning_greeting_sent")
        return message

    def end_of_day_message(
        self,
        metrics: dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> PersonalityMessage | None:
        current = now or datetime.now()
        settings = self.settings()
        if not settings.get("enabled", True) or not settings.get("end_of_day_enabled", True):
            return None
        if not in_time_window(
            current.time(),
            str(settings.get("end_of_day_window_start") or "23:30"),
            str(settings.get("end_of_day_window_end") or "23:59"),
        ):
            return None
        if self._sent(current, "end_of_day_sent"):
            return None

        sales_count = sales_count_from_metrics(metrics or {})
        if sales_count > 0:
            template = str(settings.get("end_of_day_template") or DEFAULT_PERSONALITY_SETTINGS["end_of_day_template"])
            text = template.format(sales_count=sales_count)
        else:
            text = str(
                settings.get("end_of_day_template_no_sales")
                or DEFAULT_PERSONALITY_SETTINGS["end_of_day_template_no_sales"]
            )
        message = self._message("end_of_day", text, settings)
        if message is None:
            return None
        self._mark_sent(current, "end_of_day_sent")
        return message

    def update_pharmacy_settings(self, overrides: dict[str, Any]) -> dict[str, Any]:
        data = self._settings_data()
        pharmacies = data.setdefault("pharmacies", {})
        current = dict(pharmacies.get(self.store.pharmacy_id, {}))
        current.update(overrides)
        pharmacies[self.store.pharmacy_id] = current
        self.store.save_json(PERSONALITY_SETTINGS_FILE, data)
        return self.settings()

    def settings(self) -> dict[str, Any]:
        data = self._settings_data()
        settings = dict(DEFAULT_PERSONALITY_SETTINGS)
        default_settings = data.get("default", {})
        if isinstance(default_settings, dict):
            settings.update(default_settings)
        pharmacy_settings = data.get("pharmacies", {}).get(self.store.pharmacy_id, {})
        if isinstance(pharmacy_settings, dict):
            settings.update(pharmacy_settings)
        return settings

    def _settings_data(self) -> dict[str, Any]:
        data = self.store.load_json(
            PERSONALITY_SETTINGS_FILE,
            default={"version": 1, "default": DEFAULT_PERSONALITY_SETTINGS, "pharmacies": {}},
        )
        if not isinstance(data, dict):
            data = {"version": 1, "default": DEFAULT_PERSONALITY_SETTINGS, "pharmacies": {}}
        data.setdefault("version", 1)
        data.setdefault("default", DEFAULT_PERSONALITY_SETTINGS)
        data.setdefault("pharmacies", {})
        return data

    def _state_data(self) -> dict[str, Any]:
        data = self.store.load_json(PERSONALITY_STATE_FILE, default={"version": 1, "pharmacies": {}})
        if not isinstance(data, dict):
            data = {"version": 1, "pharmacies": {}}
        data.setdefault("version", 1)
        data.setdefault("pharmacies", {})
        return data

    def _sent(self, current: datetime, flag: str) -> bool:
        data = self._state_data()
        day = date_state(data, self.store.pharmacy_id, current)
        return bool(day.get(flag))

    def _mark_sent(self, current: datetime, flag: str) -> None:
        data = self._state_data()
        day = date_state(data, self.store.pharmacy_id, current)
        day[flag] = True
        self.store.save_json(PERSONALITY_STATE_FILE, data)

    def _message(self, kind: str, text: str, settings: dict[str, Any]) -> PersonalityMessage | None:
        clean = " ".join(str(text or "").split())
        if not clean:
            return None
        max_length = int(settings.get("max_message_length") or 120)
        if len(clean) > max_length:
            clean = clean[: max_length - 1].rstrip() + "."
        return PersonalityMessage(kind=kind, text=clean, ai_calls_used=False)


def date_state(data: dict[str, Any], pharmacy_id: str, current: datetime) -> dict[str, Any]:
    pharmacy = data.setdefault("pharmacies", {}).setdefault(pharmacy_id or "default", {"dates": {}})
    return pharmacy.setdefault("dates", {}).setdefault(current.date().isoformat(), {})


def in_time_window(current: time, start_text: str, end_text: str) -> bool:
    start = parse_hhmm(start_text)
    end = parse_hhmm(end_text)
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def parse_hhmm(value: str) -> time:
    hour_text, minute_text = str(value or "00:00").split(":", maxsplit=1)
    hour = max(0, min(23, int(hour_text)))
    minute = max(0, min(59, int(minute_text)))
    return time(hour, minute)


def clean_name(value: str | None) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return ""
    return text.split()[0].capitalize()


def sales_count_from_metrics(metrics: dict[str, Any]) -> int:
    for key in ("sale_transactions", "active_sales", "sales_count", "total_sales_count"):
        try:
            value = int(metrics.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0
