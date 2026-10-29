from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "learner_id",
            "version_number",
            name="uq_submission_assignment_learner_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), index=True)
    assignment_version_id: Mapped[int] = mapped_column(ForeignKey("assignment_versions.id"))
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="submitted", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    assignment_version: Mapped["AssignmentVersion"] = relationship()
    learner: Mapped["Learner"] = relationship(back_populates="submissions")
    artifacts: Mapped[list["SubmissionArtifact"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
    )
    grades: Mapped[list["Grade"]] = relationship(back_populates="submission")
    feedback_items: Mapped[list["Feedback"]] = relationship(back_populates="submission")


class SubmissionArtifact(Base):
    __tablename__ = "submission_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    availability_status: Mapped[str] = mapped_column(String(32), default="available")

    submission: Mapped["Submission"] = relationship(back_populates="artifacts")
