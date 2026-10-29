from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("submission_id", "revision_number", name="uq_grade_submission_revision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    assignment_version_id: Mapped[int] = mapped_column(ForeignKey("assignment_versions.id"))
    rubric_id: Mapped[int] = mapped_column(ForeignKey("rubrics.id"))
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    raw_score: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    late_penalty_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    late_penalty_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    final_score: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(32), default="posted")
    grader_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    submission: Mapped["Submission"] = relationship(back_populates="grades")
    scores: Mapped[list["RubricScore"]] = relationship(back_populates="grade", cascade="all, delete-orphan")
    feedback_items: Mapped[list["Feedback"]] = relationship(back_populates="grade")
    revisions: Mapped[list["GradeRevision"]] = relationship(back_populates="grade")
    penalties: Mapped[list["GradePenalty"]] = relationship(back_populates="grade", cascade="all, delete-orphan")


class GradePenalty(Base):
    __tablename__ = "grade_penalties"
    __table_args__ = (
        UniqueConstraint("submission_id", "penalty_type", name="uq_penalty_once_per_submission"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id", ondelete="CASCADE"), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    penalty_type: Mapped[str] = mapped_column(String(32), default="late")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    grade: Mapped["Grade"] = relationship(back_populates="penalties")


class RubricScore(Base):
    __tablename__ = "rubric_scores"
    __table_args__ = (UniqueConstraint("grade_id", "criterion_id", name="uq_score_grade_criterion"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id", ondelete="CASCADE"), index=True)
    criterion_id: Mapped[int] = mapped_column(ForeignKey("rubric_criteria.id"))
    score: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    grade: Mapped["Grade"] = relationship(back_populates="scores")
    criterion: Mapped["RubricCriterion"] = relationship(back_populates="scores")


class GradeRevision(Base):
    __tablename__ = "grade_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id", ondelete="CASCADE"), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    previous_final_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    new_final_score: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    reason: Mapped[str] = mapped_column(Text)
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    grade: Mapped["Grade"] = relationship(back_populates="revisions")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    grade_id: Mapped[int | None] = mapped_column(ForeignKey("grades.id", ondelete="SET NULL"), nullable=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    grade: Mapped["Grade | None"] = relationship(back_populates="feedback_items")
    submission: Mapped["Submission"] = relationship(back_populates="feedback_items")
