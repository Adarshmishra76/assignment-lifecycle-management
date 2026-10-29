"""Resubmission workflow: request -> decision -> new attempt, with limits and ownership."""
from tests.helpers import API


def _request(world, learner, assignment, previous_submission_id):
    return world.client.post(
        f"{API}/resubmissions",
        json={"assignment_id": assignment.id, "previous_submission_id": previous_submission_id},
        headers=learner.headers,
    )


def _decide(world, resubmission_id, approved, headers=None, reason="Policy check"):
    return world.client.post(
        f"{API}/resubmissions/{resubmission_id}/decision",
        json={"approved": approved, "reason": reason},
        headers=headers or world.inst_h,
    )


def _complete(world, learner, resubmission_id, assignment):
    return world.client.post(
        f"{API}/resubmissions/{resubmission_id}/submit",
        json={"assignment_id": assignment.id, "artifacts": []},
        headers=learner.headers,
    )


def _setup(world, **kwargs):
    assignment = world.create_assignment(**kwargs)
    learner = world.add_learner()
    submission_id = world.submit_ok(learner, assignment)
    return assignment, learner, submission_id


def test_full_resubmission_flow_keeps_the_original_attempt(world):
    assignment, learner, first_id = _setup(world)

    requested = _request(world, learner, assignment, first_id)
    assert requested.status_code == 200, requested.text
    resubmission_id = requested.json()["id"]
    assert requested.json()["status"] == "requested"

    approved = _decide(world, resubmission_id, True)
    assert approved.status_code == 200 and approved.json()["status"] == "approved"

    completed = _complete(world, learner, resubmission_id, assignment)
    assert completed.status_code == 200, completed.text
    body = completed.json()
    assert body["status"] == "completed"
    assert body["resulting_submission_id"] and body["resulting_submission_id"] != first_id

    second = world.client.get(f"{API}/submissions/{body['resulting_submission_id']}", headers=learner.headers).json()
    assert second["version_number"] == 2

    listing = world.client.get(f"{API}/submissions", params={"assignment_id": assignment.id}, headers=world.inst_h).json()
    assert sorted(s["version_number"] for s in listing["items"]) == [1, 2]


def test_attempts_are_limited_by_max_resubmissions(world):
    assignment, learner, first_id = _setup(world, max_resubmissions=1)
    rid = _request(world, learner, assignment, first_id).json()["id"]
    _decide(world, rid, True)
    assert _complete(world, learner, rid, assignment).status_code == 200

    again = _request(world, learner, assignment, first_id)
    assert again.status_code == 422
    assert "exhausted" in again.json()["detail"]


def test_only_one_request_can_be_in_progress(world):
    assignment, learner, first_id = _setup(world, max_resubmissions=3)
    assert _request(world, learner, assignment, first_id).status_code == 200
    duplicate = _request(world, learner, assignment, first_id)
    assert duplicate.status_code == 422
    assert "in progress" in duplicate.json()["detail"]


def test_denied_request_cannot_be_completed(world):
    assignment, learner, first_id = _setup(world)
    rid = _request(world, learner, assignment, first_id).json()["id"]
    denied = _decide(world, rid, False, reason="Not eligible")
    assert denied.status_code == 200 and denied.json()["status"] == "denied"
    blocked = _complete(world, learner, rid, assignment)
    assert blocked.status_code == 422
    assert "not approved" in blocked.json()["detail"]


def test_request_cannot_be_decided_twice(world):
    assignment, learner, first_id = _setup(world)
    rid = _request(world, learner, assignment, first_id).json()["id"]
    assert _decide(world, rid, True).status_code == 200
    assert _decide(world, rid, False).status_code == 422


def test_automatic_policy_approves_immediately(world):
    assignment, learner, first_id = _setup(world, policy="automatic")
    response = _request(world, learner, assignment, first_id)
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert _complete(world, learner, response.json()["id"], assignment).status_code == 200


def test_assignment_without_resubmissions_rejects_requests(world):
    assignment, learner, first_id = _setup(world, policy="none", max_resubmissions=0)
    response = _request(world, learner, assignment, first_id)
    assert response.status_code == 422
    assert "not allowed" in response.json()["detail"]


def test_learner_cannot_resubmit_against_someone_elses_submission(world):
    assignment, owner, first_id = _setup(world)
    other = world.add_learner()
    response = _request(world, other, assignment, first_id)
    assert response.status_code == 422
    assert "invalid" in response.json()["detail"].lower()


def test_learner_cannot_decide_their_own_request(world):
    assignment, learner, first_id = _setup(world)
    rid = _request(world, learner, assignment, first_id).json()["id"]
    assert _decide(world, rid, True, headers=learner.headers).status_code == 403


def test_instructor_of_another_course_cannot_decide(world):
    assignment, learner, first_id = _setup(world)
    rid = _request(world, learner, assignment, first_id).json()["id"]
    other = world.add_staff("other@demo.local", "instructor")
    assert _decide(world, rid, True, headers=other.headers).status_code == 403


def test_other_learner_cannot_complete_an_approved_request(world):
    assignment, learner, first_id = _setup(world)
    rid = _request(world, learner, assignment, first_id).json()["id"]
    _decide(world, rid, True)
    intruder = world.add_learner()
    assert _complete(world, intruder, rid, assignment).status_code == 403


def test_learner_lists_only_their_own_requests(world):
    assignment, learner, first_id = _setup(world)
    _request(world, learner, assignment, first_id)
    other = world.add_learner()
    assert world.client.get(f"{API}/resubmissions", headers=other.headers).json()["total"] == 0
    assert world.client.get(f"{API}/resubmissions", headers=learner.headers).json()["total"] == 1
