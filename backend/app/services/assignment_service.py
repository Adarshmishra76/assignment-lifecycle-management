from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.core.ids import next_public_id
from app.core.lifecycle import ASSIGNMENT_TRANSITIONS, RESUBMISSION_POLICIES, assert_transition, round_score
from app.core.time import as_utc
from app.models.assignment import Assignment, AssignmentVersion
from app.models.course import Course
from app.models.rubric import Rubric, RubricCriterion
from app.models.user import User
from app.schemas.academic import AssignmentCreate, AssignmentUpdate, RubricCreate
from app.services.access import learner_profile, require_can_publish
from app.services.audit import record_audit


def list_assignments(db: Session, course_id: int | None, page: int, page_size: int, user: User):
    stmt = select(Assignment)
    count_stmt = select(func.count()).select_from(Assignment)
    if course_id:
        stmt = stmt.where(Assignment.course_id == course_id)
        count_stmt = count_stmt.where(Assignment.course_id == course_id)
    if user.role == "learner":
        stmt = stmt.where(Assignment.status.in_(["published", "closed"]))
        count_stmt = count_stmt.where(Assignment.status.in_(["published", "closed"]))
    total = db.scalar(count_stmt) or 0
    items = db.scalars(stmt.order_by(Assignment.id).offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total


def create_assignment(db: Session, payload: AssignmentCreate, user: User) -> Assignment:
    course = db.get(Course, payload.course_id)
    if not course:
        raise NotFoundError("Course not found")
    if user.role not in {"instructor", "academic_admin", "platform_admin"}:
        raise ForbiddenError("Not authorized to create assignments")
    if user.role == "instructor" and course.instructor_id != user.id:
        raise ForbiddenError("Not the instructor for this course")
    if payload.resubmission_policy not in RESUBMISSION_POLICIES:
        raise ValidationAppError("Invalid resubmission policy")
    assignment = Assignment(
        public_id=next_public_id(db, Assignment, "ASN"),
        course_id=payload.course_id,
        title=payload.title,
        description=payload.description,
        due_at=as_utc(payload.due_at),
        allow_late=payload.allow_late,
        late_penalty_percent=round_score(payload.late_penalty_percent),
        max_resubmissions=payload.max_resubmissions,
        resubmission_policy=payload.resubmission_policy,
        created_by_id=user.id,
        status="draft",
    )
    db.add(assignment)
    db.flush()
    record_audit(db, actor_id=user.id, entity_type="assignment", entity_id=assignment.id, action="create", to_state="draft")
    db.commit()
    db.refresh(assignment)
    return assignment


def update_assignment(db: Session, assignment_id: int, payload: AssignmentUpdate, user: User) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise NotFoundError("Assignment not found")
    course = db.get(Course, assignment.course_id)
    require_can_publish(user, course)
    if assignment.status == "archived":
        raise ValidationAppError("Archived assignments cannot be edited")
    data = payload.model_dump(exclude_unset=True)
    if "due_at" in data:
        data["due_at"] = as_utc(data["due_at"])
    if "resubmission_policy" in data and data["resubmission_policy"] not in RESUBMISSION_POLICIES:
        raise ValidationAppError("Invalid resubmission policy")
    for key, value in data.items():
        setattr(assignment, key, value)
    record_audit(db, actor_id=user.id, entity_type="assignment", entity_id=assignment.id, action="update")
    db.commit()
    db.refresh(assignment)
    return assignment


def upsert_rubric(db: Session, payload: RubricCreate, user: User) -> Rubric:
    assignment = db.get(Assignment, payload.assignment_id)
    if not assignment:
        raise NotFoundError("Assignment not found")
    course = db.get(Course, assignment.course_id)
    require_can_publish(user, course)
    rubric = db.scalar(select(Rubric).where(Rubric.assignment_id == assignment.id))
    max_score = sum((c.max_score for c in payload.criteria), Decimal("0"))
    if rubric is None:
        rubric = Rubric(
            public_id=next_public_id(db, Rubric, "RUB"),
            assignment_id=assignment.id,
            name=payload.name,
            version_number=1,
            max_score=round_score(max_score),
        )
        db.add(rubric)
        db.flush()
    else:
        rubric.name = payload.name
        rubric.version_number += 1
        rubric.max_score = round_score(max_score)
        rubric.criteria.clear()
        db.flush()
    for index, criterion in enumerate(payload.criteria):
        db.add(
            RubricCriterion(
                public_id=next_public_id(db, RubricCriterion, "CRT", 7),
                rubric_id=rubric.id,
                name=criterion.name,
                description=criterion.description,
                max_score=round_score(criterion.max_score),
                weight=criterion.weight,
                sort_order=criterion.sort_order or index,
            )
        )
    db.flush()
    record_audit(db, actor_id=user.id, entity_type="rubric", entity_id=rubric.id, action="upsert")
    db.commit()
    db.refresh(rubric)
    return db.scalar(select(Rubric).options(joinedload(Rubric.criteria)).where(Rubric.id == rubric.id))


def get_rubric(db: Session, assignment_id: int) -> Rubric:
    rubric = db.scalar(
        select(Rubric).options(joinedload(Rubric.criteria)).where(Rubric.assignment_id == assignment_id)
    )
    if not rubric:
        raise NotFoundError("Rubric not found")
    return rubric


def publish_assignment(db: Session, assignment_id: int, user: User) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise NotFoundError("Assignment not found")
    course = db.get(Course, assignment.course_id)
    require_can_publish(user, course)
    try:
        assert_transition(assignment.status, "published", ASSIGNMENT_TRANSITIONS, "assignment")
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc
    rubric = db.scalar(select(Rubric).options(joinedload(Rubric.criteria)).where(Rubric.assignment_id == assignment.id))
    if not rubric or not rubric.criteria or rubric.max_score <= 0:
        raise ValidationAppError("A valid rubric with criteria is required before publication")
    if assignment.due_at is None:
        raise ValidationAppError("due_at is required before publication")
    from app.core.time import utcnow

    published_at = utcnow()
    if as_utc(assignment.due_at) <= published_at:
        raise ValidationAppError("due_at must be after publication time")
    version_number = (
        db.scalar(
            select(func.coalesce(func.max(AssignmentVersion.version_number), 0)).where(
                AssignmentVersion.assignment_id == assignment.id
            )
        )
        or 0
    ) + 1
    version = AssignmentVersion(
        public_id=next_public_id(db, AssignmentVersion, "ASV"),
        assignment_id=assignment.id,
        version_number=version_number,
        title=assignment.title,
        description=assignment.description,
        due_at=assignment.due_at,
        published_at=published_at,
        rubric_id=rubric.id,
    )
    db.add(version)
    db.flush()
    assignment.status = "published"
    assignment.published_at = published_at
    assignment.current_version_id = version.id
    record_audit(
        db,
        actor_id=user.id,
        entity_type="assignment",
        entity_id=assignment.id,
        action="publish",
        from_state="draft",
        to_state="published",
        payload={"version_id": version.id, "version_number": version_number},
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def list_versions(db: Session, assignment_id: int) -> list[AssignmentVersion]:
    return list(
        db.scalars(
            select(AssignmentVersion)
            .where(AssignmentVersion.assignment_id == assignment_id)
            .order_by(AssignmentVersion.version_number)
        ).all()
    )


def get_assignment(db: Session, assignment_id: int, user: User) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise NotFoundError("Assignment not found")
    if user.role == "learner" and assignment.status not in {"published", "closed"}:
        raise ForbiddenError("Assignment is not available")
    return assignment
