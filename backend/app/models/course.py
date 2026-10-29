from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    term: Mapped[str] = mapped_column(String(32))
    instructor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    instructor: Mapped["User"] = relationship(back_populates="courses_taught")
    enrollments: Mapped[list["CourseEnrollment"]] = relationship(back_populates="course")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="course")


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (UniqueConstraint("course_id", "learner_id", name="uq_enrollment_course_learner"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="enrolled")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    course: Mapped["Course"] = relationship(back_populates="enrollments")
    learner: Mapped["Learner"] = relationship(back_populates="enrollments")
