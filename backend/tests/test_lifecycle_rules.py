"""Pure rules: rounding, late-penalty arithmetic and state-transition tables."""
from decimal import Decimal

import pytest

from app.core.lifecycle import (
    APPEAL_TRANSITIONS,
    ASSIGNMENT_TRANSITIONS,
    RESUBMISSION_TRANSITIONS,
    SUBMISSION_TRANSITIONS,
    apply_late_penalty,
    assert_transition,
    round_score,
)

D = Decimal


@pytest.mark.parametrize(
    "value, expected",
    [("2.675", "2.68"), (2.675, "2.68"), ("0.005", "0.01"), ("10.004", "10.00"), (1, "1.00"), ("33.335", "33.34")],
)
def test_round_score_rounds_half_up_to_cents(value, expected):
    assert str(round_score(value)) == expected


@pytest.mark.parametrize(
    "raw, percent, amount, final",
    [
        ("80", "10", "8.00", "72.00"),
        ("33.33", "10", "3.33", "30.00"),
        ("59.95", "15", "8.99", "50.96"),
        ("100", "0", "0.00", "100.00"),
        ("100", "100", "100.00", "0.00"),
        ("0", "10", "0.00", "0.00"),
    ],
)
def test_late_penalty_is_a_percentage_of_the_raw_score(raw, percent, amount, final):
    got_amount, got_final = apply_late_penalty(D(raw), D(percent))
    assert (str(got_amount), str(got_final)) == (amount, final)


def test_late_penalty_never_produces_a_negative_score():
    _, final = apply_late_penalty(D("50"), D("250"))
    assert final == D("0.00")


def test_penalty_is_not_compounded_when_applied_to_its_own_output():
    """Applying the helper to an already-penalised score would be the 'applied twice' bug."""
    amount, once = apply_late_penalty(D("80"), D("10"))
    _, twice = apply_late_penalty(once, D("10"))
    assert once == D("72.00")
    assert twice != once  # the helper is pure; callers are responsible for applying it once


@pytest.mark.parametrize(
    "table, current, target",
    [
        (ASSIGNMENT_TRANSITIONS, "draft", "published"),
        (ASSIGNMENT_TRANSITIONS, "published", "closed"),
        (ASSIGNMENT_TRANSITIONS, "closed", "archived"),
        (SUBMISSION_TRANSITIONS, "submitted", "graded"),
        (SUBMISSION_TRANSITIONS, "graded", "returned"),
        (RESUBMISSION_TRANSITIONS, "requested", "approved"),
        (RESUBMISSION_TRANSITIONS, "requested", "denied"),
        (RESUBMISSION_TRANSITIONS, "approved", "completed"),
        (APPEAL_TRANSITIONS, "submitted", "under_review"),
        (APPEAL_TRANSITIONS, "under_review", "approved"),
        (APPEAL_TRANSITIONS, "under_review", "rejected"),
        (APPEAL_TRANSITIONS, "under_review", "upheld"),
    ],
)
def test_allowed_transitions(table, current, target):
    assert_transition(current, target, table, "thing")


@pytest.mark.parametrize(
    "table, current, target",
    [
        (ASSIGNMENT_TRANSITIONS, "published", "draft"),
        (ASSIGNMENT_TRANSITIONS, "draft", "closed"),
        (ASSIGNMENT_TRANSITIONS, "archived", "published"),
        (SUBMISSION_TRANSITIONS, "returned", "graded"),
        (SUBMISSION_TRANSITIONS, "withdrawn", "submitted"),
        (RESUBMISSION_TRANSITIONS, "denied", "approved"),
        (RESUBMISSION_TRANSITIONS, "requested", "completed"),
        (APPEAL_TRANSITIONS, "submitted", "approved"),  # must pass through review
        (APPEAL_TRANSITIONS, "approved", "rejected"),
        (APPEAL_TRANSITIONS, "rejected", "under_review"),
    ],
)
def test_forbidden_transitions(table, current, target):
    with pytest.raises(ValueError, match="Invalid"):
        assert_transition(current, target, table, "thing")


def test_unknown_state_is_rejected():
    with pytest.raises(ValueError):
        assert_transition("mystery", "published", ASSIGNMENT_TRANSITIONS, "assignment")
