from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Rubric(Base):
    __tablename__ = "rubrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    max_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignment: Mapped["Assignment"] = relationship(back_populates="rubric")
    criteria: Mapped[list["RubricCriterion"]] = relationship(
        back_populates="rubric",
        cascade="all, delete-orphan",
        order_by="RubricCriterion.sort_order",
    )


class RubricCriterion(Base):
    __tablename__ = "rubric_criteria"
    __table_args__ = (UniqueConstraint("rubric_id", "name", name="uq_criterion_name_per_rubric"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    rubric_id: Mapped[int] = mapped_column(ForeignKey("rubrics.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_score: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("1.000"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    rubric: Mapped["Rubric"] = relationship(back_populates="criteria")
    scores: Mapped[list["RubricScore"]] = relationship(back_populates="criterion")
