from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.lifecycle import ASSIGNMENT_TRANSITIONS, round_score
from app.core.time import as_utc
from app.models import (
    Appeal,
    Assignment,
    AuditEvent,
    CourseEnrollment,
    Grade,
    GradePenalty,
    Rubric,
    RubricScore,
    Submission,
)

ROOT = Path(__file__).resolve().parents[3]


def validate_database(db: Session) -> dict:
    findings: list[dict] = []
    findings.extend(_pk_and_fk(db))
    findings.extend(_unenrolled_submissions(db))
    findings.extend(_grade_over_max(db))
    findings.extend(_duplicate_penalties(db))
    findings.extend(_penalty_arithmetic(db))
    findings.extend(_appeal_without_audit(db))
    findings.extend(_deadline_flags(db))
    findings.extend(_lifecycle_sanity(db))

    types = Counter(item["issue_type"] for item in findings)
    report = {
        "status": "fail" if findings else "pass",
        "anomaly_count": len(findings),
        "by_type": dict(types),
        "examples": findings[:20],
        "findings": findings,
        "note": "Detector does not read ground-truth labels.",
    }
    return report


def _pk_and_fk(db: Session) -> list[dict]:
    findings = []
    public_ids = defaultdict(list)
    for submission in db.scalars(select(Submission)).all():
        public_ids[submission.public_id].append(submission.id)
        if db.get(Assignment, submission.assignment_id) is None:
            findings.append(_finding("fk_violation", "submission", submission.id, "assignment_id missing"))
    for key, ids in public_ids.items():
        if len(ids) > 1:
            findings.append(_finding("duplicate_public_id", "submission", ids[0], f"{key} duplicated"))
    return findings


def _unenrolled_submissions(db: Session) -> list[dict]:
    findings = []
    enrollments = {
        (e.course_id, e.learner_id)
        for e in db.scalars(select(CourseEnrollment).where(CourseEnrollment.status == "enrolled")).all()
    }
    assignments = {a.id: a.course_id for a in db.scalars(select(Assignment)).all()}
    for submission in db.scalars(select(Submission)).all():
        course_id = assignments.get(submission.assignment_id)
        if course_id is None or (course_id, submission.learner_id) not in enrollments:
            findings.append(
                _finding(
                    "unenrolled_submission",
                    "submission",
                    submission.id,
                    "Submission belongs to a learner not enrolled in the course",
                )
            )
    return findings


def _grade_over_max(db: Session) -> list[dict]:
    findings = []
    rubrics = {
        r.id: r
        for r in db.scalars(select(Rubric).options(joinedload(Rubric.criteria))).unique().all()
    }
    for grade in db.scalars(select(Grade).options(joinedload(Grade.scores))).unique().all():
        rubric = rubrics.get(grade.rubric_id)
        if not rubric:
            findings.append(_finding("missing_rubric", "grade", grade.id, "Grade rubric missing"))
            continue
        if Decimal(str(grade.raw_score)) - Decimal(str(rubric.max_score)) > Decimal("0.009"):
            findings.append(
                _finding("grade_exceeds_rubric_max", "grade", grade.id, "Raw score exceeds rubric maximum")
            )
        crit_max = {c.id: c.max_score for c in rubric.criteria}
        for score in grade.scores:
            allowed = crit_max.get(score.criterion_id)
            if allowed is not None and Decimal(str(score.score)) - Decimal(str(allowed)) > Decimal("0.009"):
                findings.append(
                    _finding(
                        "grade_exceeds_rubric_max",
                        "rubric_score",
                        score.id,
                        "Criterion score exceeds maximum",
                    )
                )
    return findings


def _duplicate_penalties(db: Session) -> list[dict]:
    findings = []
    seen: dict[tuple[int, str], int] = {}
    for penalty in db.scalars(select(GradePenalty)).all():
        key = (penalty.submission_id, penalty.penalty_type)
        if key in seen:
            findings.append(
                _finding(
                    "duplicate_late_penalty",
                    "grade_penalty",
                    penalty.id,
                    "Late penalty applied more than once for a submission version",
                )
            )
        else:
            seen[key] = penalty.id
    return findings


def _penalty_arithmetic(db: Session) -> list[dict]:
    """A late penalty must reduce the raw score exactly once.

    The unique constraint stops a second penalty *row*, so a double deduction shows up as a
    final score that is lower than raw - recorded penalty.
    """
    findings = []
    for grade in db.scalars(select(Grade)).all():
        raw = Decimal(str(grade.raw_score))
        recorded = Decimal(str(grade.late_penalty_amount)) if grade.late_penalty_applied else Decimal("0.00")
        expected = max(Decimal("0.00"), raw - recorded)
        if abs(Decimal(str(grade.final_score)) - expected) > Decimal("0.009"):
            findings.append(
                _finding(
                    "duplicate_late_penalty",
                    "grade",
                    grade.id,
                    "Final score does not equal raw score minus the recorded late penalty (penalty applied more than once)",
                )
            )
    return findings


def _appeal_without_audit(db: Session) -> list[dict]:
    findings = []
    audits = list(db.scalars(select(AuditEvent)).all())
    grade_audits = {(a.entity_type, a.entity_id, a.action) for a in audits}
    for appeal in db.scalars(select(Appeal)).all():
        if appeal.decision == "approved" and appeal.resulting_grade_id:
            if ("grade", appeal.resulting_grade_id, "revise") not in grade_audits and (
                "grade",
                appeal.resulting_grade_id,
                "grade",
            ) not in grade_audits:
                findings.append(
                    _finding(
                        "appeal_grade_change_without_audit",
                        "appeal",
                        appeal.id,
                        "Approved appeal changed a grade without an audit event",
                    )
                )
    return findings


def _deadline_flags(db: Session) -> list[dict]:
    findings = []
    assignments = {a.id: a for a in db.scalars(select(Assignment)).all()}
    for submission in db.scalars(select(Submission)).all():
        assignment = assignments.get(submission.assignment_id)
        if not assignment or not assignment.due_at:
            continue
        late = as_utc(submission.submitted_at) > as_utc(assignment.due_at)
        if bool(submission.is_late) != bool(late):
            findings.append(
                _finding("deadline_mismatch", "submission", submission.id, "is_late does not match due date")
            )
    return findings


def _lifecycle_sanity(db: Session) -> list[dict]:
    findings = []
    for assignment in db.scalars(select(Assignment)).all():
        if assignment.status not in ASSIGNMENT_TRANSITIONS:
            findings.append(_finding("invalid_enum", "assignment", assignment.id, assignment.status))
    return findings


def _finding(issue_type: str, entity_type: str, entity_id: int, explanation: str) -> dict:
    return {
        "issue_type": issue_type,
        "affected_entity_type": entity_type,
        "affected_entity_id": entity_id,
        "explanation": explanation,
        "source": "detector",
    }


def compare_to_ground_truth(findings: list[dict], labels: list[dict]) -> dict:
    detected = {(f["issue_type"], str(f["affected_entity_id"])) for f in findings}
    actual = {
        (row["issue_type"], str(row["affected_entity_id"]))
        for row in labels
        if row.get("ground_truth") == "anomaly"
    }
    tp = len(detected & actual)
    fp = len(detected - actual)
    fn = len(actual - detected)
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": None},
    }


def write_validation_report(report: dict) -> Path:
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    path = docs / "validation-summary.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md = ROOT / "docs" / "validation-summary.md"
    md.write_text(
        f"# Validation summary\n\nStatus: **{report['status']}**\n\nAnomalies: {report['anomaly_count']}\n",
        encoding="utf-8",
    )
    return path
