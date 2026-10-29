from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.ids import next_public_id
from app.core.lifecycle import ENROLLMENT_STATES
from app.models.course import Course, CourseEnrollment
from app.models.learner import Learner
from app.models.user import User
from app.schemas.academic import CourseCreate, CourseUpdate, EnrollmentCreate, LearnerCreate
from app.services.access import ADMIN_ROLES, learner_profile
from app.services.audit import record_audit
from app.core.security import hash_password


def list_courses(db: Session, page: int, page_size: int, user: User) -> tuple[list[Course], int]:
    stmt = select(Course)
    if user.role == "learner":
        learner = learner_profile(db, user)
        if not learner:
            return [], 0
        stmt = stmt.join(CourseEnrollment).where(
            CourseEnrollment.learner_id == learner.id,
            CourseEnrollment.status == "enrolled",
        )
    elif user.role == "instructor":
        stmt = stmt.where(Course.instructor_id == user.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Course.id).offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total


def create_course(db: Session, payload: CourseCreate, user: User) -> Course:
    if user.role not in ADMIN_ROLES | {"instructor"}:
        raise ForbiddenError("Not authorized to create courses")
    if db.scalar(select(Course).where(Course.code == payload.code)):
        raise ConflictError("Course code already exists")
    instructor_id = payload.instructor_id or user.id
    instructor = db.get(User, instructor_id)
    if not instructor or instructor.role not in {"instructor", "academic_admin", "platform_admin"}:
        raise ValidationAppError("Invalid instructor_id")
    course = Course(
        public_id=next_public_id(db, Course, "CRS"),
        code=payload.code,
        title=payload.title,
        description=payload.description,
        term=payload.term,
        instructor_id=instructor_id,
        status="active",
    )
    db.add(course)
    db.flush()
    record_audit(db, actor_id=user.id, entity_type="course", entity_id=course.id, action="create")
    db.commit()
    db.refresh(course)
    return course


def update_course(db: Session, course_id: int, payload: CourseUpdate, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise NotFoundError("Course not found")
    if user.role not in ADMIN_ROLES and not (user.role == "instructor" and course.instructor_id == user.id):
        raise ForbiddenError("Not authorized to update this course")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(course, key, value)
    record_audit(db, actor_id=user.id, entity_type="course", entity_id=course.id, action="update")
    db.commit()
    db.refresh(course)
    return course


def create_learner(db: Session, payload: LearnerCreate, user: User) -> Learner:
    if user.role not in ADMIN_ROLES | {"support_staff"}:
        raise ForbiddenError("Not authorized to create learners")
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise ConflictError("Email already registered")
    if db.scalar(select(Learner).where(Learner.student_number == payload.student_number)):
        raise ConflictError("Student number already exists")
    account = User(
        public_id=next_public_id(db, User, "USR"),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role="learner",
    )
    db.add(account)
    db.flush()
    learner = Learner(
        public_id=next_public_id(db, Learner, "LRN", 7),
        user_id=account.id,
        student_number=payload.student_number,
    )
    db.add(learner)
    db.flush()
    record_audit(db, actor_id=user.id, entity_type="learner", entity_id=learner.id, action="create")
    db.commit()
    db.refresh(learner)
    return learner


def list_learners(db: Session, page: int, page_size: int, user: User) -> tuple[list[Learner], int]:
    if user.role == "learner":
        learner = learner_profile(db, user)
        return ([learner] if learner else []), (1 if learner else 0)
    stmt = select(Learner).options(joinedload(Learner.user))
    total = db.scalar(select(func.count()).select_from(Learner)) or 0
    items = db.scalars(stmt.order_by(Learner.id).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return list(items), total


def enroll(db: Session, payload: EnrollmentCreate, user: User) -> CourseEnrollment:
    course = db.get(Course, payload.course_id)
    if not course:
        raise NotFoundError("Course not found")
    learner = db.get(Learner, payload.learner_id)
    if not learner:
        raise NotFoundError("Learner not found")
    if user.role == "learner":
        own = learner_profile(db, user)
        if not own or own.id != learner.id:
            raise ForbiddenError("Learners may only enroll themselves")
    elif user.role not in ADMIN_ROLES | {"instructor", "support_staff"}:
        raise ForbiddenError("Not authorized to enroll learners")
    existing = db.scalar(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == payload.course_id,
            CourseEnrollment.learner_id == payload.learner_id,
        )
    )
    if existing:
        raise ConflictError("Duplicate enrollment")
    enrollment = CourseEnrollment(
        public_id=next_public_id(db, CourseEnrollment, "ENR", 7),
        course_id=payload.course_id,
        learner_id=payload.learner_id,
        status="enrolled",
    )
    db.add(enrollment)
    db.flush()
    record_audit(
        db,
        actor_id=user.id,
        entity_type="enrollment",
        entity_id=enrollment.id,
        action="enroll",
        to_state="enrolled",
    )
    db.commit()
    db.refresh(enrollment)
    return enrollment


def list_enrollments(db: Session, course_id: int | None, page: int, page_size: int) -> tuple[list[CourseEnrollment], int]:
    stmt = select(CourseEnrollment)
    count_stmt = select(func.count()).select_from(CourseEnrollment)
    if course_id:
        stmt = stmt.where(CourseEnrollment.course_id == course_id)
        count_stmt = count_stmt.where(CourseEnrollment.course_id == course_id)
    total = db.scalar(count_stmt) or 0
    items = db.scalars(stmt.order_by(CourseEnrollment.id).offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total
