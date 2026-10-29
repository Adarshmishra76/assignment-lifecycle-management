"""Submission rules: enrollment, deadlines, versions, artifacts and visibility."""
from sqlalchemy import func, select

from app.models import Submission
from tests.helpers import API


def _count_submissions(world):
    world.db.expire_all()
    return world.db.scalar(select(func.count()).select_from(Submission))


def test_enrolled_learner_can_submit_on_time(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    response = world.submit(learner, assignment)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["version_number"], body["is_late"], body["status"]) == (1, False, "submitted")
    assert body["learner_id"] == learner.learner_id


def test_unenrolled_learner_cannot_submit_and_nothing_is_stored(world):
    assignment = world.create_assignment()
    outsider = world.add_learner(enroll=False)
    response = world.submit(outsider, assignment)
    assert response.status_code == 403
    assert "not enrolled" in response.json()["detail"]
    assert _count_submissions(world) == 0


def test_dropped_enrollment_blocks_submission(world):
    from app.models import CourseEnrollment

    assignment = world.create_assignment()
    learner = world.add_learner()
    world.db.expire_all()
    enrollment = world.db.scalar(select(CourseEnrollment).where(CourseEnrollment.learner_id == learner.learner_id))
    enrollment.status = "dropped"
    world.db.commit()
    assert world.submit(learner, assignment).status_code == 403


def test_staff_cannot_submit_work(world):
    assignment = world.create_assignment()
    response = world.client.post(
        f"{API}/submissions", json={"assignment_id": assignment.id, "artifacts": []}, headers=world.inst_h
    )
    assert response.status_code == 403


def test_draft_assignment_is_not_open_for_submission(world):
    assignment = world.create_assignment(publish=False)
    learner = world.add_learner()
    response = world.submit(learner, assignment)
    assert response.status_code == 422
    assert "not open" in response.json()["detail"]


def test_unknown_assignment_is_404(world):
    learner = world.add_learner()
    response = world.client.post(
        f"{API}/submissions", json={"assignment_id": 99999, "artifacts": []}, headers=learner.headers
    )
    assert response.status_code == 404


def test_late_submission_is_flagged_when_late_work_is_allowed(world):
    assignment = world.create_assignment(overdue=True)
    learner = world.add_learner()
    response = world.submit(learner, assignment)
    assert response.status_code == 200
    assert response.json()["is_late"] is True


def test_late_submission_is_rejected_when_late_work_is_not_allowed(world):
    assignment = world.create_assignment(overdue=True, allow_late=False)
    learner = world.add_learner()
    response = world.submit(learner, assignment)
    assert response.status_code == 422
    assert "Late submissions are not allowed" in response.json()["detail"]
    assert _count_submissions(world) == 0


def test_second_attempt_must_use_the_resubmission_workflow(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    world.submit_ok(learner, assignment)
    again = world.submit(learner, assignment)
    assert again.status_code == 422
    assert "resubmission" in again.json()["detail"].lower()
    assert _count_submissions(world) == 1


def test_artifact_checksums_are_stored_lowercase(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    response = world.client.post(
        f"{API}/submissions",
        json={
            "assignment_id": assignment.id,
            "artifacts": [
                {"filename": "essay.pdf", "mime_type": "application/pdf", "file_size_bytes": 1234, "checksum_sha256": "AB" * 32}
            ],
        },
        headers=learner.headers,
    )
    assert response.status_code == 200, response.text
    artifact = response.json()["artifacts"][0]
    assert artifact["checksum_sha256"] == "ab" * 32
    assert artifact["availability_status"] == "available"


def test_invalid_artifact_input_is_rejected(world):
    assignment = world.create_assignment()
    learner = world.add_learner()
    good = {"filename": "a.pdf", "mime_type": "application/pdf", "file_size_bytes": 1, "checksum_sha256": "a" * 64}

    bad_status = world.client.post(
        f"{API}/submissions",
        json={"assignment_id": assignment.id, "artifacts": [{**good, "availability_status": "bogus"}]},
        headers=learner.headers,
    )
    short_hash = world.client.post(
        f"{API}/submissions",
        json={"assignment_id": assignment.id, "artifacts": [{**good, "checksum_sha256": "abc"}]},
        headers=learner.headers,
    )
    negative_size = world.client.post(
        f"{API}/submissions",
        json={"assignment_id": assignment.id, "artifacts": [{**good, "file_size_bytes": -5}]},
        headers=learner.headers,
    )
    assert bad_status.status_code == 422
    assert short_hash.status_code == 422
    assert negative_size.status_code == 422
    assert _count_submissions(world) == 0


def test_learner_sees_only_their_own_submissions(world):
    assignment = world.create_assignment()
    first, second = world.add_learner(), world.add_learner()
    first_id = world.submit_ok(first, assignment)
    second_id = world.submit_ok(second, assignment)

    mine = world.client.get(f"{API}/submissions", headers=first.headers).json()
    assert mine["total"] == 1 and [s["id"] for s in mine["items"]] == [first_id]

    staff = world.client.get(f"{API}/submissions", headers=world.inst_h).json()
    assert staff["total"] == 2

    assert world.client.get(f"{API}/submissions/{second_id}", headers=first.headers).status_code == 403


def test_submission_listing_paginates_and_filters_by_status(world):
    assignment = world.create_assignment()
    learners = [world.add_learner() for _ in range(3)]
    ids = [world.submit_ok(learner, assignment) for learner in learners]
    world.grade_ok(assignment, ids[0], [50, 30])

    page = world.client.get(f"{API}/submissions", params={"page": 1, "page_size": 2}, headers=world.inst_h).json()
    assert (page["total"], len(page["items"]), page["page"], page["page_size"]) == (3, 2, 1, 2)

    graded = world.client.get(f"{API}/submissions", params={"status": "graded"}, headers=world.inst_h).json()
    assert [s["id"] for s in graded["items"]] == [ids[0]]
