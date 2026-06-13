from __future__ import annotations

APP_BRAND = "MS2.0"
LEGACY_APP_BRAND = "PharMareen"

SETUP_WELCOME = f"Welcome to {APP_BRAND} setup 😁 Let's set up your pharmacy quickly."
ONBOARDING_DETAILS_REQUEST = (
    "Please send: pharmacy name, owner name, branch name, location, and payment modes."
)
ONBOARDING_EXAMPLE = (
    "Example: Pharmacy: Zuri Chemist; Owner: Amina; Branch: Main; "
    "Location: Nairobi; Payments: cash, mpesa, credit"
)


def onboarding_prompt(*, include_example: bool = False) -> str:
    prompt = f"{SETUP_WELCOME} {ONBOARDING_DETAILS_REQUEST}"
    if include_example:
        return f"{prompt}\n\n{ONBOARDING_EXAMPLE}"
    return prompt


def unregistered_setup_prompt() -> str:
    return f"This number is not registered yet. Reply START to set up {APP_BRAND} for your pharmacy."
