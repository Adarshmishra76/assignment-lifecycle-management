from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Resubmission(Base):
    __tablename__ = "resubmissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), index=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    previous_submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    resulting_submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="requested", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Appeal(Base):
    __tablename__ = "appeals"
    __table_args__ = (
        UniqueConstraint("grade_id", "learner_id", name="uq_appeal_grade_learner"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    evidence_refs: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="submitted", index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resulting_grade_id: Mapped[int | None] = mapped_column(ForeignKey("grades.id"), nullable=True)
