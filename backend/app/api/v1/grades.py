from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.core.exceptions import ConflictError, NotFoundError
from app.models.course import Course
from app.models.grading import Grade
from app.models.submission import Submission
from app.schemas.academic import FeedbackOut, GradeCreate, GradeOut, GradeReviseRequest, GradeRevisionOut
from app.services.access import require_can_grade
from app.services.submission_service import get_submission
from app.services.grading_service import (
    create_grade,
    get_grade,
    list_feedback,
    list_grades_for_submission,
    list_revisions,
    revise_grade,
)

router = APIRouter(tags=["grades"])


@router.post("/grades", response_model=GradeOut)
def post_grade(payload: GradeCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return create_grade(db, payload, user)


@router.get("/grades/{grade_id}", response_model=GradeOut)
def get_one_grade(grade_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_grade(db, grade_id, user)


@router.post("/grades/{grade_id}/revise", response_model=GradeOut)
def post_revise_grade(
    grade_id: int,
    payload: GradeReviseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current = db.get(Grade, grade_id)
    if not current:
        raise NotFoundError("Grade not found")
    if not current.is_current:
        raise ConflictError("Only the current grade can be revised")
    submission = db.get(Submission, current.submission_id)
    course = db.get(Course, submission.assignment.course_id)
    require_can_grade(db, user, course)
    new_grade = revise_grade(db, current, payload.scores, payload.reason, user, payload.feedback)
    db.commit()
    return get_grade(db, new_grade.id, user)


@router.get("/submissions/{submission_id}/grades", response_model=list[GradeOut])
def get_submission_grades(submission_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_submission(db, submission_id, user)  # 404 if missing, 403 if the caller may not see it
    return list_grades_for_submission(db, submission_id)


@router.get("/submissions/{submission_id}/feedback", response_model=list[FeedbackOut])
def get_feedback(submission_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_submission(db, submission_id, user)
    return list_feedback(db, submission_id)


@router.get("/submissions/{submission_id}/revisions", response_model=list[GradeRevisionOut])
def get_revisions(submission_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_submission(db, submission_id, user)
    return list_revisions(db, submission_id)
