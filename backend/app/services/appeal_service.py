from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.ids import next_public_id
from app.core.lifecycle import APPEAL_DECISIONS, APPEAL_TRANSITIONS, assert_transition
from app.core.time import utcnow
from app.models.course import Course
from app.models.grading import Grade
from app.models.resubmission import Appeal
from app.models.submission import Submission
from app.models.user import User
from app.schemas.academic import AppealCreate, AppealDecision
from app.services.access import APPEAL_REVIEW_ROLES, learner_profile, require_can_grade
from app.services.audit import record_audit
from app.services.grading_service import revise_grade


def create_appeal(db: Session, payload: AppealCreate, user: User) -> Appeal:
    learner = learner_profile(db, user)
    if user.role != "learner" or not learner:
        raise ForbiddenError("Only learners can file appeals")
    grade = db.get(Grade, payload.grade_id)
    if not grade:
        raise NotFoundError("Grade not found")
    if not grade.is_current:
        raise ValidationAppError("Appeals are allowed only for the current grade version")
    submission = db.get(Submission, grade.submission_id)
    if submission.learner_id != learner.id:
        raise ForbiddenError("Cannot appeal another learner's grade")
    existing = db.scalar(
        select(Appeal).where(Appeal.grade_id == grade.id, Appeal.learner_id == learner.id)
    )
    if existing:
        raise ConflictError("Duplicate appeal for this grade")
    appeal = Appeal(
        public_id=next_public_id(db, Appeal, "APL"),
        grade_id=grade.id,
        submission_id=submission.id,
        learner_id=learner.id,
        reason=payload.reason,
        evidence_refs=payload.evidence_refs,
        status="submitted",
    )
    db.add(appeal)
    db.flush()
    record_audit(
        db,
        actor_id=user.id,
        entity_type="appeal",
        entity_id=appeal.id,
        action="submit",
        to_state="submitted",
    )
    db.commit()
    db.refresh(appeal)
    return appeal


def start_review(db: Session, appeal_id: int, user: User) -> Appeal:
    appeal = db.get(Appeal, appeal_id)
    if not appeal:
        raise NotFoundError("Appeal not found")
    if user.role not in APPEAL_REVIEW_ROLES:
        raise ForbiddenError("Not authorized to review appeals")
    try:
        assert_transition(appeal.status, "under_review", APPEAL_TRANSITIONS, "appeal")
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc
    appeal.status = "under_review"
    appeal.reviewer_id = user.id
    record_audit(
        db,
        actor_id=user.id,
        entity_type="appeal",
        entity_id=appeal.id,
        action="review",
        from_state="submitted",
        to_state="under_review",
    )
    db.commit()
    db.refresh(appeal)
    return appeal


def decide_appeal(db: Session, appeal_id: int, payload: AppealDecision, user: User) -> Appeal:
    appeal = db.get(Appeal, appeal_id)
    if not appeal:
        raise NotFoundError("Appeal not found")
    if user.role not in APPEAL_REVIEW_ROLES:
        raise ForbiddenError("Not authorized to decide appeals")
    if payload.decision not in APPEAL_DECISIONS:
        raise ValidationAppError("Decision must be approved, rejected, or upheld")
    if appeal.status == "submitted":
        appeal.status = "under_review"
        appeal.reviewer_id = user.id
    try:
        assert_transition(appeal.status, payload.decision, APPEAL_TRANSITIONS, "appeal")
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc
    submission = db.get(Submission, appeal.submission_id)
    assignment = submission.assignment if hasattr(submission, "assignment") else None
    if assignment is None:
        from app.models.assignment import Assignment

        assignment = db.get(Assignment, submission.assignment_id)
    course = db.get(Course, assignment.course_id)
    require_can_grade(db, user, course)

    current = db.get(Grade, appeal.grade_id)
    appeal.status = payload.decision
    appeal.decision = payload.decision
    appeal.decision_reason = payload.decision_reason
    appeal.reviewer_id = user.id
    appeal.decided_at = utcnow()

    if payload.decision == "approved":
        if not payload.scores:
            raise ValidationAppError("Approved appeals must include revised criterion scores")
        new_grade = revise_grade(
            db,
            current,
            payload.scores,
            payload.decision_reason,
            user,
            payload.feedback,
        )
        appeal.resulting_grade_id = new_grade.id
    else:
        record_audit(
            db,
            actor_id=user.id,
            entity_type="grade",
            entity_id=current.id,
            action="appeal_no_change",
            payload={"decision": payload.decision, "reason": payload.decision_reason},
        )

    record_audit(
        db,
        actor_id=user.id,
        entity_type="appeal",
        entity_id=appeal.id,
        action="decide",
        to_state=payload.decision,
        payload={"reason": payload.decision_reason, "resulting_grade_id": appeal.resulting_grade_id},
    )
    db.commit()
    db.refresh(appeal)
    return appeal


def list_appeals(db: Session, user: User, page: int, page_size: int):
    stmt = select(Appeal)
    count_stmt = select(func.count()).select_from(Appeal)
    if user.role == "learner":
        learner = learner_profile(db, user)
        if not learner:
            return [], 0
        stmt = stmt.where(Appeal.learner_id == learner.id)
        count_stmt = count_stmt.where(Appeal.learner_id == learner.id)
    total = db.scalar(count_stmt) or 0
    items = db.scalars(stmt.order_by(Appeal.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total
