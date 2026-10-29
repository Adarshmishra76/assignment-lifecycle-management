"""Rubric scoring, the late-penalty rule, revisions and who may grade."""
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import AuditEvent, GradePenalty
from tests.helpers import API, D


def _penalty_rows(world, submission_id):
    world.db.expire_all()
    return list(world.db.scalars(select(GradePenalty).where(GradePenalty.submission_id == submission_id)))


# ---- scoring -----------------------------------------------------------------------------
def test_on_time_grade_sums_criteria_and_records_history(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)

    grade = world.grade_ok(assignment, submission_id, [50, 30], feedback="Good structure.")

    assert D(grade["raw_score"]) == D("80.00")
    assert D(grade["late_penalty_amount"]) == D("0.00")
    assert D(grade["final_score"]) == D("80.00")
    assert grade["late_penalty_applied"] is False
    assert (grade["status"], grade["revision_number"], grade["is_current"]) == ("posted", 1, True)
    assert len(grade["scores"]) == 2

    revisions = world.client.get(f"{API}/submissions/{submission_id}/revisions", headers=world.inst_h).json()
    assert len(revisions) == 1
    assert revisions[0]["reason"] == "Initial grade"
    assert revisions[0]["previous_final_score"] is None
    assert D(revisions[0]["new_final_score"]) == D("80.00")

    feedback = world.client.get(f"{API}/submissions/{submission_id}/feedback", headers=world.inst_h).json()
    assert [f["body"] for f in feedback] == ["Good structure."]

    submission = world.client.get(f"{API}/submissions/{submission_id}", headers=world.inst_h).json()
    assert submission["status"] == "graded"

    world.db.expire_all()
    audit = world.db.scalars(
        select(AuditEvent).where(AuditEvent.entity_type == "grade", AuditEvent.entity_id == grade["id"])
    ).all()
    assert [a.action for a in audit] == ["grade"]


def test_each_criterion_is_rounded_before_summing(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    grade = world.grade_ok(assignment, submission_id, ["10.005", "10.005"])
    # 10.005 -> 10.01 each; rounding the sum instead would give 20.01
    assert D(grade["raw_score"]) == D("20.02")


def test_full_marks_are_accepted(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    grade = world.grade_ok(assignment, world.submit_ok(learner, assignment), [60, 40])
    assert D(grade["raw_score"]) == D("100.00")


# ---- grade over rubric maximum -------------------------------------------------------------
@pytest.mark.parametrize("values", [[61, 30], [50, 40.01], [-1, 30]])
def test_scores_outside_the_criterion_range_are_rejected_and_nothing_is_saved(world, values):
    assignment = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)

    response = world.grade(assignment, submission_id, values)

    assert response.status_code == 422
    assert "exceeds maximum" in response.json()["detail"]
    assert world.client.get(f"{API}/submissions/{submission_id}/grades", headers=world.inst_h).json() == []
    assert world.client.get(f"{API}/submissions/{submission_id}", headers=world.inst_h).json()["status"] == "submitted"


def test_every_criterion_must_be_scored(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    payload = world.grade_payload(assignment, submission_id, [50, 30])
    payload["scores"] = payload["scores"][:1]
    response = world.client.post(f"{API}/grades", json=payload, headers=world.inst_h)
    assert response.status_code == 422
    assert "every rubric criterion" in response.json()["detail"]


def test_scores_for_a_criterion_of_another_rubric_are_rejected(world):
    assignment = world.create_assignment()
    other = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    payload = world.grade_payload(other, submission_id, [10, 10])
    response = world.client.post(f"{API}/grades", json=payload, headers=world.inst_h)
    assert response.status_code == 422


# ---- late penalty ---------------------------------------------------------------------------
def test_late_submission_gets_one_penalty_of_ten_percent_of_raw(world):
    assignment = world.create_assignment(overdue=True)
    learner = world.add_learner()
    submission = world.submit(learner, assignment)
    assert submission.status_code == 200 and submission.json()["is_late"] is True

    grade = world.grade_ok(assignment, submission.json()["id"], [50, 30])

    assert D(grade["raw_score"]) == D("80.00")
    assert D(grade["late_penalty_amount"]) == D("8.00")
    assert D(grade["final_score"]) == D("72.00")
    assert grade["late_penalty_applied"] is True
    assert len(_penalty_rows(world, submission.json()["id"])) == 1


def test_on_time_submission_has_no_penalty_row(world):
    case = world.graded_submission(values=(50, 30))
    assert D(case.grade["late_penalty_amount"]) == D("0.00")
    assert _penalty_rows(world, case.submission_id) == []


def test_grading_twice_is_a_conflict_and_cannot_penalise_twice(world):
    case = world.graded_submission(late=True)
    assert D(case.grade["final_score"]) == D("72.00")

    again = world.grade(case.assignment, case.submission_id, [50, 30])

    assert again.status_code == 409
    assert len(_penalty_rows(world, case.submission_id)) == 1
    current = world.client.get(f"{API}/grades/{case.grade_id}", headers=world.inst_h).json()
    assert D(current["final_score"]) == D("72.00")


def test_database_refuses_a_second_late_penalty_for_the_same_submission(world):
    case = world.graded_submission(late=True)
    with pytest.raises(IntegrityError):
        world.db.add(
            GradePenalty(
                grade_id=case.grade_id,
                submission_id=case.submission_id,
                penalty_type="late",
                amount=Decimal("1.00"),
            )
        )
        world.db.commit()
    world.db.rollback()
    assert len(_penalty_rows(world, case.submission_id)) == 1


def test_penalty_cannot_be_forced_onto_an_on_time_submission(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    response = world.grade(assignment, submission_id, [50, 30], apply_late_penalty=True)
    assert response.status_code == 422
    assert "late submissions" in response.json()["detail"].lower()


def test_grader_may_waive_the_penalty_on_a_late_submission(world):
    assignment = world.create_assignment(overdue=True)
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    grade = world.grade_ok(assignment, submission_id, [50, 30], apply_late_penalty=False)
    assert grade["late_penalty_applied"] is False
    assert D(grade["final_score"]) == D("80.00")
    assert _penalty_rows(world, submission_id) == []


def test_penalty_percentage_comes_from_the_assignment(world):
    assignment = world.create_assignment(overdue=True, late_penalty_percent="25.00")
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    grade = world.grade_ok(assignment, submission_id, [60, 40])
    assert D(grade["late_penalty_amount"]) == D("25.00")
    assert D(grade["final_score"]) == D("75.00")


# ---- revisions --------------------------------------------------------------------------------
def test_revising_a_late_grade_recalculates_the_penalty_without_stacking_it(world):
    case = world.graded_submission(late=True, values=(50, 30))

    response = world.revise(case.assignment, case.grade_id, [60, 30], reason="Missed a correct proof")

    assert response.status_code == 200, response.text
    revised = response.json()
    assert D(revised["raw_score"]) == D("90.00")
    assert D(revised["late_penalty_amount"]) == D("9.00")
    assert D(revised["final_score"]) == D("81.00")  # 90 - 10%, not 90 - 8 - 9
    assert (revised["revision_number"], revised["status"], revised["is_current"]) == (2, "revised", True)

    rows = _penalty_rows(world, case.submission_id)
    assert len(rows) == 1
    assert rows[0].amount == D("9.00")

    old = world.client.get(f"{API}/grades/{case.grade_id}", headers=world.inst_h).json()
    assert (old["is_current"], old["status"]) == (False, "superseded")
    assert D(old["final_score"]) == D("72.00")  # history is preserved, not overwritten


def test_revision_history_is_chronological_and_keeps_reasons(world):
    case = world.graded_submission(values=(50, 30))
    second = world.revise(case.assignment, case.grade_id, [55, 30], reason="First review").json()
    world.revise(case.assignment, second["id"], [60, 35], reason="Second review")

    revisions = world.client.get(f"{API}/submissions/{case.submission_id}/revisions", headers=world.inst_h).json()
    revisions.sort(key=lambda r: r["id"])

    assert [r["reason"] for r in revisions] == ["Initial grade", "First review", "Second review"]
    assert [r["previous_final_score"] for r in revisions][0] is None
    assert [D(r["new_final_score"]) for r in revisions] == [D("80.00"), D("85.00"), D("95.00")]
    assert D(revisions[2]["previous_final_score"]) == D("85.00")

    grades = world.client.get(f"{API}/submissions/{case.submission_id}/grades", headers=world.inst_h).json()
    assert [g["revision_number"] for g in grades] == [1, 2, 3]
    assert [g["is_current"] for g in grades] == [False, False, True]


def test_revision_requires_a_real_reason_and_changes_nothing_without_one(world):
    case = world.graded_submission()
    blank = world.revise(case.assignment, case.grade_id, [60, 30], reason="   ")
    assert blank.status_code == 422

    missing = world.client.post(
        f"{API}/grades/{case.grade_id}/revise",
        json={"scores": [{"criterion_id": c, "score": 10} for c in case.assignment.criteria]},
        headers=world.inst_h,
    )
    assert missing.status_code == 422

    grades = world.client.get(f"{API}/submissions/{case.submission_id}/grades", headers=world.inst_h).json()
    assert len(grades) == 1 and grades[0]["is_current"] is True


def test_only_the_current_grade_can_be_revised(world):
    case = world.graded_submission()
    assert world.revise(case.assignment, case.grade_id, [60, 30]).status_code == 200
    stale = world.revise(case.assignment, case.grade_id, [10, 10])
    assert stale.status_code == 409


def test_revision_cannot_exceed_criterion_maximum(world):
    case = world.graded_submission()
    response = world.revise(case.assignment, case.grade_id, [61, 30])
    assert response.status_code == 422


# ---- who may grade / read ---------------------------------------------------------------------
def test_learner_cannot_grade(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    response = world.grade(assignment, submission_id, [50, 30], headers=learner.headers)
    assert response.status_code == 403


def test_support_staff_cannot_grade(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    support = world.add_staff("support@demo.local", "support_staff")
    assert world.grade(assignment, submission_id, [50, 30], headers=support.headers).status_code == 403


def test_instructor_of_another_course_cannot_grade_or_revise(world):
    case = world.graded_submission()
    other = world.add_staff("other@demo.local", "instructor")
    assignment = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)

    assert world.grade(assignment, submission_id, [50, 30], headers=other.headers).status_code == 403
    assert world.revise(case.assignment, case.grade_id, [60, 30], headers=other.headers).status_code == 403


def test_academic_admin_can_grade_any_course(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    admin = world.add_staff("academic@demo.local", "academic_admin")
    assert world.grade(assignment, submission_id, [50, 30], headers=admin.headers).status_code == 200


def test_grading_unknown_submission_is_404(world):
    assignment = world.create_assignment()
    response = world.grade(assignment, 99999, [50, 30])
    assert response.status_code == 404


def test_learner_reads_own_grade_but_not_a_classmates(world):
    case = world.graded_submission()
    classmate = world.add_learner()
    assert world.client.get(f"{API}/grades/{case.grade_id}", headers=case.learner.headers).status_code == 200
    assert world.client.get(f"{API}/grades/{case.grade_id}", headers=classmate.headers).status_code == 403


# ---- regressions for defects that were fixed ---------------------------------------------------
def test_repeating_a_criterion_is_a_validation_error_and_saves_nothing(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    first, second = assignment.criteria
    payload = {
        "submission_id": submission_id,
        "scores": [
            {"criterion_id": first, "score": 10},
            {"criterion_id": second, "score": 10},
            {"criterion_id": second, "score": 10},
        ],
    }

    response = world.client.post(f"{API}/grades", json=payload, headers=world.inst_h)

    assert response.status_code == 422
    assert world.client.get(f"{API}/submissions/{submission_id}/grades", headers=world.inst_h).json() == []


def test_waived_late_penalty_stays_waived_when_the_grade_is_revised(world):
    assignment = world.create_assignment(overdue=True)
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    grade = world.grade_ok(assignment, submission_id, [50, 30], apply_late_penalty=False)

    revised = world.revise(assignment, grade["id"], [60, 30]).json()

    assert D(revised["late_penalty_amount"]) == D("0.00")
    assert D(revised["final_score"]) == D("90.00")
    assert _penalty_rows(world, submission_id) == []


@pytest.mark.parametrize("suffix", ["grades", "feedback", "revisions"])
def test_grade_history_is_visible_to_its_owner_and_staff_only(world, suffix):
    case = world.graded_submission()
    url = f"{API}/submissions/{case.submission_id}/{suffix}"
    classmate = world.add_learner()
    other_instructor = world.add_staff("other@demo.local", "instructor")

    assert world.client.get(url, headers=classmate.headers).status_code == 403
    assert world.client.get(url, headers=other_instructor.headers).status_code == 403
    assert world.client.get(url, headers=case.learner.headers).status_code == 200
    assert world.client.get(url, headers=world.inst_h).status_code == 200
    assert world.client.get(url, headers=world.admin_h).status_code == 200


def test_grade_history_of_an_unknown_submission_is_404(world):
    assert world.client.get(f"{API}/submissions/99999/grades", headers=world.inst_h).status_code == 404
