

# Valid state transitions
LEGAL_TRANSITIONS: dict[str, list[str]] = {
    "draft":                ["submitted"],
    "submitted":            ["under_review"],
    "under_review":         ["approved", "rejected", "more_info_requested"],
    "more_info_requested":  ["submitted"],
    "approved":             [],
    "rejected":             [],
}

ALL_STATES = list(LEGAL_TRANSITIONS.keys())


class IllegalTransitionError(Exception):
    """Raised when a requested state transition is not permitted."""

    def __init__(self, current: str, requested: str):
        self.current = current
        self.requested = requested
        allowed = LEGAL_TRANSITIONS.get(current, [])
        allowed_str = ", ".join(f"'{s}'" for s in allowed) if allowed else "none (terminal state)"
        super().__init__(
            f"Cannot transition from '{current}' to '{requested}'. "
            f"Allowed transitions from '{current}': {allowed_str}."
        )


def validate_transition(current_state: str, new_state: str) -> None:
    """Raise IllegalTransitionError if transition is not permitted."""
    allowed = LEGAL_TRANSITIONS.get(current_state, [])
    if new_state not in allowed:
        raise IllegalTransitionError(current_state, new_state)


def apply_transition(submission, new_state: str, reviewer_note: str = "") -> str:
    """Validate and apply a state transition."""
    from django.utils import timezone

    validate_transition(submission.state, new_state)
    old_state = submission.state

    submission.state = new_state


    if new_state == "submitted" and submission.submitted_at is None:
        submission.submitted_at = timezone.now()

    if reviewer_note:
        submission.reviewer_note = reviewer_note

    submission.save(update_fields=["state", "submitted_at", "reviewer_note", "updated_at"])
    return old_state


def get_allowed_transitions(current_state: str) -> list[str]:
    """Return the list of states this submission can legally move to."""
    return LEGAL_TRANSITIONS.get(current_state, [])
