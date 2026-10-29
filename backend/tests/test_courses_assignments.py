from datetime import timedelta

from tests.conftest import auth_header, future_due, make_instructor, make_learner
from app.core.time import utcnow
from app.models.learner import Learner


def _learner_id(db, user):
    return db.query(Learner).filter(Learner.user_id == user.id).one().id


def test_course_assignment_publish_workflow(client, db):
    instructor = make_instructor(db)
    learner = make_learner(db)
    admin_h = auth_header(client, "admin@demo.local")
    inst_h = auth_header(client, instructor.email)
    learn_h = auth_header(client, learner.email)

    course = client.post(
        "/api/v1/courses",
        json={"code": "CS100", "title": "Algorithms", "term": "2026-Fall"},
        headers=inst_h,
    )
    assert course.status_code == 200
    course_id = course.json()["id"]

    dup = client.post(
        "/api/v1/courses/enrollments",
        json={"course_id": course_id, "learner_id": _learner_id(db, learner)},
        headers=admin_h,
    )
    assert dup.status_code == 200
    again = client.post(
        "/api/v1/courses/enrollments",
        json={"course_id": course_id, "learner_id": _learner_id(db, learner)},
        headers=admin_h,
    )
    assert again.status_code == 409

    missing_parent = client.post(
        "/api/v1/assignments",
        json={"course_id": 9999, "title": "A1", "due_at": future_due()},
        headers=inst_h,
    )
    assert missing_parent.status_code == 404

    assignment = client.post(
        "/api/v1/assignments",
        json={"course_id": course_id, "title": "A1", "due_at": future_due()},
        headers=inst_h,
    )
    assert assignment.status_code == 200
    assignment_id = assignment.json()["id"]

    unauthorized = client.post(f"/api/v1/assignments/{assignment_id}/publish", headers=learn_h)
    assert unauthorized.status_code == 403

    no_rubric = client.post(f"/api/v1/assignments/{assignment_id}/publish", headers=inst_h)
    assert no_rubric.status_code == 422

    rubric = client.post(
        "/api/v1/assignments/rubrics",
        json={
            "assignment_id": assignment_id,
            "name": "Default",
            "criteria": [
                {"name": "Correctness", "max_score": 60},
                {"name": "Style", "max_score": 40},
            ],
        },
        headers=inst_h,
    )
    assert rubric.status_code == 200

    past = client.patch(
        f"/api/v1/assignments/{assignment_id}",
        json={"due_at": (utcnow() - timedelta(days=1)).isoformat()},
        headers=inst_h,
    )
    assert past.status_code == 200
    invalid_deadline = client.post(f"/api/v1/assignments/{assignment_id}/publish", headers=inst_h)
    assert invalid_deadline.status_code == 422

    client.patch(
        f"/api/v1/assignments/{assignment_id}",
        json={"due_at": future_due()},
        headers=inst_h,
    )
    published = client.post(f"/api/v1/assignments/{assignment_id}/publish", headers=inst_h)
    assert published.status_code == 200
    versions = client.get(f"/api/v1/assignments/{assignment_id}/versions", headers=inst_h)
    assert versions.status_code == 200
    assert len(versions.json()) == 1
