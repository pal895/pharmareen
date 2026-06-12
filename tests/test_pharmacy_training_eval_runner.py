from __future__ import annotations

import json
from pathlib import Path

from scripts import run_pharmacy_training_eval as runner


TEST_WORKSPACE = Path(__file__).resolve().parent.parent / ".phase8_test_workspace"


def test_phase1_eval_adapter_runs_medicine_brain_cases():
    passed, failures = runner.run_phase1_medicine_brain_eval()

    assert passed is True
    assert failures == []


def test_coverage_status_requires_all_phase8_categories():
    results = [
        runner.PhaseEvalResult(
            phase="Phase X",
            label="Fake",
            eval_path=Path("fake.jsonl"),
            passed=True,
            failures=[],
            coverage=runner.REQUIRED_COVERAGE,
        )
    ]

    coverage = runner.coverage_status(results)

    assert all(coverage.values())


def test_unified_runner_includes_phase11_live_pilot_eval():
    phases = [phase_eval.phase for phase_eval in runner.PHASE_EVALS]

    assert "Phase 11" in phases


def test_unified_runner_includes_phase12_deployment_eval():
    phases = [phase_eval.phase for phase_eval in runner.PHASE_EVALS]

    assert "Phase 12" in phases


def test_unified_runner_includes_phase13_provisioning_eval():
    phases = [phase_eval.phase for phase_eval in runner.PHASE_EVALS]

    assert "Phase 13" in phases


def test_dashboard_and_failure_outputs_are_written(monkeypatch):
    output_dir = TEST_WORKSPACE / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runner, "DASHBOARD_PATH", output_dir / "TRAINING_DASHBOARD.md")
    monkeypatch.setattr(runner, "FAILURE_EXAMPLES_PATH", output_dir / "eval_failed_training_examples.jsonl")
    monkeypatch.setattr(runner, "UNRESOLVED_ISSUES_PATH", output_dir / "UNRESOLVED_EVAL_ISSUES.md")
    results = [
        runner.PhaseEvalResult(
            phase="Phase Test",
            label="Broken eval",
            eval_path=Path("broken.jsonl"),
            passed=False,
            failures=["case 1 failed"],
            coverage=("medicine matching",),
        )
    ]

    runner.write_outputs(results)

    dashboard = runner.DASHBOARD_PATH.read_text(encoding="utf-8")
    unresolved = runner.UNRESOLVED_ISSUES_PATH.read_text(encoding="utf-8")
    failure_rows = [
        json.loads(line)
        for line in runner.FAILURE_EXAMPLES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert "Overall status: FAIL" in dashboard
    assert "Ready for next phase review: NO" in dashboard
    assert "case 1 failed" in unresolved
    assert failure_rows[0]["type"] == "eval_failure_training_example"
    assert failure_rows[0]["failure"] == "case 1 failed"
