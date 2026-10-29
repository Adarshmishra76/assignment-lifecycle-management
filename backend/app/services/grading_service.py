from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.ids import next_public_id
from app.core.lifecycle import apply_late_penalty, round_score
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.grading import Feedback, Grade, GradePenalty, GradeRevision, RubricScore
from app.models.rubric import Rubric, RubricCriterion
from app.models.submission import Submission
from app.models.user import User
from app.schemas.academic import GradeCreate, RubricScoreIn
from app.services.access import learner_profile, require_can_grade
from app.services.audit import record_audit


def _load_submission(db: Session, submission_id: int) -> Submission:
    submission = db.scalar(
        select(Submission).options(joinedload(Submission.assignment)).where(Submission.id == submission_id)
    )
    if not submission:
        raise NotFoundError("Submission not found")
    return submission


def _rubric_for_submission(db: Session, submission: Submission) -> Rubric:
    rubric = db.scalar(
        select(Rubric).options(joinedload(Rubric.criteria)).where(Rubric.assignment_id == submission.assignment_id)
    )
    if not rubric:
        raise ValidationAppError("Published rubric is missing")
    return rubric


def _compute_raw(scores: list[RubricScoreIn], criteria: list[RubricCriterion]) -> Decimal:
    by_id = {c.id: c for c in criteria}
    submitted_ids = [s.criterion_id for s in scores]
    if len(submitted_ids) != len(set(submitted_ids)) or set(submitted_ids) != set(by_id):
        raise ValidationAppError("Scores must include every rubric criterion exactly once")
    raw = Decimal("0.00")
    for item in scores:
        criterion = by_id[item.criterion_id]
        score = round_score(item.score)
        if score < 0 or score > criterion.max_score:
            raise ValidationAppError(f"Score for criterion {criterion.id} exceeds maximum")
        raw += score
    return round_score(raw)


def create_grade(db: Session, payload: GradeCreate, user: User) -> Grade:
    if user.role == "learner":
        raise ForbiddenError("Learners cannot grade work")
    submission = _load_submission(db, payload.submission_id)
    course = db.get(Course, submission.assignment.course_id)
    require_can_grade(db, user, course)
    existing_current = db.scalar(
        select(Grade).where(Grade.submission_id == submission.id, Grade.is_current.is_(True))
    )
    if existing_current:
        raise ConflictError("Submission already has a current grade; use a revision or appeal")
    rubric = _rubric_for_submission(db, submission)
    raw = _compute_raw(payload.scores, list(rubric.criteria))
    assignment: Assignment = submission.assignment
    apply_penalty = payload.apply_late_penalty
    if apply_penalty is None:
        apply_penalty = bool(submission.is_late and assignment.allow_late and assignment.late_penalty_percent > 0)
    if apply_penalty and not submission.is_late:
        raise ValidationAppError("Late penalty can only be applied to late submissions")
    late_amount = Decimal("0.00")
    final = raw
    if apply_penalty:
        prior = db.scalar(
            select(GradePenalty).where(
                GradePenalty.submission_id == submission.id,
                GradePenalty.penalty_type == "late",
            )
        )
        if prior:
            raise ConflictError("Late penalty already applied to this submission version")
        late_amount, final = apply_late_penalty(raw, assignment.late_penalty_percent)
    grade = Grade(
        public_id=next_public_id(db, Grade, "GRD"),
        submission_id=submission.id,
        assignment_version_id=submission.assignment_version_id,
        rubric_id=rubric.id,
        revision_number=1,
        is_current=True,
        raw_score=raw,
        late_penalty_applied=bool(apply_penalty),
        late_penalty_amount=late_amount,
        final_score=final,
        status="posted",
        grader_id=user.id,
    )
    db.add(grade)
    db.flush()
    for item in payload.scores:
        db.add(
            RubricScore(
                public_id=next_public_id(db, RubricScore, "SCR", 7),
                grade_id=grade.id,
                criterion_id=item.criterion_id,
                score=round_score(item.score),
            )
        )
    if apply_penalty:
        db.add(
            GradePenalty(
                grade_id=grade.id,
                submission_id=submission.id,
                penalty_type="late",
                amount=late_amount,
            )
        )
    db.add(
        GradeRevision(
            public_id=next_public_id(db, GradeRevision, "GRV"),
            grade_id=grade.id,
            submission_id=submission.id,
            previous_final_score=None,
            new_final_score=final,
            reason="Initial grade",
            changed_by_id=user.id,
        )
    )
    if payload.feedback:
        db.add(
            Feedback(
                public_id=next_public_id(db, Feedback, "FBK"),
                grade_id=grade.id,
                submission_id=submission.id,
                author_id=user.id,
                body=payload.feedback,
            )
        )
    submission.status = "graded"
    record_audit(
        db,
        actor_id=user.id,
        entity_type="grade",
        entity_id=grade.id,
        action="grade",
        to_state="posted",
        payload={"raw_score": str(raw), "final_score": str(final)},
    )
    db.commit()
    return get_grade(db, grade.id, user)


def revise_grade(
    db: Session,
    current: Grade,
    scores: list[RubricScoreIn],
    reason: str,
    user: User,
    feedback: str | None = None,
) -> Grade:
    if not reason.strip():
        raise ValidationAppError("A reason is required for every grade change")
    submission = _load_submission(db, current.submission_id)
    rubric = _rubric_for_submission(db, submission)
    raw = _compute_raw(scores, list(rubric.criteria))
    assignment = submission.assignment
    late_amount = Decimal("0.00")
    final = raw
    # Carry the first grader's decision forward: a penalty that was waived stays waived,
    # and a penalty that was applied is recalculated (never stacked) on the new raw score.
    apply_penalty = bool(current.late_penalty_applied)
    existing_penalty = db.scalar(
        select(GradePenalty).where(
            GradePenalty.submission_id == submission.id,
            GradePenalty.penalty_type == "late",
        )
    )
    if apply_penalty and existing_penalty:
        late_amount = existing_penalty.amount
        # Recalculate using policy rather than copying a stale amount.
        late_amount, final = apply_late_penalty(raw, assignment.late_penalty_percent)
        existing_penalty.amount = late_amount
    elif apply_penalty and not existing_penalty:
        late_amount, final = apply_late_penalty(raw, assignment.late_penalty_percent)
        db.add(
            GradePenalty(
                grade_id=current.id,
                submission_id=submission.id,
                penalty_type="late",
                amount=late_amount,
            )
        )
    current.is_current = False
    current.status = "superseded"
    next_revision = (
        db.scalar(
            select(func.coalesce(func.max(Grade.revision_number), 0)).where(Grade.submission_id == submission.id)
        )
        or 0
    ) + 1
    grade = Grade(
        public_id=next_public_id(db, Grade, "GRD"),
        submission_id=submission.id,
        assignment_version_id=submission.assignment_version_id,
        rubric_id=rubric.id,
        revision_number=next_revision,
        is_current=True,
        raw_score=raw,
        late_penalty_applied=bool(apply_penalty),
        late_penalty_amount=late_amount,
        final_score=final,
        status="revised",
        grader_id=user.id,
    )
    db.add(grade)
    db.flush()
    for item in scores:
        db.add(
            RubricScore(
                public_id=next_public_id(db, RubricScore, "SCR", 7),
                grade_id=grade.id,
                criterion_id=item.criterion_id,
                score=round_score(item.score),
            )
        )
    db.add(
        GradeRevision(
            public_id=next_public_id(db, GradeRevision, "GRV"),
            grade_id=grade.id,
            submission_id=submission.id,
            previous_final_score=current.final_score,
            new_final_score=final,
            reason=reason,
            changed_by_id=user.id,
        )
    )
    if feedback:
        db.add(
            Feedback(
                public_id=next_public_id(db, Feedback, "FBK"),
                grade_id=grade.id,
                submission_id=submission.id,
                author_id=user.id,
                body=feedback,
            )
        )
    record_audit(
        db,
        actor_id=user.id,
        entity_type="grade",
        entity_id=grade.id,
        action="revise",
        from_state=str(current.final_score),
        to_state=str(final),
        payload={"reason": reason, "previous_grade_id": current.id},
    )
    db.flush()
    return grade


def get_grade(db: Session, grade_id: int, user: User) -> Grade:
    grade = db.scalar(select(Grade).options(joinedload(Grade.scores)).where(Grade.id == grade_id))
    if not grade:
        raise NotFoundError("Grade not found")
    submission = db.get(Submission, grade.submission_id)
    if user.role == "learner":
        learner = learner_profile(db, user)
        if not learner or learner.id != submission.learner_id:
            raise ForbiddenError("Learners may only view their own grades")
    return grade


def list_grades_for_submission(db: Session, submission_id: int) -> list[Grade]:
    return list(
        db.scalars(
            select(Grade)
            .options(joinedload(Grade.scores))
            .where(Grade.submission_id == submission_id)
            .order_by(Grade.revision_number)
        )
        .unique()
        .all()
    )


def list_feedback(db: Session, submission_id: int) -> list[Feedback]:
    return list(
        db.scalars(select(Feedback).where(Feedback.submission_id == submission_id).order_by(Feedback.created_at)).all()
    )


def list_revisions(db: Session, submission_id: int) -> list[GradeRevision]:
    return list(
        db.scalars(
            select(GradeRevision).where(GradeRevision.submission_id == submission_id).order_by(GradeRevision.created_at)
        ).all()
    )
