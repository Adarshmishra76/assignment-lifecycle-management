from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CourseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    term: str = Field(min_length=1, max_length=32)
    instructor_id: int | None = None


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    term: str | None = None
    status: str | None = None
    instructor_id: int | None = None


class CourseOut(ORMModel):
    id: int
    public_id: str
    code: str
    title: str
    description: str | None
    term: str
    instructor_id: int
    status: str
    created_at: datetime


class LearnerCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str
    student_number: str = Field(min_length=1, max_length=32)


class LearnerOut(ORMModel):
    id: int
    public_id: str
    user_id: int
    student_number: str
    status: str
    full_name: str | None = None
    email: str | None = None


class EnrollmentCreate(BaseModel):
    course_id: int
    learner_id: int


class EnrollmentOut(ORMModel):
    id: int
    public_id: str
    course_id: int
    learner_id: int
    status: str
    enrolled_at: datetime


class AssignmentCreate(BaseModel):
    course_id: int
    title: str
    description: str | None = None
    due_at: datetime | None = None
    allow_late: bool = True
    late_penalty_percent: Decimal = Decimal("10.00")
    max_resubmissions: int = 1
    resubmission_policy: str = "instructor_approval"


class AssignmentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_at: datetime | None = None
    allow_late: bool | None = None
    late_penalty_percent: Decimal | None = None
    max_resubmissions: int | None = None
    resubmission_policy: str | None = None


class AssignmentOut(ORMModel):
    id: int
    public_id: str
    course_id: int
    title: str
    description: str | None
    status: str
    current_version_id: int | None
    due_at: datetime | None
    published_at: datetime | None
    allow_late: bool
    late_penalty_percent: Decimal
    max_resubmissions: int
    resubmission_policy: str


class AssignmentVersionOut(ORMModel):
    id: int
    public_id: str
    assignment_id: int
    version_number: int
    title: str
    due_at: datetime | None
    published_at: datetime
    rubric_id: int | None


class CriterionIn(BaseModel):
    name: str
    description: str | None = None
    max_score: Decimal
    weight: Decimal = Decimal("1.000")
    sort_order: int = 0


class RubricCreate(BaseModel):
    assignment_id: int
    name: str
    criteria: list[CriterionIn] = Field(min_length=1)


class CriterionOut(ORMModel):
    id: int
    public_id: str
    rubric_id: int
    name: str
    description: str | None
    max_score: Decimal
    weight: Decimal
    sort_order: int


class RubricOut(ORMModel):
    id: int
    public_id: str
    assignment_id: int
    name: str
    version_number: int
    max_score: Decimal
    criteria: list[CriterionOut] = []


class ArtifactIn(BaseModel):
    filename: str
    mime_type: str
    file_size_bytes: int = Field(ge=0)
    checksum_sha256: str = Field(min_length=64, max_length=64)
    availability_status: str = "available"


class SubmissionCreate(BaseModel):
    assignment_id: int
    artifacts: list[ArtifactIn] = Field(default_factory=list)


class ArtifactOut(ORMModel):
    id: int
    public_id: str
    filename: str
    mime_type: str
    file_size_bytes: int
    checksum_sha256: str
    uploaded_at: datetime
    availability_status: str


class SubmissionOut(ORMModel):
    id: int
    public_id: str
    assignment_id: int
    assignment_version_id: int
    learner_id: int
    version_number: int
    submitted_at: datetime
    is_late: bool
    status: str
    artifacts: list[ArtifactOut] = []


class RubricScoreIn(BaseModel):
    criterion_id: int
    score: Decimal


class GradeCreate(BaseModel):
    submission_id: int
    scores: list[RubricScoreIn] = Field(min_length=1)
    feedback: str | None = None
    apply_late_penalty: bool | None = None


class RubricScoreOut(ORMModel):
    id: int
    criterion_id: int
    score: Decimal


class GradeOut(ORMModel):
    id: int
    public_id: str
    submission_id: int
    revision_number: int
    is_current: bool
    raw_score: Decimal
    late_penalty_applied: bool
    late_penalty_amount: Decimal
    final_score: Decimal
    status: str
    grader_id: int
    created_at: datetime
    scores: list[RubricScoreOut] = []


class GradeReviseRequest(BaseModel):
    scores: list[RubricScoreIn] = Field(min_length=1)
    reason: str = Field(min_length=1)
    feedback: str | None = None


class FeedbackOut(ORMModel):
    id: int
    public_id: str
    grade_id: int | None
    submission_id: int
    author_id: int
    body: str
    created_at: datetime


class GradeRevisionOut(ORMModel):
    id: int
    public_id: str
    grade_id: int
    previous_final_score: Decimal | None
    new_final_score: Decimal
    reason: str
    changed_by_id: int
    created_at: datetime


class ResubmissionCreate(BaseModel):
    assignment_id: int
    previous_submission_id: int


class ResubmissionDecision(BaseModel):
    approved: bool
    reason: str


class ResubmissionOut(ORMModel):
    id: int
    public_id: str
    assignment_id: int
    learner_id: int
    previous_submission_id: int
    resulting_submission_id: int | None
    status: str
    requested_at: datetime
    decided_at: datetime | None
    decision_reason: str | None


class AppealCreate(BaseModel):
    grade_id: int
    reason: str
    evidence_refs: str | None = None


class AppealDecision(BaseModel):
    decision: str
    decision_reason: str
    scores: list[RubricScoreIn] | None = None
    feedback: str | None = None


class AppealOut(ORMModel):
    id: int
    public_id: str
    grade_id: int
    submission_id: int
    learner_id: int
    reason: str
    evidence_refs: str | None
    status: str
    reviewer_id: int | None
    decision: str | None
    decision_reason: str | None
    created_at: datetime
    decided_at: datetime | None
    resulting_grade_id: int | None


class AuditOut(ORMModel):
    id: int
    public_id: str
    actor_id: int | None
    entity_type: str
    entity_id: int
    action: str
    from_state: str | None
    to_state: str | None
    payload: str | None
    created_at: datetime
