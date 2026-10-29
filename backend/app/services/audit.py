import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.ids import next_public_id
from app.models.audit import AuditEvent


def record_audit(
    db: Session,
    *,
    actor_id: int | None,
    entity_type: str,
    entity_id: int,
    action: str,
    from_state: str | None = None,
    to_state: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        public_id=next_public_id(db, AuditEvent, "AUD", 8),
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        from_state=from_state,
        to_state=to_state,
        payload=json.dumps(payload) if payload else None,
    )
    db.add(event)
    db.flush()
    return event
