from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.actor_context import ActorContext, build_actor_context
from app.medicine_brain import MedicineBrain, compact_key, normalize_key
from app.training_store import TrainingStore


@dataclass(frozen=True)
class CorrectionResult:
    learned: bool
    correction_type: str | None = None
    alias: str | None = None
    target: str | None = None
    message: str | None = None
    ai_calls_used: bool = False
    pending_approval: bool = False
    correction_id: str | None = None
    actor_id: str | None = None
    actor_role: str | None = None


class CorrectionLearningEngine:
    def __init__(self, store: TrainingStore | None = None) -> None:
        self.store = store or TrainingStore()

    def apply(
        self,
        text: str,
        *,
        actor_context: ActorContext | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        owner_id: str | None = None,
        staff_id: str | None = None,
        source: str | None = None,
        approved: bool | None = None,
    ) -> CorrectionResult:
        parsed = parse_correction_statement(text)
        if parsed is None:
            return CorrectionResult(learned=False, message=None)

        actor = build_actor_context(
            pharmacy_id=self.store.pharmacy_id,
            actor_context=actor_context,
            actor_id=actor_id,
            owner_id=owner_id,
            staff_id=staff_id,
            actor_role=actor_role,
            source=source,
        )
        owner_id = owner_id or actor.owner_id
        staff_id = staff_id or actor.staff_id
        self.store.register_actor(
            actor.actor_id,
            actor.role,
            display_name=actor.display_name,
            source=actor.source,
        )

        alias, target = parsed
        correction_type, canonical_target = self._classify_target(target)
        if correction_type is None or canonical_target is None:
            return CorrectionResult(
                learned=False,
                alias=alias,
                target=target,
                message=f"I could not learn that yet. Please use: alias means known medicine/payment/form.",
            )

        effective_approved = actor.is_owner if approved is None else approved
        if not effective_approved:
            pending = self.store.add_pending_correction(
                correction_type=correction_type,
                alias=alias,
                target=canonical_target,
                actor_id=actor.actor_id,
                actor_role=actor.role,
                owner_id=owner_id,
                staff_id=staff_id,
                source=actor.source,
            )
            self._append_feedback(
                correction_type,
                alias,
                canonical_target,
                owner_id=owner_id,
                staff_id=staff_id,
                actor_id=actor.actor_id,
                actor_role=actor.role,
                approved=False,
                status="pending",
                correction_id=str(pending["id"]),
            )
            return CorrectionResult(
                learned=False,
                correction_type=correction_type,
                alias=normalize_key(alias),
                target=canonical_target,
                message=f"Saved for owner approval: {normalize_key(alias)} means {canonical_target}.",
                pending_approval=True,
                correction_id=str(pending["id"]),
                actor_id=actor.actor_id,
                actor_role=actor.role,
            )

        self._commit_learning(
            correction_type,
            alias,
            canonical_target,
            owner_id=owner_id,
            staff_id=staff_id,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            approved_by_owner_id=owner_id if actor.is_owner else None,
            source=actor.source,
            approved=True,
        )
        self._append_feedback(
            correction_type,
            alias,
            canonical_target,
            owner_id=owner_id,
            staff_id=staff_id,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            approved=True,
            status="approved",
        )
        return CorrectionResult(
            learned=True,
            correction_type=correction_type,
            alias=normalize_key(alias),
            target=canonical_target,
            message=learned_message(alias, canonical_target, correction_type),
            actor_id=actor.actor_id,
            actor_role=actor.role,
        )

    def approve_pending(
        self,
        correction_id: str,
        *,
        owner_id: str,
        source: str | None = None,
    ) -> CorrectionResult:
        pending = self.store.pending_correction(correction_id)
        if pending is None:
            return CorrectionResult(
                learned=False,
                message=f"Pending correction {correction_id} was not found.",
            )
        if pending.get("status") != "pending":
            return CorrectionResult(
                learned=False,
                correction_id=correction_id,
                message=f"Pending correction {correction_id} is already {pending.get('status')}.",
            )

        correction_type = str(pending.get("type") or "")
        alias = str(pending.get("alias") or "")
        target = str(pending.get("target") or "")
        staff_id = pending.get("staff_id")
        self.store.register_actor(owner_id, "owner", source=source)
        self._commit_learning(
            correction_type,
            alias,
            target,
            owner_id=owner_id,
            staff_id=str(staff_id) if staff_id else None,
            actor_id=owner_id,
            actor_role="owner",
            approved_by_owner_id=owner_id,
            source=source,
            approved=True,
        )
        self.store.mark_pending_correction(correction_id, "approved", owner_id=owner_id)
        self._append_feedback(
            correction_type,
            alias,
            target,
            owner_id=owner_id,
            staff_id=str(staff_id) if staff_id else None,
            actor_id=owner_id,
            actor_role="owner",
            approved=True,
            status="approved",
            correction_id=correction_id,
        )
        return CorrectionResult(
            learned=True,
            correction_type=correction_type,
            alias=normalize_key(alias),
            target=target,
            message=learned_message(alias, target, correction_type),
            correction_id=correction_id,
            actor_id=owner_id,
            actor_role="owner",
        )

    def reject_pending(
        self,
        correction_id: str,
        *,
        owner_id: str,
    ) -> CorrectionResult:
        pending = self.store.mark_pending_correction(correction_id, "rejected", owner_id=owner_id)
        if pending is None:
            return CorrectionResult(False, message=f"Pending correction {correction_id} was not found.")
        return CorrectionResult(
            learned=False,
            correction_type=str(pending.get("type") or ""),
            alias=str(pending.get("alias") or ""),
            target=str(pending.get("target") or ""),
            message=f"Rejected pending correction {correction_id}.",
            correction_id=correction_id,
            actor_id=owner_id,
            actor_role="owner",
        )

    def _commit_learning(
        self,
        correction_type: str,
        alias: str,
        canonical_target: str,
        *,
        owner_id: str | None,
        staff_id: str | None,
        actor_id: str | None,
        actor_role: str | None,
        approved_by_owner_id: str | None,
        source: str | None,
        approved: bool,
    ) -> None:
        if correction_type == "medicine_alias":
            self.store.add_medicine_alias(
                alias,
                canonical_target,
                owner_id=owner_id,
                staff_id=staff_id,
                actor_id=actor_id,
                actor_role=actor_role,
                approved_by_owner_id=approved_by_owner_id,
                source=source,
                approved=approved,
            )
        elif correction_type == "payment_alias":
            self.store.add_payment_alias(
                alias,
                canonical_target,
                owner_id=owner_id,
                staff_id=staff_id,
                actor_id=actor_id,
                actor_role=actor_role,
                approved_by_owner_id=approved_by_owner_id,
                source=source,
                approved=approved,
            )
        elif correction_type == "form_alias":
            self.store.add_form_alias(
                alias,
                canonical_target,
                owner_id=owner_id,
                staff_id=staff_id,
                actor_id=actor_id,
                actor_role=actor_role,
                approved_by_owner_id=approved_by_owner_id,
                source=source,
                approved=approved,
            )
        elif correction_type == "packaging_alias":
            self.store.add_packaging_alias(
                alias,
                canonical_target,
                owner_id=owner_id,
                staff_id=staff_id,
                actor_id=actor_id,
                actor_role=actor_role,
                approved_by_owner_id=approved_by_owner_id,
                source=source,
                approved=approved,
            )
        elif correction_type == "unit_alias":
            self.store.add_unit_alias(
                alias,
                canonical_target,
                owner_id=owner_id,
                staff_id=staff_id,
                actor_id=actor_id,
                actor_role=actor_role,
                approved_by_owner_id=approved_by_owner_id,
                source=source,
                approved=approved,
            )

    def _append_feedback(
        self,
        correction_type: str,
        alias: str,
        canonical_target: str,
        *,
        owner_id: str | None,
        staff_id: str | None,
        actor_id: str | None,
        actor_role: str | None,
        approved: bool,
        status: str,
        correction_id: str | None = None,
    ) -> None:
        self.store.append_jsonl(
            "feedback_log.jsonl",
            {
                "type": correction_type,
                "pharmacy_id": self.store.pharmacy_id,
                "owner_id": owner_id,
                "staff_id": staff_id,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "alias": normalize_key(alias),
                "target": canonical_target,
                "approved": approved,
                "status": status,
                "correction_id": correction_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _classify_target(self, target: str) -> tuple[str | None, str | None]:
        clean_target = normalize_key(target)
        if not clean_target:
            return None, None

        payment = self._payment_target(clean_target)
        if payment:
            return "payment_alias", payment

        form = self._named_target("forms", clean_target)
        if form:
            return "form_alias", form

        packaging = self._named_target("packaging", clean_target)
        if packaging:
            return "packaging_alias", packaging

        unit = self._named_target("units", clean_target)
        if unit:
            return "unit_alias", unit

        medicine = self._medicine_target(clean_target)
        if medicine:
            return "medicine_alias", medicine

        # Owner-approved medicine names can be learned before onboarding adds full profiles.
        if len(clean_target) >= 3:
            return "medicine_alias", " ".join(word.capitalize() for word in clean_target.split())
        return None, None

    def _payment_target(self, target: str) -> str | None:
        forms_units = self.store.forms_units()
        for canonical, details in forms_units.get("payments", {}).items():
            aliases = {canonical, *(str(alias) for alias in details.get("aliases", []))}
            if target in {normalize_key(alias) for alias in aliases}:
                return canonical
        return None

    def _named_target(self, section: str, target: str) -> str | None:
        forms_units = self.store.forms_units()
        for canonical, details in forms_units.get(section, {}).items():
            aliases = {canonical, *(str(alias) for alias in details.get("aliases", []))}
            if target in {normalize_key(alias) for alias in aliases}:
                return canonical
        return None

    def _medicine_target(self, target: str) -> str | None:
        brain = MedicineBrain(self.store)
        target_key = compact_key(target)
        for profile in brain.profiles:
            keys = {compact_key(profile.name), *(compact_key(alias) for alias in profile.aliases)}
            if target_key in keys:
                return profile.name
        return None


def parse_correction_statement(text: str) -> tuple[str, str] | None:
    clean = " ".join(str(text or "").strip().split())
    clean = re.sub(r"^(?:learn|teach|remember)\s+", "", clean, flags=re.IGNORECASE)
    match = re.fullmatch(
        r"(.+?)\s*(?:=|means|mean)\s*(.+)",
        clean,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    alias = normalize_correction_side(match.group(1))
    target = normalize_correction_side(match.group(2))
    if not alias or not target or alias == target:
        return None
    return alias, target


def normalize_correction_side(value: str) -> str:
    text = str(value or "").strip().strip("\"'`.,:;!?")
    text = re.sub(r"^(?:when i say|if i say|i say|we say|staff say)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def learned_message(alias: str, target: str, correction_type: str) -> str:
    label = {
        "medicine_alias": "medicine",
        "payment_alias": "payment",
        "form_alias": "form",
        "packaging_alias": "packaging",
        "unit_alias": "unit",
    }.get(correction_type, "correction")
    return f"Learned {label}: {normalize_key(alias)} means {target}."
