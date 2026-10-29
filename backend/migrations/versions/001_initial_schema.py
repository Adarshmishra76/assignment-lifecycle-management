"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-10-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_public_id", "users", ["public_id"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "learners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("student_number", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_learners_public_id", "learners", ["public_id"], unique=True)
    op.create_index("ix_learners_student_number", "learners", ["student_number"], unique=True)

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("term", sa.String(32), nullable=False),
        sa.Column("instructor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_courses_public_id", "courses", ["public_id"], unique=True)
    op.create_index("ix_courses_code", "courses", ["code"], unique=True)
    op.create_index("ix_courses_status", "courses", ["status"])

    op.create_table(
        "course_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learner_id", sa.Integer(), sa.ForeignKey("learners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="enrolled"),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("course_id", "learner_id", name="uq_enrollment_course_learner"),
    )
    op.create_index("ix_enrollments_public_id", "course_enrollments", ["public_id"], unique=True)

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("allow_late", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("late_penalty_percent", sa.Numeric(5, 2), nullable=False, server_default="10.00"),
        sa.Column("max_resubmissions", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("resubmission_policy", sa.String(32), nullable=False, server_default="instructor_approval"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assignments_public_id", "assignments", ["public_id"], unique=True)

    op.create_table(
        "rubrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_score", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rubrics_public_id", "rubrics", ["public_id"], unique=True)

    op.create_table(
        "rubric_criteria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("rubric_id", sa.Integer(), sa.ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("max_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("weight", sa.Numeric(6, 3), nullable=False, server_default="1.000"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("rubric_id", "name", name="uq_criterion_name_per_rubric"),
    )
    op.create_index("ix_criteria_public_id", "rubric_criteria", ["public_id"], unique=True)

    op.create_table(
        "assignment_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rubric_id", sa.Integer(), sa.ForeignKey("rubrics.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("assignment_id", "version_number", name="uq_assignment_version_number"),
    )
    op.create_index("ix_assignment_versions_public_id", "assignment_versions", ["public_id"], unique=True)
    # batch mode: SQLite cannot ALTER constraints in place (copy-and-move instead)
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.create_foreign_key(
            "fk_assignment_current_version",
            "assignment_versions",
            ["current_version_id"],
            ["id"],
        )

    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assignment_version_id", sa.Integer(), sa.ForeignKey("assignment_versions.id"), nullable=False),
        sa.Column("learner_id", sa.Integer(), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_late", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("assignment_id", "learner_id", "version_number", name="uq_submission_assignment_learner_version"),
    )
    op.create_index("ix_submissions_public_id", "submissions", ["public_id"], unique=True)

    op.create_table(
        "submission_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("availability_status", sa.String(32), nullable=False, server_default="available"),
    )
    op.create_index("ix_artifacts_public_id", "submission_artifacts", ["public_id"], unique=True)

    op.create_table(
        "grades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assignment_version_id", sa.Integer(), sa.ForeignKey("assignment_versions.id"), nullable=False),
        sa.Column("rubric_id", sa.Integer(), sa.ForeignKey("rubrics.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("raw_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("late_penalty_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("late_penalty_amount", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("final_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="posted"),
        sa.Column("grader_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("submission_id", "revision_number", name="uq_grade_submission_revision"),
    )
    op.create_index("ix_grades_public_id", "grades", ["public_id"], unique=True)

    op.create_table(
        "grade_penalties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("penalty_type", sa.String(32), nullable=False, server_default="late"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("submission_id", "penalty_type", name="uq_penalty_once_per_submission"),
    )

    op.create_table(
        "rubric_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("criterion_id", sa.Integer(), sa.ForeignKey("rubric_criteria.id"), nullable=False),
        sa.Column("score", sa.Numeric(10, 2), nullable=False),
        sa.UniqueConstraint("grade_id", "criterion_id", name="uq_score_grade_criterion"),
    )
    op.create_index("ix_rubric_scores_public_id", "rubric_scores", ["public_id"], unique=True)

    op.create_table(
        "grade_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_final_score", sa.Numeric(10, 2), nullable=True),
        sa.Column("new_final_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_grade_revisions_public_id", "grade_revisions", ["public_id"], unique=True)

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feedback_public_id", "feedback", ["public_id"], unique=True)

    op.create_table(
        "resubmissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learner_id", sa.Integer(), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("previous_submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("resulting_submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="requested"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_resubmissions_public_id", "resubmissions", ["public_id"], unique=True)

    op.create_table(
        "appeals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.id"), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("learner_id", sa.Integer(), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_refs", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="submitted"),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decision", sa.String(32), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resulting_grade_id", sa.Integer(), sa.ForeignKey("grades.id"), nullable=True),
        sa.UniqueConstraint("grade_id", "learner_id", name="uq_appeal_grade_learner"),
    )
    op.create_index("ix_appeals_public_id", "appeals", ["public_id"], unique=True)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=True),
        sa.Column("to_state", sa.String(32), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_public_id", "audit_events", ["public_id"], unique=True)
    op.create_index("ix_audit_entity", "audit_events", ["entity_type", "entity_id"])


def downgrade() -> None:
    for table in [
        "audit_events",
        "appeals",
        "resubmissions",
        "feedback",
        "grade_revisions",
        "rubric_scores",
        "grade_penalties",
        "grades",
        "submission_artifacts",
        "submissions",
        "assignment_versions",
        "rubric_criteria",
        "rubrics",
        "assignments",
        "course_enrollments",
        "courses",
        "learners",
        "users",
    ]:
        op.drop_table(table)
