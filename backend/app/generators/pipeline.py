from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from app.core.lifecycle import apply_late_penalty, round_score
from app.core.security import hash_password
from app.generators.checksums import file_checksum, logical_checksum
from app.generators.config import SEED, resolve_config
from app.models import (
    Appeal,
    Assignment,
    AssignmentVersion,
    AuditEvent,
    Course,
    CourseEnrollment,
    Feedback,
    Grade,
    GradePenalty,
    GradeRevision,
    Learner,
    Resubmission,
    Rubric,
    RubricCriterion,
    RubricScore,
    Submission,
    SubmissionArtifact,
    User,
)
from app.validators.ground_truth import write_ground_truth_templates

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
PASSWORD = "DemoPass123!"


def _pid(prefix: str, index: int, width: int = 6) -> str:
    return f"{prefix}-{index:0{width}d}"


def _clear(db: Session) -> None:
    # assignments.current_version_id points at versions, and versions point at rubrics, so
    # detach the cycle first and delete versions before the rubrics they reference.
    db.execute(update(Assignment).values(current_version_id=None))
    for model in (
        AuditEvent,
        Appeal,
        Resubmission,
        Feedback,
        GradeRevision,
        RubricScore,
        GradePenalty,
        Grade,
        SubmissionArtifact,
        Submission,
        AssignmentVersion,
        RubricCriterion,
        Rubric,
        Assignment,
        CourseEnrollment,
        Learner,
        Course,
        User,
    ):
        db.execute(delete(model))
    db.commit()


def _inject_anomalies(
    db: Session,
    *,
    grades,
    appeals,
    resubmissions,
    submissions,
    learners,
    course_learners,
    assignment_by_id,
    submission_by_id,
    penalty_by_submission,
) -> list[dict]:
    """Plant the four required anomalies in otherwise clean data and return their real ids.

    Choices are made by walking rows in id order, so the result is fixed by the seed alone.
    Rows that take part in appeals or resubmissions are left alone to keep each anomaly isolated.
    """
    appealed = {a.grade_id for a in appeals}
    appealed_submissions = {a.submission_id for a in appeals}
    previous = {r.previous_submission_id for r in resubmissions}
    pool = [
        g
        for g in sorted(grades, key=lambda g: g.id)
        if g.is_current and g.id not in appealed and g.submission_id not in previous
    ]
    found: dict[str, dict] = {}

    # 1. grade_exceeds_rubric_max: raw score above the rubric maximum (100)
    over = next((g for g in pool if not g.late_penalty_applied), None)
    if over:
        over.raw_score = Decimal("115.00")
        over.final_score = Decimal("115.00")
        found["grade_exceeds_rubric_max"] = {"affected_entity_type": "grade", "affected_entity_id": over.id}

    # 2. duplicate_late_penalty: the penalty is taken off the final score twice
    dup = next((g for g in pool if g is not over and g.late_penalty_applied), None) or next(
        (g for g in pool if g is not over), None
    )
    if dup:
        sub = submission_by_id[dup.submission_id]
        assignment = assignment_by_id[sub.assignment_id]
        if not dup.late_penalty_applied:
            sub.is_late = True
            sub.submitted_at = assignment.due_at + timedelta(hours=6)
            amount, _ = apply_late_penalty(dup.raw_score, assignment.late_penalty_percent)
            dup.late_penalty_applied = True
            dup.late_penalty_amount = amount
            db.add(GradePenalty(grade_id=dup.id, submission_id=sub.id, penalty_type="late", amount=amount))
        dup.final_score = round_score(max(Decimal("0.00"), dup.raw_score - 2 * dup.late_penalty_amount))
        found["duplicate_late_penalty"] = {"affected_entity_type": "grade", "affected_entity_id": dup.id}

    # 3. unenrolled_submission: a first attempt filed under a learner who is not in the course
    skip = {g.submission_id for g in (over, dup) if g}
    taken = {(s.assignment_id, s.learner_id) for s in submissions}
    for sub in sorted(submissions, key=lambda s: s.id):
        if sub.version_number != 1 or sub.id in previous | appealed_submissions | skip:
            continue
        enrolled = set(course_learners[assignment_by_id[sub.assignment_id].course_id])
        outsider = next((l for l in learners if l.id not in enrolled and (sub.assignment_id, l.id) not in taken), None)
        if outsider:
            sub.learner_id = outsider.id
            found["unenrolled_submission"] = {"affected_entity_type": "submission", "affected_entity_id": sub.id}
            break

    # 4. appeal_grade_change_without_audit: the last approved appeal (its audit event is skipped later)
    approved = [a for a in appeals if a.decision == "approved" and a.resulting_grade_id]
    if approved:
        found["appeal_grade_change_without_audit"] = {
            "affected_entity_type": "appeal",
            "affected_entity_id": approved[-1].id,
        }

    db.flush()
    order = [
        "unenrolled_submission",
        "grade_exceeds_rubric_max",
        "duplicate_late_penalty",
        "appeal_grade_change_without_audit",
    ]
    return [{"issue_type": key, **found[key]} for key in order if key in found]


def generate_dataset(db: Session, mode: str = "starter", seed: int = SEED, force: bool = False, export: bool = True) -> dict:
    cfg = resolve_config(mode, seed)
    existing = db.scalar(select(func.count()).select_from(Assignment)) or 0
    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    # A lone user is the bootstrap admin created at app startup; the generator
    # recreates that account, so it is safe to clear without force.
    if (existing or user_count > 1) and not force:
        raise ValueError("Database is not empty. Re-run with force=True to regenerate safely.")
    if existing or user_count:
        _clear(db)

    faker = Faker()
    faker.seed_instance(seed)
    rng = np.random.default_rng(seed)
    password_hash = hash_password(PASSWORD)
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)

    users: list[User] = []
    admin = User(
        public_id=_pid("USR", 1),
        email="admin@demo.local",
        password_hash=password_hash,
        full_name="Platform Administrator",
        role="platform_admin",
        created_at=origin,
        updated_at=origin,
    )
    users.append(admin)
    academic = User(
        public_id=_pid("USR", 2),
        email="academic@demo.local",
        password_hash=password_hash,
        full_name="Academic Administrator",
        role="academic_admin",
        created_at=origin,
        updated_at=origin,
    )
    users.append(academic)
    support = User(
        public_id=_pid("USR", 3),
        email="support@demo.local",
        password_hash=password_hash,
        full_name="Support Staff",
        role="support_staff",
        created_at=origin,
        updated_at=origin,
    )
    users.append(support)
    instructors: list[User] = []
    for i in range(cfg.instructors):
        user = User(
            public_id=_pid("USR", 4 + i),
            email=f"instructor{i + 1:04d}@demo.local",
            password_hash=password_hash,
            full_name=faker.name(),
            role="instructor",
            created_at=origin,
            updated_at=origin,
        )
        instructors.append(user)
        users.append(user)
    db.add_all(users)
    db.flush()

    learners: list[Learner] = []
    learner_users: list[User] = []
    for i in range(cfg.learners):
        user = User(
            public_id=_pid("USR", 4 + cfg.instructors + i, 7),
            email=f"learner{i + 1:07d}@demo.local",
            password_hash=password_hash,
            full_name=faker.name(),
            role="learner",
            created_at=origin,
            updated_at=origin,
        )
        learner_users.append(user)
    db.add_all(learner_users)
    db.flush()
    for i, user in enumerate(learner_users, start=1):
        learners.append(
            Learner(
                public_id=_pid("LRN", i, 7),
                user_id=user.id,
                student_number=_pid("STU", i, 7),
                created_at=origin,
            )
        )
    db.add_all(learners)
    db.flush()

    courses: list[Course] = []
    for i in range(cfg.courses):
        instructor = instructors[i % len(instructors)]
        courses.append(
            Course(
                public_id=_pid("CRS", i + 1),
                code=f"CS{i + 1:04d}",
                title=f"Course {i + 1:04d}",
                description="Synthetic course",
                term="2026-Fall",
                instructor_id=instructor.id,
                status="active",
                created_at=origin,
                updated_at=origin,
            )
        )
    db.add_all(courses)
    db.flush()

    enrollments: list[CourseEnrollment] = []
    enroll_n = 2 if cfg.mode == "starter" else 3
    counter = 1
    course_learners: dict[int, list[int]] = defaultdict(list)
    for learner in learners:
        chosen = [courses[(learner.id + offset) % len(courses)] for offset in range(enroll_n)]
        seen = set()
        for course in chosen:
            if course.id in seen:
                continue
            seen.add(course.id)
            enrollments.append(
                CourseEnrollment(
                    public_id=_pid("ENR", counter, 7),
                    course_id=course.id,
                    learner_id=learner.id,
                    status="enrolled",
                    enrolled_at=origin,
                )
            )
            course_learners[course.id].append(learner.id)
            counter += 1
    db.add_all(enrollments)
    db.flush()

    assignments: list[Assignment] = []
    for i in range(cfg.assignments):
        course = courses[i % len(courses)]
        due = origin + timedelta(days=30 + int(rng.integers(0, 20)))
        assignments.append(
            Assignment(
                public_id=_pid("ASN", i + 1),
                course_id=course.id,
                title=f"Assignment {i + 1:04d}",
                description="Synthetic assignment",
                status="published",
                due_at=due,
                published_at=origin + timedelta(days=1),
                allow_late=True,
                late_penalty_percent=Decimal("10.00"),
                max_resubmissions=1,
                resubmission_policy="instructor_approval",
                created_by_id=course.instructor_id,
                created_at=origin,
                updated_at=origin,
            )
        )
    db.add_all(assignments)
    db.flush()

    rubrics: list[Rubric] = []
    criteria: list[RubricCriterion] = []
    crit_i = 1
    for i, assignment in enumerate(assignments, start=1):
        max_score = Decimal("100.00")
        rubrics.append(
            Rubric(
                public_id=_pid("RUB", i),
                assignment_id=assignment.id,
                name=f"Rubric {i:04d}",
                version_number=1,
                max_score=max_score,
                created_at=origin,
            )
        )
    db.add_all(rubrics)
    db.flush()
    for rubric in rubrics:
        piece = round_score(rubric.max_score / cfg.criteria_per_rubric)
        remainder = rubric.max_score
        for c in range(cfg.criteria_per_rubric):
            score = remainder if c == cfg.criteria_per_rubric - 1 else piece
            remainder -= piece
            criteria.append(
                RubricCriterion(
                    public_id=_pid("CRT", crit_i, 7),
                    rubric_id=rubric.id,
                    name=f"Criterion {c + 1}",
                    description="Quality of work",
                    max_score=score,
                    weight=Decimal("1.000"),
                    sort_order=c,
                )
            )
            crit_i += 1
    db.add_all(criteria)
    db.flush()
    rubric_by_assignment = {r.assignment_id: r for r in rubrics}
    criteria_by_rubric: dict[int, list[RubricCriterion]] = defaultdict(list)
    for criterion in criteria:
        criteria_by_rubric[criterion.rubric_id].append(criterion)

    versions: list[AssignmentVersion] = []
    for i, assignment in enumerate(assignments, start=1):
        rubric = rubric_by_assignment[assignment.id]
        versions.append(
            AssignmentVersion(
                public_id=_pid("ASV", i),
                assignment_id=assignment.id,
                version_number=1,
                title=assignment.title,
                description=assignment.description,
                due_at=assignment.due_at,
                published_at=assignment.published_at,
                rubric_id=rubric.id,
                created_at=origin,
            )
        )
    db.add_all(versions)
    db.flush()
    version_by_assignment = {v.assignment_id: v for v in versions}
    for assignment in assignments:
        assignment.current_version_id = version_by_assignment[assignment.id].id
    db.flush()

    assignment_by_id = {a.id: a for a in assignments}
    pairs: list[tuple[Assignment, int]] = []
    for assignment in assignments:
        eligible = course_learners[assignment.course_id]
        for learner_id in eligible:
            pairs.append((assignment, learner_id))
    rng.shuffle(pairs)
    # Resubmissions are part of the target, so first attempts make up the remainder.
    resub_count = max(1, int(cfg.target_submissions * 0.05))
    pairs = pairs[: cfg.target_submissions - resub_count]

    submissions: list[Submission] = []
    artifacts: list[SubmissionArtifact] = []
    for i, (assignment, learner_id) in enumerate(pairs, start=1):
        late_roll = float(rng.random())
        is_late = late_roll < 0.15
        submitted_at = assignment.due_at + timedelta(hours=6) if is_late else assignment.due_at - timedelta(days=1)
        missing = float(rng.random()) < 0.05
        submissions.append(
            Submission(
                public_id=_pid("SUB", i, 7),
                assignment_id=assignment.id,
                assignment_version_id=version_by_assignment[assignment.id].id,
                learner_id=learner_id,
                version_number=1,
                submitted_at=submitted_at,
                is_late=is_late,
                status="submitted",
                created_at=origin,
            )
        )
    db.add_all(submissions)
    db.flush()
    for i, submission in enumerate(submissions, start=1):
        missing = float(rng.random()) < 0.05
        payload = f"{submission.public_id}-artifact".encode()
        artifacts.append(
            SubmissionArtifact(
                public_id=_pid("ART", i, 7),
                submission_id=submission.id,
                filename=f"{submission.public_id}.pdf",
                mime_type="application/pdf",
                file_size_bytes=int(rng.integers(10_000, 400_000)),
                checksum_sha256=hashlib.sha256(payload).hexdigest(),
                uploaded_at=submission.submitted_at,
                availability_status="missing" if missing else "available",
            )
        )
    db.add_all(artifacts)
    db.flush()

    grades: list[Grade] = []
    scores: list[RubricScore] = []
    penalties: list[GradePenalty] = []
    revisions: list[GradeRevision] = []
    feedback_rows: list[Feedback] = []
    score_i = 1
    grade_i = 1
    for submission in submissions:
        if float(rng.random()) < 0.2:
            continue
        assignment = assignment_by_id[submission.assignment_id]
        rubric = rubric_by_assignment[assignment.id]
        crits = criteria_by_rubric[rubric.id]
        raw = Decimal("0.00")
        criterion_scores = []
        for criterion in crits:
            frac = Decimal(str(round(float(rng.uniform(0.55, 0.98)), 4)))
            value = round_score(criterion.max_score * frac)
            criterion_scores.append((criterion, value))
            raw += value
        raw = round_score(raw)
        apply_penalty = submission.is_late
        late_amount = Decimal("0.00")
        final = raw
        if apply_penalty:
            late_amount, final = apply_late_penalty(raw, assignment.late_penalty_percent)
        instructor_id = assignment.created_by_id
        grade = Grade(
            public_id=_pid("GRD", grade_i),
            submission_id=submission.id,
            assignment_version_id=submission.assignment_version_id,
            rubric_id=rubric.id,
            revision_number=1,
            is_current=True,
            raw_score=raw,
            late_penalty_applied=apply_penalty,
            late_penalty_amount=late_amount,
            final_score=final,
            status="posted",
            grader_id=instructor_id,
            created_at=submission.submitted_at + timedelta(days=2),
        )
        grades.append(grade)
        grade_i += 1
        submission.status = "graded"
    db.add_all(grades)
    db.flush()
    grades_by_submission = {g.submission_id: g for g in grades}
    # rebuild criterion scores now that grade ids exist
    rng2 = np.random.default_rng(seed + 1)
    for submission in submissions:
        grade = grades_by_submission.get(submission.id)
        if not grade:
            continue
        assignment = assignment_by_id[submission.assignment_id]
        rubric = rubric_by_assignment[assignment.id]
        crits = criteria_by_rubric[rubric.id]
        raw = Decimal("0.00")
        for criterion in crits:
            frac = Decimal(str(round(float(rng2.uniform(0.55, 0.98)), 4)))
            value = round_score(criterion.max_score * frac)
            scores.append(
                RubricScore(
                    public_id=_pid("SCR", score_i, 7),
                    grade_id=grade.id,
                    criterion_id=criterion.id,
                    score=value,
                )
            )
            score_i += 1
            raw += value
        raw = round_score(raw)
        apply_penalty = submission.is_late
        late_amount = Decimal("0.00")
        final = raw
        if apply_penalty:
            late_amount, final = apply_late_penalty(raw, assignment.late_penalty_percent)
            penalties.append(
                GradePenalty(
                    grade_id=grade.id,
                    submission_id=submission.id,
                    penalty_type="late",
                    amount=late_amount,
                )
            )
        grade.raw_score = raw
        grade.late_penalty_applied = apply_penalty
        grade.late_penalty_amount = late_amount
        grade.final_score = final
        revisions.append(
            GradeRevision(
                public_id=_pid("GRV", grade.id),
                grade_id=grade.id,
                submission_id=submission.id,
                previous_final_score=None,
                new_final_score=final,
                reason="Initial grade",
                changed_by_id=grade.grader_id,
                created_at=grade.created_at,
            )
        )
        feedback_rows.append(
            Feedback(
                public_id=_pid("FBK", grade.id),
                grade_id=grade.id,
                submission_id=submission.id,
                author_id=grade.grader_id,
                body="Solid work. See rubric comments.",
                created_at=grade.created_at,
            )
        )
    db.add_all(scores)
    db.add_all(penalties)
    db.add_all(revisions)
    db.add_all(feedback_rows)
    db.flush()

    resubmissions: list[Resubmission] = []
    eligible_subs = [s for s in submissions if s.version_number == 1]
    rng.shuffle(eligible_subs)
    resub_count = min(resub_count, len(eligible_subs))
    for i, submission in enumerate(eligible_subs[:resub_count], start=1):
        resubmissions.append(
            Resubmission(
                public_id=_pid("RSB", i),
                assignment_id=submission.assignment_id,
                learner_id=submission.learner_id,
                previous_submission_id=submission.id,
                status="approved",
                requested_at=submission.submitted_at + timedelta(days=3),
                decided_at=submission.submitted_at + timedelta(days=4),
                decided_by_id=assignment_by_id[submission.assignment_id].created_by_id,
                decision_reason="Eligible under policy",
            )
        )
    db.add_all(resubmissions)
    db.flush()

    extra_subs: list[Submission] = []
    sub_n = len(submissions)
    for i, record in enumerate(resubmissions, start=1):
        assignment = assignment_by_id[record.assignment_id]
        extra = Submission(
            public_id=_pid("SUB", sub_n + i, 7),
            assignment_id=record.assignment_id,
            assignment_version_id=version_by_assignment[record.assignment_id].id,
            learner_id=record.learner_id,
            version_number=2,
            submitted_at=record.requested_at + timedelta(days=2),
            is_late=True,
            status="submitted",
            created_at=origin,
        )
        extra_subs.append(extra)
        record.resulting_submission_id = None
        record.status = "completed"
    db.add_all(extra_subs)
    db.flush()
    for record, extra in zip(resubmissions, extra_subs):
        record.resulting_submission_id = extra.id
    submissions.extend(extra_subs)
    submission_by_id = {sub.id: sub for sub in submissions}
    grade_by_id = {g.id: g for g in grades}
    penalty_by_submission = {p.submission_id: p for p in penalties}

    appeals: list[Appeal] = []
    graded = list(grades)
    rng.shuffle(graded)
    # Keep a few graded rows free of appeals: the anomaly injection below needs them.
    appeal_count = min(max(6, int(len(graded) * 0.03)), max(0, len(graded) - 4))
    decisions = ["approved", "rejected", "upheld"]
    for i, grade in enumerate(graded[:appeal_count], start=1):
        decision = decisions[(i - 1) % 3]
        submission = submission_by_id[grade.submission_id]
        appeals.append(
            Appeal(
                public_id=_pid("APL", i),
                grade_id=grade.id,
                submission_id=grade.submission_id,
                learner_id=submission.learner_id,
                reason="Please reconsider criterion 1.",
                evidence_refs="artifact:original",
                status=decision,
                reviewer_id=grade.grader_id,
                decision=decision,
                decision_reason="Reviewed against rubric",
                created_at=grade.created_at + timedelta(days=1),
                decided_at=grade.created_at + timedelta(days=2),
            )
        )
    db.add_all(appeals)
    db.flush()

    # Approved appeals get a preserved revision.
    rev_extra: list[Grade] = []
    for appeal in appeals:
        if appeal.decision != "approved":
            continue
        old = grade_by_id[appeal.grade_id]
        old.is_current = False
        old.status = "superseded"
        new_raw = round_score(min(Decimal("100.00"), old.raw_score + Decimal("2.00")))
        new_amount = Decimal("0.00")
        new_final = new_raw
        if old.late_penalty_applied:
            policy = assignment_by_id[submission_by_id[old.submission_id].assignment_id]
            new_amount, new_final = apply_late_penalty(new_raw, policy.late_penalty_percent)
            penalty_by_submission[old.submission_id].amount = new_amount  # one penalty row, recalculated
        new_grade = Grade(
            public_id=_pid("GRD", grade_i),
            submission_id=old.submission_id,
            assignment_version_id=old.assignment_version_id,
            rubric_id=old.rubric_id,
            revision_number=old.revision_number + 1,
            is_current=True,
            raw_score=new_raw,
            late_penalty_applied=old.late_penalty_applied,
            late_penalty_amount=new_amount,
            final_score=new_final,
            status="revised",
            grader_id=old.grader_id,
            created_at=old.created_at + timedelta(days=3),
        )
        grade_i += 1
        rev_extra.append(new_grade)
        db.add(new_grade)
        db.flush()
        appeal.resulting_grade_id = new_grade.id
        db.add(
            GradeRevision(
                public_id=_pid("GRV", new_grade.id),
                grade_id=new_grade.id,
                submission_id=old.submission_id,
                previous_final_score=old.final_score,
                new_final_score=new_final,
                reason="Appeal approved",
                changed_by_id=old.grader_id,
                created_at=new_grade.created_at,
            )
        )
    db.flush()

    anomalies = _inject_anomalies(
        db,
        grades=grades,
        appeals=appeals,
        resubmissions=resubmissions,
        submissions=submissions,
        learners=learners,
        course_learners=course_learners,
        assignment_by_id=assignment_by_id,
        submission_by_id=submission_by_id,
        penalty_by_submission=penalty_by_submission,
    )
    unaudited = next(
        (a for a in reversed(anomalies) if a["issue_type"] == "appeal_grade_change_without_audit"), None
    )
    unaudited_appeal = next((a for a in appeals if unaudited and a.id == unaudited["affected_entity_id"]), None)
    skipped_grade_id = unaudited_appeal.resulting_grade_id if unaudited_appeal else None

    audits: list[AuditEvent] = []
    audit_i = 1
    def add_audit(entity_type, entity_id, action, to_state=None, actor_id=None):
        nonlocal audit_i
        audits.append(
            AuditEvent(
                public_id=_pid("AUD", audit_i, 8),
                actor_id=actor_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                to_state=to_state,
                created_at=origin,
            )
        )
        audit_i += 1

    for assignment in assignments:
        add_audit("assignment", assignment.id, "publish", "published", assignment.created_by_id)
    for submission in submissions:
        add_audit("submission", submission.id, "submit", "submitted")
    for grade in grades + rev_extra:
        if grade.id == skipped_grade_id:
            continue  # the injected anomaly: a grade change with no audit event
        add_audit("grade", grade.id, "grade" if grade.revision_number == 1 else "revise", grade.status, grade.grader_id)
    for appeal in appeals:
        add_audit("appeal", appeal.id, "decide", appeal.decision, appeal.reviewer_id)
        if appeal.decision == "approved" and appeal.resulting_grade_id and appeal is not unaudited_appeal:
            add_audit("grade", appeal.resulting_grade_id, "revise", "revised", appeal.reviewer_id)
    db.add_all(audits)
    db.commit()

    counts = {
        "users": db.scalar(select(func.count()).select_from(User)),
        "learners": db.scalar(select(func.count()).select_from(Learner)),
        "courses": db.scalar(select(func.count()).select_from(Course)),
        "enrollments": db.scalar(select(func.count()).select_from(CourseEnrollment)),
        "assignments": db.scalar(select(func.count()).select_from(Assignment)),
        "assignment_versions": db.scalar(select(func.count()).select_from(AssignmentVersion)),
        "rubrics": db.scalar(select(func.count()).select_from(Rubric)),
        "rubric_criteria": db.scalar(select(func.count()).select_from(RubricCriterion)),
        "submissions": db.scalar(select(func.count()).select_from(Submission)),
        "artifacts": db.scalar(select(func.count()).select_from(SubmissionArtifact)),
        "grades": db.scalar(select(func.count()).select_from(Grade)),
        "rubric_scores": db.scalar(select(func.count()).select_from(RubricScore)),
        "grade_revisions": db.scalar(select(func.count()).select_from(GradeRevision)),
        "feedback": db.scalar(select(func.count()).select_from(Feedback)),
        "resubmissions": db.scalar(select(func.count()).select_from(Resubmission)),
        "appeals": db.scalar(select(func.count()).select_from(Appeal)),
        "audit_events": db.scalar(select(func.count()).select_from(AuditEvent)),
    }
    result = {"mode": mode, "seed": seed, "counts": counts, "anomalies": anomalies}
    if export:
        result["export"] = export_dataset(db, mode, seed, counts)
        write_ground_truth_templates(DATA / "ground_truth", anomalies)
    return result


ENTITY_QUERIES = {
    "users": User,
    "learners": Learner,
    "courses": Course,
    "enrollments": CourseEnrollment,
    "assignments": Assignment,
    "assignment_versions": AssignmentVersion,
    "rubrics": Rubric,
    "rubric_criteria": RubricCriterion,
    "submissions": Submission,
    "artifacts": SubmissionArtifact,
    "grades": Grade,
    "rubric_scores": RubricScore,
    "grade_revisions": GradeRevision,
    "feedback": Feedback,
    "resubmissions": Resubmission,
    "appeals": Appeal,
    "audit_events": AuditEvent,
}


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return "'" + value.strftime("%Y-%m-%d %H:%M:%S.%f") + "'"
    return "'" + str(value).replace("'", "''") + "'"


def _insert_statements(table: str, rows: list[dict]) -> list[str]:
    statements = []
    for row in rows:
        columns = ", ".join(row)
        values = ", ".join(_sql_literal(v) for v in row.values())
        statements.append(f"INSERT INTO {table} ({columns}) VALUES ({values});")
    return statements


def _row_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def export_dataset(db: Session, mode: str, seed: int, counts: dict) -> dict:
    out_dir = DATA / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    (DATA / "manifests").mkdir(parents=True, exist_ok=True)
    checksums = {}
    sql_lines = [
        "-- Generated seed data (SQLite). Load into a database created from the application schema.",
        "PRAGMA foreign_keys=OFF;",
        "BEGIN;",
    ]
    for name, model in ENTITY_QUERIES.items():
        rows = [_row_dict(obj) for obj in db.scalars(select(model).order_by(model.id)).all()]
        sql_lines.extend(_insert_statements(model.__tablename__, rows))
        frame = pd.DataFrame(rows)
        csv_path = out_dir / f"{name}.csv"
        json_path = out_dir / f"{name}.json"
        frame.to_csv(csv_path, index=False)
        json_path.write_text(json.dumps(rows, default=str, indent=2), encoding="utf-8")
        checksums[name] = {
            "row_count": len(rows),
            "logical_sha256": logical_checksum(rows),
            "csv_sha256": file_checksum(csv_path),
            "json_sha256": file_checksum(json_path),
        }
    sql_path = out_dir / "seed.sql"
    sql_lines.extend(["COMMIT;", "PRAGMA foreign_keys=ON;"])
    sql_path.write_text("\n".join(sql_lines) + "\n", encoding="utf-8")
    manifest = {
        "seed": seed,
        "mode": mode,
        "generated_note": "Logical checksums exclude timestamps and password hashes.",
        "counts": counts,
        "checksums": checksums,
    }
    manifest_path = DATA / "manifests" / f"{mode}_{seed}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return {"directory": str(out_dir), "manifest": str(manifest_path), "checksums": checksums}
