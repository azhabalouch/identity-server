import re

from personas.constants import CONTEXTS

SCOPE_PATTERN = re.compile(r"^(read|write):profile:(professional|personal|gaming|\*)$")
SCOPE_FORMAT_HINT = (
    "Send one scope in the form read:profile:<context> or write:profile:<context>. "
    f"<context> must be one of {', '.join(CONTEXTS)}, in lower case. "
    "read:profile:* reads every persona the user has consented to."
)

def parse_scope(scope):
    """Return (action, context) or None when the scope string is invalid."""

    match = SCOPE_PATTERN.match(scope or "")

    if not match:
        return None
    
    action, context = match.groups()

    if action == "write" and context == "*":
        return None
    
    return action, context