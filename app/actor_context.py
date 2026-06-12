from __future__ import annotations

from dataclasses import dataclass


OWNER_ROLES = {"owner", "admin"}
STAFF_ROLES = {"staff", "cashier"}


@dataclass(frozen=True)
class ActorContext:
    pharmacy_id: str = "default"
    actor_id: str | None = None
    role: str = "owner"
    source: str | None = None
    display_name: str | None = None

    @property
    def is_owner(self) -> bool:
        return normalize_role(self.role) in OWNER_ROLES

    @property
    def owner_id(self) -> str | None:
        return self.actor_id if self.is_owner else None

    @property
    def staff_id(self) -> str | None:
        return None if self.is_owner else self.actor_id


def build_actor_context(
    *,
    pharmacy_id: str = "default",
    actor_context: ActorContext | None = None,
    actor_id: str | None = None,
    owner_id: str | None = None,
    staff_id: str | None = None,
    actor_role: str | None = None,
    source: str | None = None,
    display_name: str | None = None,
) -> ActorContext:
    if actor_context is not None:
        context_pharmacy_id = actor_context.pharmacy_id
        if not context_pharmacy_id or context_pharmacy_id == "default":
            context_pharmacy_id = pharmacy_id or "default"
        return ActorContext(
            pharmacy_id=context_pharmacy_id,
            actor_id=actor_context.actor_id,
            role=normalize_role(actor_context.role),
            source=actor_context.source or source,
            display_name=actor_context.display_name or display_name,
        )

    resolved_actor_id = actor_id or owner_id or staff_id
    role = normalize_role(actor_role)
    if actor_role is None:
        if owner_id:
            role = "owner"
        elif staff_id:
            role = "staff"
        else:
            # Backward-compatible default for existing single-owner flows.
            role = "owner"

    return ActorContext(
        pharmacy_id=pharmacy_id or "default",
        actor_id=resolved_actor_id,
        role=role,
        source=source,
        display_name=display_name,
    )


def normalize_role(role: str | None) -> str:
    clean = str(role or "owner").strip().lower()
    if clean in OWNER_ROLES:
        return "owner"
    if clean in STAFF_ROLES:
        return clean
    return "staff" if clean in {"employee", "assistant", "seller"} else "owner"
