from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase9_live_readiness_cases.jsonl"
LIVE_PLAN_PATH = ROOT_DIR / "training" / "live_test_plan.json"
LIVE_PLAN_MD_PATH = ROOT_DIR / "training" / "LIVE_TEST_PLAN.md"
DASHBOARD_PATH = ROOT_DIR / "training" / "TRAINING_DASHBOARD.md"


REQUIRED_TEST_IDS = {
    "whatsapp_deterministic_sale",
    "whatsapp_typo_sale",
    "whatsapp_shorthand_sale",
    "whatsapp_ambiguous_medicine",
    "whatsapp_no_stock_block",
    "whatsapp_stock_check",
    "whatsapp_undo_by_sale_number",
    "whatsapp_correction_by_sale_number",
    "whatsapp_report_today",
    "multi_owner_staff_simulated",
    "offline_tap_talk_online",
    "offline_tap_talk_offline",
    "offline_media_queue_online_offline",
    "whatsapp_invoice_photo",
    "offline_invoice_photo",
    "editable_approval_card",
    "token_usage_preserved",
}

PREPARED_ONLY_IDS = {
    "offline_tap_talk_online",
    "offline_tap_talk_offline",
    "offline_media_queue_online_offline",
    "whatsapp_invoice_photo",
    "offline_invoice_photo",
    "editable_approval_card",
}


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    plan = load_plan()
    for index, row in enumerate(load_jsonl(eval_path), start=1):
        case = str(row["case"])
        errors = CASES[case](plan)
        if errors:
            failures.append(f"case {index} {case}: " + "; ".join(errors))
    return not failures, failures


def case_all_live_checklist_items_prepared(plan: dict[str, Any]) -> list[str]:
    tests = plan_tests(plan)
    actual_ids = {str(item.get("id") or "") for item in tests}
    errors: list[str] = []
    missing = sorted(REQUIRED_TEST_IDS - actual_ids)
    extra = sorted(actual_ids - REQUIRED_TEST_IDS)
    if missing:
        errors.append(f"missing live test ids: {', '.join(missing)}")
    if extra:
        errors.append(f"unexpected live test ids: {', '.join(extra)}")
    for item in tests:
        for field in ("id", "order", "surface", "title", "action", "expected", "status", "execution_mode", "token_expectation"):
            if item.get(field) in (None, ""):
                errors.append(f"{item.get('id')} missing {field}")
        if item.get("status") != "prepared":
            errors.append(f"{item.get('id')} status is not prepared")
    return errors


def case_live_execution_not_started(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("status") != "prepared":
        errors.append(f"plan status expected prepared, got {plan.get('status')}")
    if plan.get("live_execution_status") != "not_started":
        errors.append(f"live execution status expected not_started, got {plan.get('live_execution_status')}")
    for item in plan_tests(plan):
        if str(item.get("status") or "") in {"passed", "failed", "complete", "running"}:
            errors.append(f"{item.get('id')} appears executed with status {item.get('status')}")
    if not LIVE_PLAN_MD_PATH.exists():
        errors.append("human live test plan markdown missing")
    return errors


def case_one_test_at_a_time_rule_present(plan: dict[str, Any]) -> list[str]:
    rule_text = " ".join(
        [
            str(plan.get("execution_rule") or ""),
            str(plan.get("stop_rule") or ""),
            LIVE_PLAN_MD_PATH.read_text(encoding="utf-8") if LIVE_PLAN_MD_PATH.exists() else "",
        ]
    ).lower()
    errors: list[str] = []
    if "one clear live test at a time" not in rule_text and "one clear test at a time" not in rule_text:
        errors.append("one-test-at-a-time rule missing")
    if "stop" not in rule_text or "fix" not in rule_text or "retest" not in rule_text:
        errors.append("failure stop/fix/retest rule missing")
    return errors


def case_evidence_fields_required(plan: dict[str, Any]) -> list[str]:
    required = {"input_sent", "actual_reply", "stock_or_report_observed", "pass_fail", "token_observation"}
    actual = {str(item) for item in plan.get("evidence_required", [])}
    missing = sorted(required - actual)
    return [f"missing evidence fields: {', '.join(missing)}"] if missing else []


def case_token_preservation_declared(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    token_rule = str(plan.get("token_rule") or "").lower()
    if "deterministic" not in token_rule or "ai/openai" not in token_rule:
        errors.append("token rule does not declare deterministic/no AI expectation")
    for item in plan_tests(plan):
        expectation = str(item.get("token_expectation") or "")
        if not expectation:
            errors.append(f"{item.get('id')} missing token expectation")
    known_zero_ids = REQUIRED_TEST_IDS - {"whatsapp_invoice_photo", "offline_invoice_photo", "whatsapp_report_today"}
    for item in plan_tests(plan):
        if item.get("id") in known_zero_ids and "zero" not in str(item.get("token_expectation") or "").lower() and "no_unnecessary_ai" not in str(item.get("token_expectation") or "").lower():
            errors.append(f"{item.get('id')} does not preserve zero/no-unnecessary AI expectation")
    return errors


def case_paused_photo_and_offline_items_are_prepared_only(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    by_id = {str(item.get("id") or ""): item for item in plan_tests(plan)}
    for test_id in PREPARED_ONLY_IDS:
        item = by_id.get(test_id)
        if item is None:
            errors.append(f"{test_id} missing")
            continue
        if item.get("status") != "prepared":
            errors.append(f"{test_id} is not prepared-only")
        if not str(item.get("execution_mode") or "").startswith("manual"):
            errors.append(f"{test_id} should remain manual live preparation")
    return errors


def case_phase8_dashboard_ready(_plan: dict[str, Any]) -> list[str]:
    if not DASHBOARD_PATH.exists():
        return ["Phase 8 dashboard missing"]
    dashboard = DASHBOARD_PATH.read_text(encoding="utf-8")
    errors: list[str] = []
    if "Overall status: PASS" not in dashboard:
        errors.append("Phase 8 dashboard is not PASS")
    if "Ready for Phase 9 review: YES" not in dashboard and "Ready for next phase review: YES" not in dashboard:
        errors.append("Phase 8 dashboard did not approve next phase review")
    return errors


CASES = {
    "all_live_checklist_items_prepared": case_all_live_checklist_items_prepared,
    "live_execution_not_started": case_live_execution_not_started,
    "one_test_at_a_time_rule_present": case_one_test_at_a_time_rule_present,
    "evidence_fields_required": case_evidence_fields_required,
    "token_preservation_declared": case_token_preservation_declared,
    "paused_photo_and_offline_items_are_prepared_only": case_paused_photo_and_offline_items_are_prepared_only,
    "phase8_dashboard_ready": case_phase8_dashboard_ready,
}


def load_plan() -> dict[str, Any]:
    data = json.loads(LIVE_PLAN_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def plan_tests(plan: dict[str, Any]) -> list[dict[str, Any]]:
    tests = plan.get("tests", [])
    return [item for item in tests if isinstance(item, dict)]


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
        print(f"PHASE 9 LIVE READINESS EVAL: PASS ({EVAL_PATH})")
        return 0

    print(f"PHASE 9 LIVE READINESS EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
