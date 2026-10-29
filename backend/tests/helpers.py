"""Builders shared by the workflow tests.

Everything goes through the public API wherever possible so the tests exercise the same
paths a client would. Direct ORM writes are only used to create states the API refuses to
produce (an overdue deadline, an unenrolled submission, a tampered grade).
"""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.core.time import utcnow
from app.models import Assignment, Learner, User
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user
from tests.conftest import auth_header, future_due

API = "/api/v1"
D = Decimal


def make_user(db, email: str, role: str, student_number: str | None = None):
    admin = db.query(User).filter(User.role == "platform_admin").one()
    return register_user(
        db,
        RegisterRequest(
            email=email,
            password="DemoPass123!",
            full_name=email.split("@")[0],
            role=role,
            student_number=student_number,
        ),
        actor=admin,
    )


class World:
    def __init__(self, client, db):
        self.client = client
        self.db = db
        self.admin_h = auth_header(client, "admin@demo.local")
        self.instructor = make_user(db, "teacher@demo.local", "instructor")
        self.inst_h = auth_header(client, "teacher@demo.local")
        response = client.post(
            f"{API}/courses",
            json={"code": "CS100", "title": "Algorithms", "term": "2026-Fall"},
            headers=self.inst_h,
        )
        assert response.status_code == 200, response.text
        self.course_id = response.json()["id"]
        self._learners = 0
        self._assignments = 0

    # ---- people -------------------------------------------------------------------------
    def add_learner(self, enroll: bool = True):
        self._learners += 1
        email = f"learner{self._learners}@demo.local"
        user = make_user(self.db, email, "learner", student_number=f"STU-{self._learners}")
        learner = self.db.query(Learner).filter(Learner.user_id == user.id).one()
        if enroll:
            response = self.client.post(
                f"{API}/courses/enrollments",
                json={"course_id": self.course_id, "learner_id": learner.id},
                headers=self.admin_h,
            )
            assert response.status_code == 200, response.text
        return SimpleNamespace(
            user=user,
            learner_id=learner.id,
            headers=auth_header(self.client, email),
        )

    def add_staff(self, email: str, role: str):
        user = make_user(self.db, email, role)
        return SimpleNamespace(user=user, headers=auth_header(self.client, email))

    # ---- assignments --------------------------------------------------------------------
    def create_assignment(
        self,
        *,
        criteria=(("Correctness", 60), ("Style", 40)),
        late_penalty_percent="10.00",
        allow_late=True,
        max_resubmissions=1,
        policy="instructor_approval",
        overdue=False,
        publish=True,
    ):
        self._assignments += 1
        response = self.client.post(
            f"{API}/assignments",
            json={
                "course_id": self.course_id,
                "title": f"Assignment {self._assignments}",
                "due_at": future_due(),
                "allow_late": allow_late,
                "late_penalty_percent": late_penalty_percent,
                "max_resubmissions": max_resubmissions,
                "resubmission_policy": policy,
            },
            headers=self.inst_h,
        )
        assert response.status_code == 200, response.text
        assignment_id = response.json()["id"]
        rubric = self.client.post(
            f"{API}/assignments/rubrics",
            json={
                "assignment_id": assignment_id,
                "name": "Rubric",
                "criteria": [{"name": name, "max_score": maximum} for name, maximum in criteria],
            },
            headers=self.inst_h,
        )
        assert rubric.status_code == 200, rubric.text
        criterion_ids = [c["id"] for c in sorted(rubric.json()["criteria"], key=lambda c: c["id"])]
        if publish:
            published = self.client.post(f"{API}/assignments/{assignment_id}/publish", headers=self.inst_h)
            assert published.status_code == 200, published.text
        if overdue:
            self.make_overdue(assignment_id)
        return SimpleNamespace(id=assignment_id, criteria=criterion_ids)

    def make_overdue(self, assignment_id: int) -> None:
        """Move the deadline into the past after publication (publishing needs a future date)."""
        self.db.expire_all()
        assignment = self.db.get(Assignment, assignment_id)
        assignment.due_at = utcnow() - timedelta(hours=2)
        self.db.commit()

    # ---- submissions and grades ---------------------------------------------------------
    def submit(self, actor, assignment):
        return self.client.post(
            f"{API}/submissions",
            json={"assignment_id": assignment.id, "artifacts": []},
            headers=actor.headers,
        )

    def submit_ok(self, actor, assignment) -> int:
        response = self.submit(actor, assignment)
        assert response.status_code == 200, response.text
        return response.json()["id"]

    def grade_payload(self, assignment, submission_id: int, values, **extra) -> dict:
        return {
            "submission_id": submission_id,
            "scores": [{"criterion_id": c, "score": v} for c, v in zip(assignment.criteria, values)],
            **extra,
        }

    def grade(self, assignment, submission_id: int, values, headers=None, **extra):
        return self.client.post(
            f"{API}/grades",
            json=self.grade_payload(assignment, submission_id, values, **extra),
            headers=headers or self.inst_h,
        )

    def grade_ok(self, assignment, submission_id: int, values, **extra) -> dict:
        response = self.grade(assignment, submission_id, values, **extra)
        assert response.status_code == 200, response.text
        return response.json()

    def revise(self, assignment, grade_id: int, values, reason="Regrade", headers=None):
        return self.client.post(
            f"{API}/grades/{grade_id}/revise",
            json={
                "scores": [{"criterion_id": c, "score": v} for c, v in zip(assignment.criteria, values)],
                "reason": reason,
            },
            headers=headers or self.inst_h,
        )

    def graded_submission(self, *, values=(50, 30), late=False, **assignment_kwargs):
        """assignment + enrolled learner + submission + posted grade."""
        assignment = self.create_assignment(overdue=late, **assignment_kwargs)
        learner = self.add_learner()
        submission_id = self.submit_ok(learner, assignment)
        grade = self.grade_ok(assignment, submission_id, list(values))
        return SimpleNamespace(
            assignment=assignment,
            learner=learner,
            submission_id=submission_id,
            grade=grade,
            grade_id=grade["id"],
        )

    # ---- appeals ------------------------------------------------------------------------
    def file_appeal(self, learner, grade_id: int, reason="Criterion 1 was marked too harshly."):
        return self.client.post(
            f"{API}/appeals",
            json={"grade_id": grade_id, "reason": reason},
            headers=learner.headers,
        )

    def decide_appeal(self, appeal_id: int, decision: str, assignment=None, values=None, headers=None, reason="Reviewed"):
        body = {"decision": decision, "decision_reason": reason}
        if values is not None:
            body["scores"] = [{"criterion_id": c, "score": v} for c, v in zip(assignment.criteria, values)]
        return self.client.post(f"{API}/appeals/{appeal_id}/decision", json=body, headers=headers or self.inst_h)

    def approved_appeal(self, case, values=(60, 30)):
        appeal = self.file_appeal(case.learner, case.grade_id)
        assert appeal.status_code == 200, appeal.text
        decided = self.decide_appeal(appeal.json()["id"], "approved", case.assignment, list(values))
        assert decided.status_code == 200, decided.text
        return decided.json()
