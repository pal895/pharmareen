from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.ai_policy import (
    APPROVED_AI_WORKFLOWS,
    UnjustifiedAICallError,
    approved_ai_workflows_snapshot,
    require_approved_ai_workflow,
)
from app.main import get_report_service


ROOT = Path(__file__).resolve().parents[1]


def test_approved_ai_workflows_have_complete_machine_readable_justifications():
    required_fields = {
        "workflow_name",
        "exact_reason_deterministic_execution_is_insufficient",
        "expected_user_value",
        "fallback_behavior",
        "token_cost_controls",
        "timeout_seconds",
        "maximum_retry_count",
        "caching_behavior",
        "privacy_data_scope",
        "approval_status",
        "responsible_file_or_owner",
    }

    snapshot = approved_ai_workflows_snapshot()
    assert set(snapshot) == {
        "voice_transcription",
        "ambiguous_command_parsing",
        "photo_invoice_extraction",
    }
    for name, justification in snapshot.items():
        assert set(justification) == required_fields
        assert justification["workflow_name"] == name
        assert justification["approval_status"] == "approved"
        assert justification["maximum_retry_count"] == 0
        assert all(value != "" for value in justification.values())


def test_unregistered_routine_ai_workflow_fails_closed():
    with pytest.raises(UnjustifiedAICallError):
        require_approved_ai_workflow("routine_report_recommendations")


def test_production_report_dependency_injection_has_no_ai_recommender():
    source = inspect.getsource(get_report_service)
    assert "recommender=None" in source
    assert "get_ai_service" not in source


def test_all_production_openai_clients_are_confined_to_policy_guarded_wrappers():
    openai_importers: set[str] = set()
    guarded_workflows: set[str] = set()
    for path in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        imports_openai = any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and (
                (isinstance(node, ast.ImportFrom) and node.module == "openai")
                or (
                    isinstance(node, ast.Import)
                    and any(alias.name == "openai" for alias in node.names)
                )
            )
            for node in ast.walk(tree)
        )
        if imports_openai:
            openai_importers.add(path.relative_to(ROOT).as_posix())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "require_approved_ai_workflow"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                guarded_workflows.add(str(node.args[0].value))

    assert openai_importers == {"app/ai.py", "app/transcription.py"}
    assert set(APPROVED_AI_WORKFLOWS).issubset(guarded_workflows)


def test_openai_clients_disable_automatic_retries_and_bound_timeouts():
    ai_source = (ROOT / "app" / "ai.py").read_text(encoding="utf-8")
    transcription_source = (ROOT / "app" / "transcription.py").read_text(encoding="utf-8")
    assert "timeout=45.0, max_retries=0" in ai_source
    assert "timeout=30.0, max_retries=0" in transcription_source
