from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.correction_learning import CorrectionLearningEngine
from app.domain import Action, ParsedEvent, ParseResult
from app.local_first_parser import LocalFirstParser
from app.medicine_brain import MedicineBrain
from app.training_store import TrainingStore


EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase3_correction_learning_cases.jsonl"
SOURCE_TRAINING_DIR = ROOT_DIR / "training"
EVAL_WORKSPACE = ROOT_DIR / ".phase3_eval_workspace"


class EvalFallbackParser:
    def __init__(self) -> None:
        self.calls = 0

    def parse_events(self, text: str, master_drug_names: list[str]) -> ParseResult:
        self.calls += 1
        return ParseResult(
            events=[ParsedEvent("Fallback Medicine", Action.NOT_SOLD, quantity=1)]
        )


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    cases = load_jsonl(eval_path)
    for index, case in enumerate(cases, start=1):
        training_dir = make_training_copy(f"case_{index}")
        store = TrainingStore(training_dir=training_dir, pharmacy_id=f"pharmacy_{index}")
        fallback = EvalFallbackParser()
        parser = LocalFirstParser(
            fallback,
            brain=MedicineBrain(store),
            learning_engine=CorrectionLearningEngine(store),
        )

        correction = parser.parse_events(str(case["correction"]), master_drug_names=[])
        followup = parser.parse_events(str(case["followup"]), master_drug_names=[])
        expected = case["expected"]
        brain_result = parser.last_command.brain_result if parser.last_command else None
        errors = check_case(correction, followup, fallback.calls, store, expected, brain_result)
        if errors:
            failures.append(f"case {index} {case['correction']!r}: " + "; ".join(errors))
    return not failures, failures


def check_case(
    correction: ParseResult,
    followup: ParseResult,
    fallback_calls: int,
    store: TrainingStore,
    expected: dict[str, Any],
    brain_result: Any,
) -> list[str]:
    errors: list[str] = []
    if not correction.needs_clarification or not correction.clarification_question:
        errors.append("correction did not return learned reply")

    memory_entries = store.pharmacy_memory().get("entries", [])
    if not memory_entries:
        errors.append("no memory entry saved")
    elif memory_entries[-1].get("type") != expected.get("correction_type"):
        errors.append(
            f"correction_type expected {expected.get('correction_type')}, got {memory_entries[-1].get('type')}"
        )

    if fallback_calls != expected.get("fallback_calls", 0):
        errors.append(f"fallback_calls expected {expected.get('fallback_calls')}, got {fallback_calls}")

    if not followup.events:
        errors.append("followup returned no event")
        return errors

    event = followup.events[0]
    if event.drug_name != expected.get("medicine_name"):
        errors.append(f"medicine_name expected {expected.get('medicine_name')}, got {event.drug_name}")
    if "quantity" in expected and event.quantity != expected["quantity"]:
        errors.append(f"quantity expected {expected['quantity']}, got {event.quantity}")

    notes = event.notes
    if expected.get("payment") == "cash" and "Payment: Cash" not in notes:
        errors.append("payment cash not reflected in notes")
    if expected.get("packaging") == "strip" and "Packaging: strip" not in notes:
        errors.append("packaging strip not reflected in notes")
    if expected.get("dose") and f"Dose: {expected['dose']}" not in notes:
        errors.append(f"dose {expected['dose']} not reflected in notes")
    if brain_result is not None:
        for field in ("payment", "packaging", "dose", "unit"):
            if field in expected and getattr(brain_result, field) != expected[field]:
                errors.append(
                    f"brain {field} expected {expected[field]!r}, got {getattr(brain_result, field)!r}"
                )
    return errors


def make_training_copy(name: str) -> Path:
    training_dir = EVAL_WORKSPACE / name / "training"
    if training_dir.parent.exists():
        shutil.rmtree(training_dir.parent)
    shutil.copytree(SOURCE_TRAINING_DIR, training_dir)
    (training_dir / "corrections.json").write_text('{"version": 1, "pharmacies": {}}\n')
    (training_dir / "feedback_log.jsonl").write_text("")
    return training_dir


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
        print(f"PHASE 3 CORRECTION LEARNING EVAL: PASS ({EVAL_PATH})")
        return 0

    print(f"PHASE 3 CORRECTION LEARNING EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
