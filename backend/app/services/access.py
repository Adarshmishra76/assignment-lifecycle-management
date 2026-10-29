from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.course import Course, CourseEnrollment
from app.models.learner import Learner
from app.models.submission import Submission
from app.models.user import User

ADMIN_ROLES = {"academic_admin", "platform_admin"}
STAFF_ROLES = {"instructor", "academic_admin", "support_staff", "platform_admin"}
GRADE_ROLES = {"instructor", "academic_admin", "platform_admin"}
PUBLISH_ROLES = {"instructor", "academic_admin", "platform_admin"}
APPEAL_REVIEW_ROLES = {"instructor", "academic_admin", "platform_admin"}
ADMIN_ONLY = {"academic_admin", "platform_admin"}
PLATFORM_ONLY = {"platform_admin"}


def learner_profile(db: Session, user: User) -> Learner | None:
    return db.scalar(select(Learner).where(Learner.user_id == user.id))


def require_course_staff(db: Session, user: User, course: Course) -> None:
    if user.role in ADMIN_ROLES:
        return
    if user.role == "instructor" and course.instructor_id == user.id:
        return
    if user.role == "support_staff":
        return
    raise ForbiddenError("Not authorized for this course")


def require_can_grade(db: Session, user: User, course: Course) -> None:
    if user.role in ADMIN_ROLES:
        return
    if user.role == "instructor" and course.instructor_id == user.id:
        return
    raise ForbiddenError("Not authorized to grade")


def require_can_publish(user: User, course: Course) -> None:
    if user.role in ADMIN_ROLES:
        return
    if user.role == "instructor" and course.instructor_id == user.id:
        return
    raise ForbiddenError("Not authorized to publish")


def get_enrollment(db: Session, course_id: int, learner_id: int) -> CourseEnrollment | None:
    return db.scalar(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.learner_id == learner_id,
            CourseEnrollment.status == "enrolled",
        )
    )


def require_submission_access(db: Session, user: User, submission: Submission) -> None:
    if user.role in STAFF_ROLES:
        course = db.get(Course, submission.assignment.course_id) if submission.assignment else None
        if course is None:
            course = db.get(Course, submission.assignment.course_id) if hasattr(submission, "assignment") else None
        return
    learner = learner_profile(db, user)
    if not learner or learner.id != submission.learner_id:
        raise ForbiddenError("Learners may only access their own submissions")


def get_or_404(db: Session, model, ident, label: str):
    obj = db.get(model, ident)
    if obj is None:
        raise NotFoundError(f"{label} not found")
    return obj
