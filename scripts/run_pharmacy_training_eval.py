from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.medicine_brain import MedicineBrain
from scripts import (
    run_phase2_local_parser_eval,
    run_phase3_correction_eval,
    run_phase4_workflow_eval,
    run_phase5_sale_numbering_eval,
    run_phase6_multi_owner_eval,
    run_phase7_personality_eval,
    run_phase9_live_readiness_eval,
    run_phase10_reliability_eval,
    run_phase11_live_pilot_eval,
    run_phase12_deployment_eval,
    run_phase13_provisioning_eval,
)


TRAINING_DIR = ROOT_DIR / "training"
EVALS_DIR = TRAINING_DIR / "evals"
DASHBOARD_PATH = TRAINING_DIR / "TRAINING_DASHBOARD.md"
FAILURE_EXAMPLES_PATH = TRAINING_DIR / "eval_failed_training_examples.jsonl"
UNRESOLVED_ISSUES_PATH = TRAINING_DIR / "UNRESOLVED_EVAL_ISSUES.md"
PHASE1_EVAL_PATH = EVALS_DIR / "phase1_medicine_brain_cases.jsonl"


@dataclass(frozen=True)
class PhaseEval:
    phase: str
    label: str
    eval_path: Path
    runner: Callable[[], tuple[bool, list[str]]]
    coverage: tuple[str, ...]


@dataclass(frozen=True)
class PhaseEvalResult:
    phase: str
    label: str
    eval_path: Path
    passed: bool
    failures: list[str]
    coverage: tuple[str, ...]


PHASE_EVALS: tuple[PhaseEval, ...] = (
    PhaseEval(
        phase="Phase 1",
        label="Medicine brain",
        eval_path=PHASE1_EVAL_PATH,
        runner=lambda: run_phase1_medicine_brain_eval(PHASE1_EVAL_PATH),
        coverage=("medicine matching", "typos", "shorthand", "forms/units", "payments", "ambiguity", "zero-token proof"),
    ),
    PhaseEval(
        phase="Phase 2",
        label="Local-first parser",
        eval_path=run_phase2_local_parser_eval.EVAL_PATH,
        runner=run_phase2_local_parser_eval.run_eval,
        coverage=("local parser wrapper", "rush-hour shorthand", "AI fallback boundary", "zero-token proof"),
    ),
    PhaseEval(
        phase="Phase 3",
        label="Correction learning",
        eval_path=run_phase3_correction_eval.EVAL_PATH,
        runner=run_phase3_correction_eval.run_eval,
        coverage=("corrections", "owner-approved learning", "pharmacy memory", "zero-token proof"),
    ),
    PhaseEval(
        phase="Phase 4",
        label="Workflow brain",
        eval_path=run_phase4_workflow_eval.EVAL_PATH,
        runner=run_phase4_workflow_eval.run_eval,
        coverage=("workflow commands", "reports", "stock", "restock", "no-stock", "payments"),
    ),
    PhaseEval(
        phase="Phase 5",
        label="Sale numbering",
        eval_path=run_phase5_sale_numbering_eval.EVAL_PATH,
        runner=run_phase5_sale_numbering_eval.run_eval,
        coverage=("sale numbering", "undo/edit", "finance reconciliation", "audit", "zero-token proof"),
    ),
    PhaseEval(
        phase="Phase 6",
        label="Multi-owner/staff safety",
        eval_path=run_phase6_multi_owner_eval.EVAL_PATH,
        runner=run_phase6_multi_owner_eval.run_eval,
        coverage=("multi-owner behavior", "staff audit", "owner approval", "report accuracy", "zero-token proof"),
    ),
    PhaseEval(
        phase="Phase 7",
        label="Personality engine",
        eval_path=run_phase7_personality_eval.EVAL_PATH,
        runner=run_phase7_personality_eval.run_eval,
        coverage=("personality rules", "no spam", "disable/tune", "zero-token proof"),
    ),
    PhaseEval(
        phase="Phase 9",
        label="Live readiness",
        eval_path=run_phase9_live_readiness_eval.EVAL_PATH,
        runner=run_phase9_live_readiness_eval.run_eval,
        coverage=("live readiness", "token preservation", "one-test-at-a-time"),
    ),
    PhaseEval(
        phase="Phase 10",
        label="Production reliability",
        eval_path=run_phase10_reliability_eval.EVAL_PATH,
        runner=run_phase10_reliability_eval.run_eval,
        coverage=("offline recovery", "duplicate prevention", "sync reliability", "no-data-loss", "zero-token proof"),
    ),
    PhaseEval(
        phase="Phase 11",
        label="Live pharmacy pilot",
        eval_path=run_phase11_live_pilot_eval.EVAL_PATH,
        runner=run_phase11_live_pilot_eval.run_eval,
        coverage=(
            "live pilot execution",
            "pilot isolation",
            "live issue capture",
            "production telemetry",
            "pilot rollback",
            "owner feedback",
            "workflow friction",
            "pilot stability scoring",
            "production readiness",
            "zero-token proof",
        ),
    ),
    PhaseEval(
        phase="Phase 12",
        label="Deployment onboarding",
        eval_path=run_phase12_deployment_eval.EVAL_PATH,
        runner=run_phase12_deployment_eval.run_eval,
        coverage=(
            "deployment onboarding",
            "pharmacy bootstrap",
            "medicine import",
            "owner setup",
            "deployment readiness",
            "monitoring dashboard",
            "deployment recovery",
            "activation controls",
            "deployment audit",
            "deployment scoring",
            "zero-token proof",
        ),
    ),
    PhaseEval(
        phase="Phase 13",
        label="Autonomous provisioning",
        eval_path=run_phase13_provisioning_eval.EVAL_PATH,
        runner=run_phase13_provisioning_eval.run_eval,
        coverage=(
            "autonomous provisioning",
            "three-step owner onboarding",
            "unknown-number onboarding",
            "namespace isolation",
            "deployment scalability",
            "provisioning stress tests",
            "activation gate",
            "onboarding recovery",
            "zero-token proof",
        ),
    ),
)


REQUIRED_COVERAGE = (
    "medicine matching",
    "typos",
    "shorthand",
    "forms/units",
    "payments",
    "ambiguity",
    "corrections",
    "workflow commands",
    "sale numbering",
    "multi-owner behavior",
    "personality rules",
    "live readiness",
    "offline recovery",
    "duplicate prevention",
    "sync reliability",
    "no-data-loss",
    "live pilot execution",
    "pilot isolation",
    "live issue capture",
    "production telemetry",
    "pilot rollback",
    "owner feedback",
    "workflow friction",
    "pilot stability scoring",
    "production readiness",
    "deployment onboarding",
    "pharmacy bootstrap",
    "medicine import",
    "owner setup",
    "deployment readiness",
    "monitoring dashboard",
    "deployment recovery",
    "activation controls",
    "deployment audit",
    "deployment scoring",
    "autonomous provisioning",
    "three-step owner onboarding",
    "unknown-number onboarding",
    "namespace isolation",
    "deployment scalability",
    "provisioning stress tests",
    "activation gate",
    "onboarding recovery",
    "zero-token proof",
)


def run_unified_eval() -> tuple[bool, list[PhaseEvalResult]]:
    results: list[PhaseEvalResult] = []
    for phase_eval in PHASE_EVALS:
        passed, failures = phase_eval.runner()
        results.append(
            PhaseEvalResult(
                phase=phase_eval.phase,
                label=phase_eval.label,
                eval_path=phase_eval.eval_path,
                passed=passed,
                failures=failures,
                coverage=phase_eval.coverage,
            )
        )
    return all(result.passed for result in results), results


def run_phase1_medicine_brain_eval(eval_path: Path = PHASE1_EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    brain = MedicineBrain()
    for index, case in enumerate(load_jsonl(eval_path), start=1):
        result = brain.analyze(str(case["input"]))
        expected = case["expected"]
        errors = check_medicine_case(result.as_dict(), expected)
        if errors:
            failures.append(f"case {index} {case['input']!r}: " + "; ".join(errors))
    return not failures, failures


def check_medicine_case(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("status", "medicine_name", "quantity", "payment", "form", "unit", "dose", "packaging", "action"):
        if field in expected and actual.get(field) != expected[field]:
            errors.append(f"{field} expected {expected[field]!r}, got {actual.get(field)!r}")
    if actual.get("ai_calls_used") is not False:
        errors.append("medicine brain used AI")
    if actual.get("token_safe") is not True:
        errors.append("medicine brain was not token safe")
    return errors


def coverage_status(results: list[PhaseEvalResult]) -> dict[str, bool]:
    covered = {item: False for item in REQUIRED_COVERAGE}
    for result in results:
        if not result.passed:
            continue
        for item in result.coverage:
            if item in covered:
                covered[item] = True
    return covered


def write_outputs(results: list[PhaseEvalResult]) -> None:
    write_failure_examples(results)
    write_unresolved_issues(results)
    write_dashboard(results)


def write_failure_examples(results: list[PhaseEvalResult]) -> None:
    rows: list[dict[str, Any]] = []
    created_at = datetime.now(timezone.utc).isoformat()
    for result in results:
        for failure in result.failures:
            rows.append(
                {
                    "type": "eval_failure_training_example",
                    "phase": result.phase,
                    "label": result.label,
                    "eval_path": str(result.eval_path),
                    "failure": failure,
                    "needs_review": True,
                    "created_at": created_at,
                }
            )
    FAILURE_EXAMPLES_PATH.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_unresolved_issues(results: list[PhaseEvalResult]) -> None:
    failures = [(result, failure) for result in results for failure in result.failures]
    if not failures:
        UNRESOLVED_ISSUES_PATH.write_text(
            "# Unresolved Eval Issues\n\nStatus: PASS\n\nNo unresolved eval issues.\n",
            encoding="utf-8",
        )
        return

    lines = ["# Unresolved Eval Issues", "", "Status: FAIL", ""]
    for result, failure in failures:
        lines.append(f"- {result.phase} - {result.label}: {failure}")
    UNRESOLVED_ISSUES_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_dashboard(results: list[PhaseEvalResult]) -> None:
    all_passed = all(result.passed for result in results)
    coverage = coverage_status(results)
    lines = [
        "# PharMareen Training Dashboard",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Overall status: {'PASS' if all_passed else 'FAIL'}",
        f"Ready for next phase review: {'YES' if all_passed and all(coverage.values()) else 'NO'}",
        "",
        "## Phase Evals",
        "",
    ]
    for result in results:
        lines.append(f"- [{'x' if result.passed else ' '}] {result.phase} - {result.label}: {'PASS' if result.passed else 'FAIL'}")
    lines.extend(["", "## Required Coverage", ""])
    for item, passed in coverage.items():
        lines.append(f"- [{'x' if passed else ' '}] {item}")
    lines.extend(["", "## Artifacts", ""])
    lines.append(f"- Failure training examples: `{FAILURE_EXAMPLES_PATH.name}`")
    lines.append(f"- Unresolved issues: `{UNRESOLVED_ISSUES_PATH.name}`")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    if all_passed and all(coverage.values()):
        lines.append("Ready for next phase review. Do not start live testing until explicitly instructed.")
    else:
        lines.append("Not ready. Fix unresolved eval issues first.")
    DASHBOARD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(passed: bool, results: list[PhaseEvalResult]) -> None:
    print(f"PHARMACY TRAINING EVAL: {'PASS' if passed else 'FAIL'}")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"- {result.phase} {result.label}: {status} ({result.eval_path})")
        for failure in result.failures:
            print(f"  - {failure}")
    coverage = coverage_status(results)
    print(f"READY FOR NEXT PHASE REVIEW: {'YES' if passed and all(coverage.values()) else 'NO'}")
    print(f"DASHBOARD: {DASHBOARD_PATH}")
    print(f"FAILED TRAINING EXAMPLES: {FAILURE_EXAMPLES_PATH}")
    print(f"UNRESOLVED ISSUES: {UNRESOLVED_ISSUES_PATH}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if clean:
            rows.append(json.loads(clean))
    return rows


def main() -> int:
    passed, results = run_unified_eval()
    write_outputs(results)
    print_summary(passed, results)
    return 0 if passed and all(coverage_status(results).values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
