from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.academic import (
    AssignmentCreate,
    AssignmentOut,
    AssignmentUpdate,
    AssignmentVersionOut,
    RubricCreate,
    RubricOut,
)
from app.schemas.common import Paginated
from app.services.assignment_service import (
    create_assignment,
    get_assignment,
    get_rubric,
    list_assignments,
    list_versions,
    publish_assignment,
    update_assignment,
    upsert_rubric,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.get("", response_model=Paginated[AssignmentOut])
def get_assignments(
    course_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = list_assignments(db, course_id, page, page_size, user)
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=AssignmentOut)
def post_assignment(payload: AssignmentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return create_assignment(db, payload, user)


@router.patch("/{assignment_id}", response_model=AssignmentOut)
def patch_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return update_assignment(db, assignment_id, payload, user)


@router.post("/{assignment_id}/publish", response_model=AssignmentOut)
def post_publish(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return publish_assignment(db, assignment_id, user)


@router.get("/{assignment_id}/versions", response_model=list[AssignmentVersionOut])
def get_versions(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list_versions(db, assignment_id)


@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_one_assignment(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_assignment(db, assignment_id, user)


@router.post("/rubrics", response_model=RubricOut)
def post_rubric(payload: RubricCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return upsert_rubric(db, payload, user)


@router.get("/{assignment_id}/rubric", response_model=RubricOut)
def get_assignment_rubric(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_rubric(db, assignment_id)
