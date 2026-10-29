from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.core.ids import next_public_id
from app.core.lifecycle import ARTIFACT_STATUSES
from app.core.time import as_utc, utcnow
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.submission import Submission, SubmissionArtifact
from app.models.user import User
from app.schemas.academic import SubmissionCreate
from app.services.access import get_enrollment, learner_profile, require_can_grade
from app.services.audit import record_audit


def _next_version(db: Session, assignment_id: int, learner_id: int) -> int:
    current = db.scalar(
        select(func.coalesce(func.max(Submission.version_number), 0)).where(
            Submission.assignment_id == assignment_id,
            Submission.learner_id == learner_id,
        )
    )
    return int(current or 0) + 1


def create_submission(db: Session, payload: SubmissionCreate, user: User) -> Submission:
    assignment = db.get(Assignment, payload.assignment_id)
    if not assignment:
        raise NotFoundError("Assignment not found")
    if assignment.status != "published":
        raise ValidationAppError("Assignment is not open for submissions")
    if not assignment.current_version_id:
        raise ValidationAppError("Assignment has no published version")
    learner = learner_profile(db, user)
    if user.role != "learner" or not learner:
        raise ForbiddenError("Only enrolled learners can submit work")
    if not get_enrollment(db, assignment.course_id, learner.id):
        raise ForbiddenError("Learner is not enrolled in this course")
    now = utcnow()
    due = as_utc(assignment.due_at)
    is_late = bool(due and now > due)
    if is_late and not assignment.allow_late:
        raise ValidationAppError("Late submissions are not allowed")
    version_number = _next_version(db, assignment.id, learner.id)
    if version_number > 1:
        raise ValidationAppError("Use the resubmission workflow for additional attempts")
    submission = Submission(
        public_id=next_public_id(db, Submission, "SUB", 7),
        assignment_id=assignment.id,
        assignment_version_id=assignment.current_version_id,
        learner_id=learner.id,
        version_number=version_number,
        submitted_at=now,
        is_late=is_late,
        status="submitted",
    )
    db.add(submission)
    db.flush()
    for artifact in payload.artifacts:
        if artifact.availability_status not in ARTIFACT_STATUSES:
            raise ValidationAppError("Invalid artifact availability status")
        db.add(
            SubmissionArtifact(
                public_id=next_public_id(db, SubmissionArtifact, "ART", 7),
                submission_id=submission.id,
                filename=artifact.filename,
                mime_type=artifact.mime_type,
                file_size_bytes=artifact.file_size_bytes,
                checksum_sha256=artifact.checksum_sha256.lower(),
                availability_status=artifact.availability_status,
            )
        )
    record_audit(
        db,
        actor_id=user.id,
        entity_type="submission",
        entity_id=submission.id,
        action="submit",
        to_state="submitted",
        payload={"is_late": is_late, "version_number": version_number},
    )
    db.commit()
    return get_submission(db, submission.id, user)


def create_resubmitted_work(db: Session, assignment: Assignment, learner_id: int, payload: SubmissionCreate, actor_id: int) -> Submission:
    now = utcnow()
    due = as_utc(assignment.due_at)
    is_late = bool(due and now > due)
    version_number = _next_version(db, assignment.id, learner_id)
    submission = Submission(
        public_id=next_public_id(db, Submission, "SUB", 7),
        assignment_id=assignment.id,
        assignment_version_id=assignment.current_version_id,
        learner_id=learner_id,
        version_number=version_number,
        submitted_at=now,
        is_late=is_late,
        status="submitted",
    )
    db.add(submission)
    db.flush()
    for artifact in payload.artifacts:
        db.add(
            SubmissionArtifact(
                public_id=next_public_id(db, SubmissionArtifact, "ART", 7),
                submission_id=submission.id,
                filename=artifact.filename,
                mime_type=artifact.mime_type,
                file_size_bytes=artifact.file_size_bytes,
                checksum_sha256=artifact.checksum_sha256.lower(),
                availability_status=artifact.availability_status,
            )
        )
    record_audit(
        db,
        actor_id=actor_id,
        entity_type="submission",
        entity_id=submission.id,
        action="resubmit",
        to_state="submitted",
        payload={"version_number": version_number},
    )
    db.flush()
    return submission


def get_submission(db: Session, submission_id: int, user: User) -> Submission:
    submission = db.scalar(
        select(Submission)
        .options(joinedload(Submission.artifacts), joinedload(Submission.assignment))
        .where(Submission.id == submission_id)
    )
    if not submission:
        raise NotFoundError("Submission not found")
    if user.role == "learner":
        learner = learner_profile(db, user)
        if not learner or learner.id != submission.learner_id:
            raise ForbiddenError("Learners may only access their own submissions")
    elif user.role == "instructor":
        course = db.get(Course, submission.assignment.course_id)
        require_can_grade(db, user, course)
    return submission


def list_submissions(
    db: Session,
    user: User,
    assignment_id: int | None,
    learner_id: int | None,
    page: int,
    page_size: int,
    status: str | None = None,
):
    stmt = select(Submission).options(joinedload(Submission.artifacts))
    count_stmt = select(func.count()).select_from(Submission)
    if assignment_id:
        stmt = stmt.where(Submission.assignment_id == assignment_id)
        count_stmt = count_stmt.where(Submission.assignment_id == assignment_id)
    if status:
        stmt = stmt.where(Submission.status == status)
        count_stmt = count_stmt.where(Submission.status == status)
    if user.role == "learner":
        learner = learner_profile(db, user)
        if not learner:
            return [], 0
        stmt = stmt.where(Submission.learner_id == learner.id)
        count_stmt = count_stmt.where(Submission.learner_id == learner.id)
    elif learner_id:
        stmt = stmt.where(Submission.learner_id == learner_id)
        count_stmt = count_stmt.where(Submission.learner_id == learner_id)
    total = db.scalar(count_stmt) or 0
    items = db.scalars(stmt.order_by(Submission.id).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return list(items), total
