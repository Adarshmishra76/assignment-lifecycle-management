from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.core.ids import next_public_id
from app.core.lifecycle import RESUBMISSION_TRANSITIONS, assert_transition
from app.core.time import utcnow
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.resubmission import Resubmission
from app.models.submission import Submission
from app.models.user import User
from app.schemas.academic import ResubmissionCreate, ResubmissionDecision, SubmissionCreate
from app.services.access import learner_profile, require_can_grade
from app.services.audit import record_audit
from app.services.submission_service import create_resubmitted_work


def request_resubmission(db: Session, payload: ResubmissionCreate, user: User) -> Resubmission:
    learner = learner_profile(db, user)
    if user.role != "learner" or not learner:
        raise ForbiddenError("Only learners can request resubmissions")
    assignment = db.get(Assignment, payload.assignment_id)
    if not assignment:
        raise NotFoundError("Assignment not found")
    previous = db.get(Submission, payload.previous_submission_id)
    if not previous or previous.learner_id != learner.id or previous.assignment_id != assignment.id:
        raise ValidationAppError("Previous submission is invalid")
    if assignment.resubmission_policy == "none" or assignment.max_resubmissions <= 0:
        raise ValidationAppError("Resubmissions are not allowed for this assignment")
    used = db.scalar(
        select(func.count()).select_from(Submission).where(
            Submission.assignment_id == assignment.id,
            Submission.learner_id == learner.id,
        )
    ) or 0
    if used > assignment.max_resubmissions:
        raise ValidationAppError("Resubmission attempts exhausted")
    pending = db.scalar(
        select(Resubmission).where(
            Resubmission.assignment_id == assignment.id,
            Resubmission.learner_id == learner.id,
            Resubmission.status.in_(["requested", "approved"]),
        )
    )
    if pending:
        raise ValidationAppError("A resubmission request is already in progress")
    status = "approved" if assignment.resubmission_policy == "automatic" else "requested"
    record = Resubmission(
        public_id=next_public_id(db, Resubmission, "RSB"),
        assignment_id=assignment.id,
        learner_id=learner.id,
        previous_submission_id=previous.id,
        status=status,
        decided_at=utcnow() if status == "approved" else None,
        decision_reason="Automatic policy approval" if status == "approved" else None,
    )
    db.add(record)
    db.flush()
    record_audit(
        db,
        actor_id=user.id,
        entity_type="resubmission",
        entity_id=record.id,
        action="request",
        to_state=status,
    )
    db.commit()
    db.refresh(record)
    return record


def decide_resubmission(db: Session, resubmission_id: int, payload: ResubmissionDecision, user: User) -> Resubmission:
    record = db.get(Resubmission, resubmission_id)
    if not record:
        raise NotFoundError("Resubmission not found")
    assignment = db.get(Assignment, record.assignment_id)
    course = db.get(Course, assignment.course_id)
    require_can_grade(db, user, course)
    target = "approved" if payload.approved else "denied"
    try:
        assert_transition(record.status, target, RESUBMISSION_TRANSITIONS, "resubmission")
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc
    record.status = target
    record.decided_at = utcnow()
    record.decided_by_id = user.id
    record.decision_reason = payload.reason
    record_audit(
        db,
        actor_id=user.id,
        entity_type="resubmission",
        entity_id=record.id,
        action="decide",
        to_state=target,
        payload={"reason": payload.reason},
    )
    db.commit()
    db.refresh(record)
    return record


def complete_resubmission(db: Session, resubmission_id: int, payload: SubmissionCreate, user: User) -> Resubmission:
    record = db.get(Resubmission, resubmission_id)
    if not record:
        raise NotFoundError("Resubmission not found")
    learner = learner_profile(db, user)
    if not learner or learner.id != record.learner_id:
        raise ForbiddenError("Only the requesting learner can submit the new attempt")
    if record.status != "approved":
        raise ValidationAppError("Resubmission is not approved")
    assignment = db.get(Assignment, record.assignment_id)
    used = db.scalar(
        select(func.count()).select_from(Submission).where(
            Submission.assignment_id == assignment.id,
            Submission.learner_id == learner.id,
        )
    ) or 0
    if used > assignment.max_resubmissions:
        raise ValidationAppError("Resubmission attempts exhausted")
    submission = create_resubmitted_work(db, assignment, learner.id, payload, user.id)
    record.resulting_submission_id = submission.id
    record.status = "completed"
    record_audit(
        db,
        actor_id=user.id,
        entity_type="resubmission",
        entity_id=record.id,
        action="complete",
        to_state="completed",
        payload={"submission_id": submission.id},
    )
    db.commit()
    db.refresh(record)
    return record


def list_resubmissions(db: Session, user: User, page: int, page_size: int):
    stmt = select(Resubmission)
    count_stmt = select(func.count()).select_from(Resubmission)
    if user.role == "learner":
        learner = learner_profile(db, user)
        if not learner:
            return [], 0
        stmt = stmt.where(Resubmission.learner_id == learner.id)
        count_stmt = count_stmt.where(Resubmission.learner_id == learner.id)
    total = db.scalar(count_stmt) or 0
    items = db.scalars(stmt.order_by(Resubmission.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total
