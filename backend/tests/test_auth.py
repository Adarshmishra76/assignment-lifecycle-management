from tests.conftest import auth_header, make_instructor, make_learner


def test_register_and_login(client):
    created = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@demo.local",
            "password": "DemoPass123!",
            "full_name": "New Learner",
            "role": "learner",
            "student_number": "STU-9",
        },
    )
    assert created.status_code == 200
    token = client.post("/api/v1/auth/login", json={"email": "new@demo.local", "password": "DemoPass123!"})
    assert token.status_code == 200
    me = client.get("api/v1/auth/me", headers={"Authorization": f"Bearer {token.json()['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "learner"


def test_invalid_login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@demo.local", "password": "wrong"})
    assert response.status_code == 401


def test_learner_cannot_self_register_as_admin(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "evil@demo.local",
            "password": "DemoPass123!",
            "full_name": "Evil",
            "role": "platform_admin",
        },
    )
    assert response.status_code == 422


def test_learner_cannot_grade(client, db):
    make_instructor(db)
    learner = make_learner(db)
    headers = auth_header(client, learner.email)
    response = client.post(
        "/api/v1/grades",
        json={"submission_id": 1, "scores": [{"criterion_id": 1, "score": 1}]},
        headers=headers,
    )
    assert response.status_code in (403, 404)
