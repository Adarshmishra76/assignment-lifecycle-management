"""Appeals: filing rules, decisions, preserved history and atomic audit."""
import json
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Appeal, AuditEvent, Grade, GradeRevision, User
from app.schemas.academic import AppealDecision, RubricScoreIn
from app.services import appeal_service, grading_service
from tests.helpers import API, D


def _audit(world, entity_type, entity_id):
    world.db.expire_all()
    return list(
        world.db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
            .order_by(AuditEvent.id)
        )
    )


def _grades(world, submission_id):
    return world.client.get(f"{API}/submissions/{submission_id}/grades", headers=world.inst_h).json()


# ---- filing ---------------------------------------------------------------------------------
def test_learner_can_appeal_their_current_grade(world):
    case = world.graded_submission()
    response = world.file_appeal(case.learner, case.grade_id)
    assert response.status_code == 200, response.text
    appeal = response.json()
    assert appeal["status"] == "submitted"
    assert appeal["grade_id"] == case.grade_id
    assert [a.action for a in _audit(world, "appeal", appeal["id"])] == ["submit"]


def test_duplicate_appeal_for_the_same_grade_is_a_conflict(world):
    case = world.graded_submission()
    assert world.file_appeal(case.learner, case.grade_id).status_code == 200
    assert world.file_appeal(case.learner, case.grade_id).status_code == 409


def test_learner_cannot_appeal_a_classmates_grade(world):
    case = world.graded_submission()
    classmate = world.add_learner()
    assert world.file_appeal(classmate, case.grade_id).status_code == 403


def test_staff_cannot_file_appeals(world):
    case = world.graded_submission()
    response = world.client.post(
        f"{API}/appeals", json={"grade_id": case.grade_id, "reason": "x"}, headers=world.inst_h
    )
    assert response.status_code == 403


def test_superseded_grades_cannot_be_appealed(world):
    case = world.graded_submission()
    assert world.revise(case.assignment, case.grade_id, [55, 30]).status_code == 200
    response = world.file_appeal(case.learner, case.grade_id)
    assert response.status_code == 422
    assert "current grade" in response.json()["detail"]


def test_appealing_an_unknown_grade_is_404(world):
    learner = world.add_learner()
    assert world.file_appeal(learner, 99999).status_code == 404


def test_learner_lists_only_their_own_appeals(world):
    case = world.graded_submission()
    world.file_appeal(case.learner, case.grade_id)
    classmate = world.add_learner()
    assert world.client.get(f"{API}/appeals", headers=classmate.headers).json()["total"] == 0
    assert world.client.get(f"{API}/appeals", headers=case.learner.headers).json()["total"] == 1
    assert world.client.get(f"{API}/appeals", headers=world.inst_h).json()["total"] == 1


# ---- decisions -------------------------------------------------------------------------------
def test_approved_appeal_creates_a_new_grade_revision_and_audit_trail(world):
    case = world.graded_submission(values=(50, 30))

    appeal = world.approved_appeal(case, values=(60, 30))

    assert appeal["status"] == "approved" and appeal["decision"] == "approved"
    new_id = appeal["resulting_grade_id"]
    assert new_id and new_id != case.grade_id

    grades = _grades(world, case.submission_id)
    assert [g["revision_number"] for g in grades] == [1, 2]
    old, new = grades
    assert (old["is_current"], old["status"]) == (False, "superseded")
    assert D(old["final_score"]) == D("80.00")  # original preserved
    assert (new["is_current"], new["status"]) == (True, "revised")
    assert D(new["final_score"]) == D("90.00")

    revisions = world.client.get(f"{API}/submissions/{case.submission_id}/revisions", headers=world.inst_h).json()
    revisions.sort(key=lambda r: r["id"])
    assert [r["reason"] for r in revisions] == ["Initial grade", "Reviewed"]
    assert D(revisions[1]["previous_final_score"]) == D("80.00")

    grade_audit = _audit(world, "grade", new_id)
    assert [a.action for a in grade_audit] == ["revise"]
    assert json.loads(grade_audit[0].payload)["previous_grade_id"] == case.grade_id
    assert [a.action for a in _audit(world, "appeal", appeal["id"])] == ["submit", "decide"]


def test_approved_appeal_on_late_work_keeps_a_single_penalty(world):
    case = world.graded_submission(late=True, values=(50, 30))
    appeal = world.approved_appeal(case, values=(60, 30))
    new = [g for g in _grades(world, case.submission_id) if g["is_current"]][0]
    assert new["id"] == appeal["resulting_grade_id"]
    assert D(new["raw_score"]) == D("90.00")
    assert D(new["late_penalty_amount"]) == D("9.00")
    assert D(new["final_score"]) == D("81.00")  # 90 - 10%, penalty not stacked


def test_approved_appeal_without_scores_is_rejected_and_changes_nothing(world):
    case = world.graded_submission()
    appeal_id = world.file_appeal(case.learner, case.grade_id).json()["id"]

    response = world.decide_appeal(appeal_id, "approved", values=None)

    assert response.status_code == 422
    assert len(_grades(world, case.submission_id)) == 1
    listed = world.client.get(f"{API}/appeals", headers=world.inst_h).json()["items"][0]
    assert listed["status"] == "submitted" and listed["resulting_grade_id"] is None


@pytest.mark.parametrize("decision", ["rejected", "upheld"])
def test_declined_appeal_leaves_the_grade_untouched_but_is_audited(world, decision):
    case = world.graded_submission(values=(50, 30))
    appeal_id = world.file_appeal(case.learner, case.grade_id).json()["id"]

    response = world.decide_appeal(appeal_id, decision, reason="Marked correctly")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == decision and response.json()["resulting_grade_id"] is None
    grades = _grades(world, case.submission_id)
    assert len(grades) == 1 and grades[0]["is_current"] is True
    assert D(grades[0]["final_score"]) == D("80.00")
    assert "appeal_no_change" in [a.action for a in _audit(world, "grade", case.grade_id)]


def test_unknown_decision_is_rejected(world):
    case = world.graded_submission()
    appeal_id = world.file_appeal(case.learner, case.grade_id).json()["id"]
    assert world.decide_appeal(appeal_id, "maybe").status_code == 422


def test_decided_appeal_cannot_be_decided_again(world):
    case = world.graded_submission()
    appeal_id = world.file_appeal(case.learner, case.grade_id).json()["id"]
    assert world.decide_appeal(appeal_id, "rejected").status_code == 200
    assert world.decide_appeal(appeal_id, "approved", case.assignment, [60, 40]).status_code == 422
    assert len(_grades(world, case.submission_id)) == 1


def test_review_moves_a_submitted_appeal_under_review_once(world):
    case = world.graded_submission()
    appeal_id = world.file_appeal(case.learner, case.grade_id).json()["id"]
    first = world.client.post(f"{API}/appeals/{appeal_id}/review", headers=world.inst_h)
    assert first.status_code == 200 and first.json()["status"] == "under_review"
    again = world.client.post(f"{API}/appeals/{appeal_id}/review", headers=world.inst_h)
    assert again.status_code == 422


def test_learners_and_support_staff_cannot_review_or_decide(world):
    case = world.graded_submission()
    appeal_id = world.file_appeal(case.learner, case.grade_id).json()["id"]
    support = world.add_staff("support@demo.local", "support_staff")

    for headers in (case.learner.headers, support.headers):
        assert world.client.post(f"{API}/appeals/{appeal_id}/review", headers=headers).status_code == 403
        assert world.decide_appeal(appeal_id, "rejected", headers=headers).status_code == 403


def test_instructor_of_another_course_cannot_decide(world):
    case = world.graded_submission()
    appeal_id = world.file_appeal(case.learner, case.grade_id).json()["id"]
    other = world.add_staff("other@demo.local", "instructor")
    assert world.decide_appeal(appeal_id, "rejected", headers=other.headers).status_code == 403
    listed = world.client.get(f"{API}/appeals", headers=world.inst_h).json()["items"][0]
    assert listed["status"] == "submitted"


# ---- atomicity -------------------------------------------------------------------------------
def test_grade_change_and_audit_are_committed_together(world, monkeypatch):
    """If the audit write fails, the approved appeal must not leave a changed grade behind."""
    case = world.graded_submission(values=(50, 30))
    appeal_id = world.file_appeal(case.learner, case.grade_id).json()["id"]
    assert world.client.post(f"{API}/appeals/{appeal_id}/review", headers=world.inst_h).status_code == 200

    def failing_audit(*_args, **_kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(grading_service, "record_audit", failing_audit)
    world.db.expire_all()
    instructor = world.db.get(User, world.instructor.id)
    decision = AppealDecision(
        decision="approved",
        decision_reason="Rubric misapplied",
        scores=[RubricScoreIn(criterion_id=c, score=Decimal(v)) for c, v in zip(case.assignment.criteria, (60, 30))],
    )

    with pytest.raises(RuntimeError):
        appeal_service.decide_appeal(world.db, appeal_id, decision, instructor)
    world.db.rollback()

    world.db.expire_all()
    grades = list(world.db.scalars(select(Grade).where(Grade.submission_id == case.submission_id)))
    assert len(grades) == 1
    assert grades[0].is_current is True and grades[0].status == "posted"
    appeal = world.db.get(Appeal, appeal_id)
    assert appeal.status == "under_review"
    assert appeal.decision is None and appeal.resulting_grade_id is None
    revisions = world.db.scalars(select(GradeRevision).where(GradeRevision.submission_id == case.submission_id)).all()
    assert len(revisions) == 1
