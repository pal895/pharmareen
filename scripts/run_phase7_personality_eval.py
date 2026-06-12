from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.personality import OwnerExperienceEngine
from app.training_store import TrainingStore


EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase7_personality_cases.jsonl"
SOURCE_TRAINING_DIR = ROOT_DIR / "training"
EVAL_WORKSPACE = ROOT_DIR / ".phase7_eval_workspace"
NAIROBI = ZoneInfo("Africa/Nairobi")


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for index, row in enumerate(load_jsonl(eval_path), start=1):
        case = row["case"]
        errors = CASES[case]()
        if errors:
            failures.append(f"case {index} {case}: " + "; ".join(errors))
    return not failures, failures


def case_morning_greeting_once() -> list[str]:
    engine = make_engine("morning_once")
    first = engine.morning_greeting(owner_name="Samuel", now=at(2026, 6, 12, 8))
    second = engine.morning_greeting(owner_name="Samuel", now=at(2026, 6, 12, 8, 30))
    errors: list[str] = []
    if first is None or first.text != "Morning Samuel. Ready for another strong pharmacy day?":
        errors.append(f"morning greeting unexpected: {first}")
    if second is not None:
        errors.append("morning greeting repeated on same day")
    return errors


def case_end_of_day_once() -> list[str]:
    engine = make_engine("end_once")
    first = engine.end_of_day_message({"sale_transactions": 214}, now=at(2026, 6, 12, 23, 59))
    second = engine.end_of_day_message({"sale_transactions": 214}, now=at(2026, 6, 12, 23, 59))
    errors: list[str] = []
    if first is None or "214 sales" not in first.text:
        errors.append(f"end-of-day message unexpected: {first}")
    if second is not None:
        errors.append("end-of-day message repeated on same day")
    return errors


def case_disable_and_tune() -> list[str]:
    engine = make_engine("disable_tune")
    engine.update_pharmacy_settings({"enabled": False})
    disabled = engine.morning_greeting(owner_name="Samuel", now=at(2026, 6, 12, 8))
    engine.update_pharmacy_settings(
        {
            "enabled": True,
            "morning_template": "Morning {name}. Steady records, steady sales.",
        }
    )
    tuned = engine.morning_greeting(owner_name="Samuel", now=at(2026, 6, 12, 8))
    errors: list[str] = []
    if disabled is not None:
        errors.append("disabled personality still generated message")
    if tuned is None or tuned.text != "Morning Samuel. Steady records, steady sales.":
        errors.append(f"tuned message unexpected: {tuned}")
    return errors


def case_pharmacy_specific_settings() -> list[str]:
    engine_a = make_engine("pharmacy_specific", pharmacy_id="pharmacy_a")
    engine_b = OwnerExperienceEngine(
        TrainingStore(training_dir=engine_a.store.training_dir, pharmacy_id="pharmacy_b")
    )
    engine_a.update_pharmacy_settings({"enabled": False})
    message_a = engine_a.morning_greeting(owner_name="Amina", now=at(2026, 6, 12, 8))
    message_b = engine_b.morning_greeting(owner_name="Amina", now=at(2026, 6, 12, 8))
    errors: list[str] = []
    if message_a is not None:
        errors.append("pharmacy A disable leaked into generated message")
    if message_b is None:
        errors.append("pharmacy B inherited pharmacy A disable")
    return errors


def case_short_no_ai_messages() -> list[str]:
    engine = make_engine("short_no_ai")
    morning = engine.morning_greeting(owner_name="Samuel", now=at(2026, 6, 12, 8))
    end = engine.end_of_day_message({"sale_transactions": 5}, now=at(2026, 6, 12, 23, 59))
    errors: list[str] = []
    for message in (morning, end):
        if message is None:
            errors.append("expected message was empty")
            continue
        if len(message.text) > 120:
            errors.append(f"message too long: {message.text}")
        if message.ai_calls_used:
            errors.append("message reported AI usage")
    return errors


def case_no_rush_hour_injection() -> list[str]:
    engine = make_engine("no_midday")
    morning = engine.morning_greeting(owner_name="Samuel", now=at(2026, 6, 12, 14))
    end = engine.end_of_day_message({"sale_transactions": 10}, now=at(2026, 6, 12, 14))
    errors: list[str] = []
    if morning is not None:
        errors.append("morning greeting generated outside morning window")
    if end is not None:
        errors.append("end-of-day message generated during workday")
    return errors


CASES = {
    "morning_greeting_once": case_morning_greeting_once,
    "end_of_day_once": case_end_of_day_once,
    "disable_and_tune": case_disable_and_tune,
    "pharmacy_specific_settings": case_pharmacy_specific_settings,
    "short_no_ai_messages": case_short_no_ai_messages,
    "no_rush_hour_injection": case_no_rush_hour_injection,
}


def make_engine(name: str, pharmacy_id: str = "pharmacy_a") -> OwnerExperienceEngine:
    training_dir = EVAL_WORKSPACE / name / "training"
    if training_dir.parent.exists():
        shutil.rmtree(training_dir.parent)
    shutil.copytree(SOURCE_TRAINING_DIR, training_dir)
    (training_dir / "personality_state.json").write_text('{"version": 1, "pharmacies": {}}\n')
    return OwnerExperienceEngine(TrainingStore(training_dir=training_dir, pharmacy_id=pharmacy_id))


def at(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=NAIROBI)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if clean:
            rows.append(json.loads(clean))
    return rows


def main() -> int:
    passed, failures = run_eval()
    if passed:
        print(f"PHASE 7 PERSONALITY EVAL: PASS ({EVAL_PATH})")
        return 0

    print(f"PHASE 7 PERSONALITY EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
