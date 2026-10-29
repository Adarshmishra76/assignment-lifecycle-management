from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.academic import AppealCreate, AppealDecision, AppealOut
from app.schemas.common import Paginated
from app.services.appeal_service import create_appeal, decide_appeal, list_appeals, start_review

router = APIRouter(prefix="/appeals", tags=["appeals"])


@router.get("", response_model=Paginated[AppealOut])
def get_appeals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = list_appeals(db, user, page, page_size)
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=AppealOut)
def post_appeal(payload: AppealCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return create_appeal(db, payload, user)


@router.post("/{appeal_id}/review", response_model=AppealOut)
def post_review(appeal_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return start_review(db, appeal_id, user)


@router.post("/{appeal_id}/decision", response_model=AppealOut)
def post_decision(
    appeal_id: int,
    payload: AppealDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return decide_appeal(db, appeal_id, payload, user)
