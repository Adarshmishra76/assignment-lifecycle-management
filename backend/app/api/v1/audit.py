from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.academic import AuditOut
from app.schemas.common import Paginated

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=Paginated[AuditOut])
def get_audit(
    entity_type: str | None = None,
    entity_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("instructor", "academic_admin", "support_staff", "platform_admin")),
):
    stmt = select(AuditEvent)
    count_stmt = select(func.count()).select_from(AuditEvent)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
        count_stmt = count_stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
        count_stmt = count_stmt.where(AuditEvent.entity_id == entity_id)
    total = db.scalar(count_stmt) or 0
    items = db.scalars(
        stmt.order_by(AuditEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Paginated(items=items, total=total, page=page, page_size=page_size)
