from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase2_local_parser_cases.jsonl"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain import Action, ParsedEvent, ParseResult
from app.local_first_parser import LocalFirstParser


class EvalFallbackParser:
    def __init__(self) -> None:
        self.calls = 0

    def parse_events(self, text: str, master_drug_names: list[str]) -> ParseResult:
        self.calls += 1
        return ParseResult(
            events=[
                ParsedEvent(
                    drug_name="Fallback Medicine",
                    action=Action.NOT_SOLD,
                    quantity=1,
                    notes="fallback",
                )
            ]
        )


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    cases = load_jsonl(eval_path)
    for index, case in enumerate(cases, start=1):
        fallback = EvalFallbackParser()
        parser = LocalFirstParser(fallback)
        result = parser.parse_events(str(case["input"]), master_drug_names=[])
        expected = case["expected"]
        errors = check_case(result, parser.last_used_fallback, expected)
        if errors:
            failures.append(f"case {index} {case['input']!r}: " + "; ".join(errors))
    return not failures, failures


def check_case(result: ParseResult, used_fallback: bool, expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    route = "fallback" if used_fallback else "local"
    if route != expected.get("route"):
        errors.append(f"route expected {expected.get('route')}, got {route}")

    if "needs_clarification" in expected and result.needs_clarification != expected["needs_clarification"]:
        errors.append(
            f"needs_clarification expected {expected['needs_clarification']}, got {result.needs_clarification}"
        )

    question_contains = expected.get("question_contains")
    if question_contains and question_contains not in str(result.clarification_question or ""):
        errors.append(f"question missing {question_contains!r}")

    if expected.get("route") == "fallback":
        return errors

    if expected.get("needs_clarification"):
        return errors

    if not result.events:
        return [*errors, "no events returned"]

    event = result.events[0]
    action = event.action.value if event.action else None
    for field, actual in {
        "action": action,
        "medicine_name": event.drug_name,
        "quantity": event.quantity,
    }.items():
        if field in expected and actual != expected[field]:
            errors.append(f"{field} expected {expected[field]!r}, got {actual!r}")

    notes_contains = expected.get("notes_contains")
    if notes_contains and notes_contains not in event.notes:
        errors.append(f"notes missing {notes_contains!r}")
    return errors


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
        print(f"PHASE 2 LOCAL PARSER EVAL: PASS ({EVAL_PATH})")
        return 0

    print(f"PHASE 2 LOCAL PARSER EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
