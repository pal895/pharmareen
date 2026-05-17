from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.pharmacy_simulation import load_training_cases, run_simulation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PharMareen local-first pharmacy behavior simulations.")
    parser.add_argument("--dataset", default="datasets/pharmacy_training", help="Dataset folder containing JSONL cases.")
    parser.add_argument("--iterations", type=int, default=10, help="Repeat simulated cases to mimic rush-hour volume.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any simulated case fails.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    args = parser.parse_args()

    base_cases = [case for case in load_training_cases(Path(args.dataset)) if case.simulate]
    expanded = [
        replace(case, id=f"{case.id}#{iteration + 1}")
        for iteration in range(max(args.iterations, 1))
        for case in base_cases
    ]
    summary = run_simulation(expanded)
    if args.json:
        print(json.dumps(summary.as_dict(), indent=2, ensure_ascii=False))
    else:
        print("PHARMAREEN PHARMACY SIMULATION")
        print(f"cases={summary.total} passed={summary.passed} failed={summary.failed} avg_ms={summary.average_ms:.2f}")
        print(f"ai_allowed={summary.ai_calls_allowed} unexpected_ai={summary.ai_calls_blocked}")
        failures = [result for result in summary.results if not result.ok][:10]
        for result in failures:
            print(f"FAIL {result.case_id} issues={','.join(result.issues)} reply={result.reply[:120]!r}")
    if args.strict and summary.failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
