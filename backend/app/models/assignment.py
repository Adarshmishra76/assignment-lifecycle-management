from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignment_versions.id", use_alter=True, name="fk_assignment_current_version"),
        nullable=True,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allow_late: Mapped[bool] = mapped_column(default=True)
    late_penalty_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10.00"))
    max_resubmissions: Mapped[int] = mapped_column(Integer, default=1)
    resubmission_policy: Mapped[str] = mapped_column(String(32), default="instructor_approval")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    course: Mapped["Course"] = relationship(back_populates="assignments")
    versions: Mapped[list["AssignmentVersion"]] = relationship(
        back_populates="assignment",
        foreign_keys="AssignmentVersion.assignment_id",
    )
    current_version: Mapped["AssignmentVersion | None"] = relationship(
        foreign_keys="Assignment.current_version_id",
        post_update=True,
    )
    rubric: Mapped["Rubric | None"] = relationship(back_populates="assignment", uselist=False)
    submissions: Mapped[list["Submission"]] = relationship(back_populates="assignment")


class AssignmentVersion(Base):
    __tablename__ = "assignment_versions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "version_number", name="uq_assignment_version_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    rubric_id: Mapped[int | None] = mapped_column(ForeignKey("rubrics.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignment: Mapped["Assignment"] = relationship(
        back_populates="versions",
        foreign_keys=[assignment_id],
    )
    rubric: Mapped["Rubric | None"] = relationship(foreign_keys=[rubric_id])
