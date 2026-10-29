from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.academic import CourseCreate, CourseOut, CourseUpdate, EnrollmentCreate, EnrollmentOut
from app.schemas.common import Paginated
from app.services.course_service import create_course, enroll, list_courses, list_enrollments, update_course

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=Paginated[CourseOut])
def get_courses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = list_courses(db, page, page_size, user)
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=CourseOut)
def post_course(payload: CourseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return create_course(db, payload, user)


@router.patch("/{course_id}", response_model=CourseOut)
def patch_course(
    course_id: int,
    payload: CourseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return update_course(db, course_id, payload, user)


@router.post("/enrollments", response_model=EnrollmentOut)
def post_enrollment(
    payload: EnrollmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return enroll(db, payload, user)


@router.get("/enrollments", response_model=Paginated[EnrollmentOut])
def get_enrollments(
    course_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = list_enrollments(db, course_id, page, page_size)
    return Paginated(items=items, total=total, page=page, page_size=page_size)
