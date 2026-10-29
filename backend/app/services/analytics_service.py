from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment import Assignment
from app.models.grading import Grade, GradeRevision
from app.models.resubmission import Appeal, Resubmission
from app.models.submission import Submission, SubmissionArtifact


def overview_metrics(db: Session) -> dict:
    total_assignments = db.scalar(select(func.count()).select_from(Assignment)) or 0
    total_submissions = db.scalar(select(func.count()).select_from(Submission)) or 0
    late = db.scalar(select(func.count()).select_from(Submission).where(Submission.is_late.is_(True))) or 0
    on_time = total_submissions - late
    missing_artifacts = (
        db.scalar(
            select(func.count()).select_from(SubmissionArtifact).where(
                SubmissionArtifact.availability_status == "missing"
            )
        )
        or 0
    )
    total_artifacts = db.scalar(select(func.count()).select_from(SubmissionArtifact)) or 0
    pending_grading = (
        db.scalar(select(func.count()).select_from(Submission).where(Submission.status == "submitted")) or 0
    )
    avg_raw = db.scalar(select(func.avg(Grade.raw_score)).where(Grade.is_current.is_(True)))
    avg_final = db.scalar(select(func.avg(Grade.final_score)).where(Grade.is_current.is_(True)))
    resubmissions = db.scalar(select(func.count()).select_from(Resubmission)) or 0
    appeals = db.scalar(select(func.count()).select_from(Appeal)) or 0
    appeal_approved = db.scalar(select(func.count()).select_from(Appeal).where(Appeal.decision == "approved")) or 0
    appeal_rejected = db.scalar(select(func.count()).select_from(Appeal).where(Appeal.decision == "rejected")) or 0
    appeal_upheld = db.scalar(select(func.count()).select_from(Appeal).where(Appeal.decision == "upheld")) or 0
    grade_changes = (
        db.scalar(select(func.count()).select_from(GradeRevision).where(GradeRevision.previous_final_score.is_not(None)))
        or 0
    )
    turnaround = db.scalar(
        select(func.avg(func.julianday(Grade.created_at) - func.julianday(Submission.submitted_at)))
        .select_from(Grade)
        .join(Submission, Submission.id == Grade.submission_id)
        .where(Grade.revision_number == 1)
    )
    improvement = _resubmission_improvement(db)
    return {
        "resubmission_score_improvement": improvement,
        "total_assignments": total_assignments,
        "total_submissions": total_submissions,
        "on_time_rate": (on_time / total_submissions) if total_submissions else 0,
        "late_rate": (late / total_submissions) if total_submissions else 0,
        "missing_artifact_rate": (missing_artifacts / total_artifacts) if total_artifacts else 0,
        "pending_grading": pending_grading,
        "average_grading_turnaround_days": float(turnaround or 0),
        "average_raw_grade": float(avg_raw or 0),
        "average_final_grade": float(avg_final or 0),
        "resubmission_rate": (resubmissions / total_submissions) if total_submissions else 0,
        "appeal_rate": (appeals / total_submissions) if total_submissions else 0,
        "appeal_outcomes": {
            "approved": appeal_approved,
            "rejected": appeal_rejected,
            "upheld": appeal_upheld,
        },
        "grade_change_rate": (grade_changes / total_submissions) if total_submissions else 0,
    }


def _resubmission_improvement(db: Session) -> float:
    """Average (final score of resubmitted attempt - final score of previous attempt)."""
    from sqlalchemy.orm import aliased

    prev = aliased(Grade)
    new = aliased(Grade)
    value = db.scalar(
        select(func.avg(new.final_score - prev.final_score))
        .select_from(Resubmission)
        .join(prev, (prev.submission_id == Resubmission.previous_submission_id) & prev.is_current.is_(True))
        .join(new, (new.submission_id == Resubmission.resulting_submission_id) & new.is_current.is_(True))
    )
    return float(value or 0)
