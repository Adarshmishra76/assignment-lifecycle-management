from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.academic import SubmissionCreate, SubmissionOut
from app.schemas.common import Paginated
from app.services.submission_service import create_submission, get_submission, list_submissions

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.get("", response_model=Paginated[SubmissionOut])
def get_submissions(
    assignment_id: int | None = None,
    learner_id: int | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = list_submissions(db, user, assignment_id, learner_id, page, page_size, status)
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=SubmissionOut)
def post_submission(payload: SubmissionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return create_submission(db, payload, user)


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_one(submission_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_submission(db, submission_id, user)
