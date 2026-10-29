from sqlalchemy import func, select
from sqlalchemy.orm import Session


def next_public_id(db: Session, model, prefix: str, width: int = 6) -> str:
    """Return the next sequential public id (e.g. CRT-0000004).

    Pending objects are flushed first so several ids requested in a row do not
    collide, and the highest existing number is used (not the row count) so ids
    stay unique after rows are deleted.
    """
    db.flush()
    start = len(prefix) + 2  # SQL substr is 1-indexed; skip "PREFIX-"
    highest = db.scalar(
        select(func.max(func.cast(func.substr(model.public_id, start), type_=__import__("sqlalchemy").Integer))).where(
            model.public_id.like(f"{prefix}-%")
        )
    )
    return f"{prefix}-{(highest or 0) + 1:0{width}d}"
