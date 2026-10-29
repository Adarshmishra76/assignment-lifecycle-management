from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.academic import ResubmissionCreate, ResubmissionDecision, ResubmissionOut, SubmissionCreate
from app.schemas.common import Paginated
from app.services.resubmission_service import complete_resubmission, decide_resubmission, list_resubmissions, request_resubmission

router = APIRouter(prefix="/resubmissions", tags=["resubmissions"])


@router.get("", response_model=Paginated[ResubmissionOut])
def get_resubmissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = list_resubmissions(db, user, page, page_size)
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ResubmissionOut)
def post_resubmission(
    payload: ResubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return request_resubmission(db, payload, user)


@router.post("/{resubmission_id}/decision", response_model=ResubmissionOut)
def post_decision(
    resubmission_id: int,
    payload: ResubmissionDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return decide_resubmission(db, resubmission_id, payload, user)


@router.post("/{resubmission_id}/submit", response_model=ResubmissionOut)
def post_complete(
    resubmission_id: int,
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return complete_resubmission(db, resubmission_id, payload, user)
