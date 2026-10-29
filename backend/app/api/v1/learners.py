from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.academic import LearnerCreate, LearnerOut
from app.schemas.common import Paginated
from app.services.course_service import create_learner, list_learners

router = APIRouter(prefix="/learners", tags=["learners"])


@router.get("", response_model=Paginated[LearnerOut])
def get_learners(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = list_learners(db, page, page_size, user)
    mapped = []
    for learner in items:
        mapped.append(
            LearnerOut(
                id=learner.id,
                public_id=learner.public_id,
                user_id=learner.user_id,
                student_number=learner.student_number,
                status=learner.status,
                full_name=learner.user.full_name if learner.user else None,
                email=learner.user.email if learner.user else None,
            )
        )
    return Paginated(items=mapped, total=total, page=page, page_size=page_size)


@router.post("", response_model=LearnerOut)
def post_learner(payload: LearnerCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    learner = create_learner(db, payload, user)
    return LearnerOut(
        id=learner.id,
        public_id=learner.public_id,
        user_id=learner.user_id,
        student_number=learner.student_number,
        status=learner.status,
        full_name=payload.full_name,
        email=payload.email,
    )
