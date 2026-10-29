from decimal import ROUND_HALF_UP, Decimal

ASSIGNMENT_STATES = ("draft", "published", "closed", "archived")
ASSIGNMENT_TRANSITIONS = {
    "draft": {"published"},
    "published": {"closed"},
    "closed": {"archived"},
    "archived": set(),
}

ENROLLMENT_STATES = ("enrolled", "dropped", "completed")
ENROLLMENT_TRANSITIONS = {
    "enrolled": {"dropped", "completed"},
    "dropped": set(),
    "completed": set(),
}

SUBMISSION_STATES = ("submitted", "graded", "returned", "withdrawn")
SUBMISSION_TRANSITIONS = {
    "submitted": {"graded", "withdrawn"},
    "graded": {"returned"},
    "returned": set(),
    "withdrawn": set(),
}

RESUBMISSION_STATES = ("requested", "approved", "denied", "completed")
RESUBMISSION_TRANSITIONS = {
    "requested": {"approved", "denied"},
    "approved": {"completed"},
    "denied": set(),
    "completed": set(),
}

APPEAL_STATES = ("submitted", "under_review", "approved", "rejected", "upheld")
APPEAL_TRANSITIONS = {
    "submitted": {"under_review"},
    "under_review": {"approved", "rejected", "upheld"},
    "approved": set(),
    "rejected": set(),
    "upheld": set(),
}

APPEAL_DECISIONS = ("approved", "rejected", "upheld")
ROLES = (
    "learner",
    "instructor",
    "academic_admin",
    "support_staff",
    "platform_admin",
)

RESUBMISSION_POLICIES = ("none", "instructor_approval", "automatic")
ARTIFACT_STATUSES = ("available", "missing", "quarantined")
GRADE_STATUSES = ("draft", "posted", "revised", "superseded")


def assert_transition(current: str, target: str, table: dict[str, set[str]], label: str) -> None:
    allowed = table.get(current, set())
    if target not in allowed:
        raise ValueError(f"Invalid {label} transition: {current} -> {target}")


def round_score(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def apply_late_penalty(raw_score: Decimal, penalty_percent: Decimal) -> tuple[Decimal, Decimal]:
    """Return (penalty_amount, final_score). Penalty is a percent of raw score."""
    raw = round_score(raw_score)
    percent = round_score(penalty_percent)
    amount = round_score(raw * percent / Decimal("100"))
    final = round_score(max(Decimal("0.00"), raw - amount))
    return amount, final
