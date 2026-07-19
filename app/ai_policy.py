from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final


class UnjustifiedAICallError(RuntimeError):
    """Raised when production code attempts an unapproved AI workflow."""


@dataclass(frozen=True)
class AIWorkflowJustification:
    workflow_name: str
    exact_reason_deterministic_execution_is_insufficient: str
    expected_user_value: str
    fallback_behavior: str
    token_cost_controls: str
    timeout_seconds: int
    maximum_retry_count: int
    caching_behavior: str
    privacy_data_scope: str
    approval_status: str
    responsible_file_or_owner: str


# Permanent MS2.0 rule: no routine operational workflow may invoke an LLM or
# other paid AI API unless it is explicitly approved here. This registry is
# deliberately data-shaped so tests and repository tooling can inspect it.
APPROVED_AI_WORKFLOWS: Final[dict[str, AIWorkflowJustification]] = {
    "voice_transcription": AIWorkflowJustification(
        workflow_name="voice_transcription",
        exact_reason_deterministic_execution_is_insufficient="Uploaded voice bytes have no reliable local transcript in the server runtime.",
        expected_user_value="Owners can submit a voice note when browser-local speech recognition is unavailable.",
        fallback_behavior="Ask for typed text; never invent a transcript or mutate pharmacy data.",
        token_cost_controls="One transcription request per uncached media hash; short pharmacy prompt only.",
        timeout_seconds=30,
        maximum_retry_count=0,
        caching_behavior="Processed media hashes are reused by the WhatsApp bridge path.",
        privacy_data_scope="Only the owner-submitted audio and a fixed pharmacy vocabulary prompt.",
        approval_status="approved",
        responsible_file_or_owner="app/transcription.py (MS2.0 engineering)",
    ),
    "ambiguous_command_parsing": AIWorkflowJustification(
        workflow_name="ambiguous_command_parsing",
        exact_reason_deterministic_execution_is_insufficient="The shared local parser and medicine resolver could not safely classify free-form text.",
        expected_user_value="A genuinely ambiguous owner message can be normalized or returned for clarification.",
        fallback_behavior="Return a clarification request; never infer prices or mutate data without review.",
        token_cost_controls="Local-first gate, at most one request, capped catalog context, structured JSON response.",
        timeout_seconds=30,
        maximum_retry_count=0,
        caching_behavior="No response cache; deterministic parsing always runs first.",
        privacy_data_scope="Owner message plus at most 500 catalog medicine names; no sales ledger or patient data.",
        approval_status="approved",
        responsible_file_or_owner="app/ai.py and app/local_first_parser.py (MS2.0 engineering)",
    ),
    "photo_invoice_extraction": AIWorkflowJustification(
        workflow_name="photo_invoice_extraction",
        exact_reason_deterministic_execution_is_insufficient="Local OCR/classification could not produce a safe structured review and AI was explicitly enabled.",
        expected_user_value="An unreadable supplier invoice can become an editable, non-mutating review draft.",
        fallback_behavior="Save the photo for manual review; never guess fields or add stock automatically.",
        token_cost_controls="Explicit feature gate, one request per uncached media hash, structured response only.",
        timeout_seconds=45,
        maximum_retry_count=0,
        caching_behavior="Processed media hashes prevent duplicate extraction requests.",
        privacy_data_scope="Only the submitted pharmacy invoice/photo; output remains review-first.",
        approval_status="approved",
        responsible_file_or_owner="app/main.py and app/ai.py (MS2.0 engineering)",
    ),
}


def require_approved_ai_workflow(workflow_name: str) -> AIWorkflowJustification:
    justification = APPROVED_AI_WORKFLOWS.get(workflow_name)
    if justification is None or justification.approval_status != "approved":
        raise UnjustifiedAICallError(
            f"AI workflow '{workflow_name}' is prohibited without an approved MS2.0 justification."
        )
    return justification


def approved_ai_workflows_snapshot() -> dict[str, dict[str, object]]:
    return {name: asdict(justification) for name, justification in APPROVED_AI_WORKFLOWS.items()}
