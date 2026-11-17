"""Tests for student accounts, isolated learning data, and tutor workflows."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from qwenpaw.app.learning import api as learning_api
from qwenpaw.app.learning.store import LearningStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        learning_api,
        "_store",
        LearningStore(tmp_path / "learning.sqlite3"),
    )
    app = FastAPI()
    app.include_router(learning_api.router)
    with TestClient(app) as test_client:
        yield test_client


def _register(client: TestClient, username: str) -> tuple[str, str]:
    response = client.post(
        "/learning/auth/register",
        json={"username": username, "password": "secure-password-123"},
    )
    assert response.status_code == 200
    data = response.json()
    return data["student"]["id"], data["token"]


def test_student_accounts_and_materials_are_isolated(client: TestClient) -> None:
    first_id, first_token = _register(client, "student-one")
    second_id, second_token = _register(client, "student-two")

    added = client.post(
        "/learning/materials",
        headers={"X-Student-Token": first_token},
        json={
            "subject": "Sinh học",
            "grade": 10,
            "title": "Động vật có vú",
            "content": "Khỉ là động vật có vú và linh trưởng.",
        },
    )
    assert added.status_code == 200

    first_materials = client.get(
        "/learning/materials",
        headers={"X-Student-Token": first_token},
    ).json()
    second_materials = client.get(
        "/learning/materials",
        headers={"X-Student-Token": second_token},
    ).json()

    assert first_id != second_id
    assert len(first_materials) == 1
    assert second_materials == []

    login = client.post(
        "/learning/auth/login",
        json={"username": "student-one", "password": "secure-password-123"},
    )
    assert login.status_code == 200
    assert login.json()["student"]["id"] == first_id

    logged_out = client.post(
        "/learning/auth/logout",
        headers={"X-Student-Token": first_token},
    )
    assert logged_out.status_code == 200
    assert client.get(
        "/learning/auth/me",
        headers={"X-Student-Token": first_token},
    ).status_code == 401


def test_qwenpaw_login_owns_separate_learning_records(
    tmp_path,
    monkeypatch,
) -> None:
    store = LearningStore(tmp_path / "shared-learning.sqlite3")
    _, legacy_token = store.register("legacy-account", "legacy-password-123")
    monkeypatch.setattr(learning_api, "_store", store)
    app = FastAPI()

    @app.middleware("http")
    async def set_authenticated_user(request, call_next):
        request.state.user = request.headers["X-Test-User"]
        return await call_next(request)

    app.include_router(learning_api.router)
    with TestClient(app) as test_client:
        first = test_client.get(
            "/learning/auth/me",
            headers={
                "X-Test-User": "student-a",
                "X-Student-Token": legacy_token,
            },
        ).json()
        second = test_client.get(
            "/learning/auth/me",
            headers={"X-Test-User": "student-b"},
        ).json()
        assert first["id"] != second["id"]

        created = test_client.post(
            "/learning/materials",
            headers={"X-Test-User": "student-a"},
            json={
                "subject": "Toán",
                "grade": 10,
                "title": "Hàm số",
                "content": "Tài liệu riêng của học sinh A.",
            },
        )
        assert created.status_code == 200
        assert test_client.get(
            "/learning/materials",
            headers={"X-Test-User": "student-a"},
        ).json()
        assert test_client.get(
            "/learning/materials",
            headers={"X-Test-User": "student-b"},
        ).json() == []


def test_qwenpaw_bearer_token_identifies_user_without_middleware_state(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        learning_api,
        "verify_token",
        lambda token: (
            "local-student" if token == "valid-qwenpaw-token" else None
        ),
    )

    response = client.get(
        "/learning/auth/me",
        headers={"Authorization": "Bearer valid-qwenpaw-token"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "local-student"


def test_qwenpaw_username_reuses_existing_learning_account(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.sqlite3")
    existing, _ = store.register("LocalStudent", "legacy-password-123")

    current = store.get_or_create_for_username("localstudent")

    assert current["id"] == existing["id"]


def test_rag_answer_is_saved_to_student_history(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, token = _register(client, "rag-student")
    headers = {"X-Student-Token": token}
    client.post(
        "/learning/materials",
        headers=headers,
        json={
            "subject": "Sinh học",
            "grade": 10,
            "title": "Bài về linh trưởng",
            "content": "Khỉ thuộc nhóm động vật linh trưởng.",
        },
    )
    prompts: list[str] = []

    async def fake_generate(_request, prompt: str) -> str:
        prompts.append(prompt)
        return "Khỉ thuộc nhóm động vật linh trưởng."

    monkeypatch.setattr(learning_api, "_generate_text", fake_generate)
    answer = client.post(
        "/learning/ask",
        headers=headers,
        json={
            "question": "Khỉ thuộc nhóm động vật nào?",
            "subject": "Sinh học",
            "grade": 10,
            "topic": "Động vật",
            "mode": "question",
        },
    )

    assert answer.status_code == 200
    assert answer.json()["sources"][0]["title"] == "Bài về linh trưởng"
    assert "Khỉ thuộc nhóm động vật linh trưởng." in prompts[0]
    saved = client.get("/learning/history", headers=headers).json()
    assert saved[0]["prompt"] == "Khỉ thuộc nhóm động vật nào?"
    assert saved[0]["topic"] == "Động vật"


def test_quiz_grading_updates_progress_and_recommendations(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, token = _register(client, "quiz-student")
    headers = {"X-Student-Token": token}
    generated = {
        "questions": [
            {
                "prompt": "Câu 1?",
                "options": ["Đúng", "Sai 1", "Sai 2", "Sai 3"],
                "correct_index": 0,
                "explanation": "Giải thích câu 1.",
            },
            {
                "prompt": "Câu 2?",
                "options": ["Sai 1", "Đúng", "Sai 2", "Sai 3"],
                "correct_index": 1,
                "explanation": "Giải thích câu 2.",
            },
        ],
    }

    async def fake_generate(_request, _prompt: str) -> str:
        import json

        return json.dumps(generated)

    monkeypatch.setattr(learning_api, "_generate_text", fake_generate)
    created = client.post(
        "/learning/quizzes",
        headers=headers,
        json={
            "subject": "Toán",
            "topic": "Hàm số",
            "grade": 10,
            "difficulty": "easy",
            "count": 2,
        },
    )
    assert created.status_code == 200
    quiz = created.json()
    assert "correct_index" not in quiz["questions"][0]
    assert "explanation" not in quiz["questions"][0]

    submitted = client.post(
        f"/learning/quizzes/{quiz['id']}/submit",
        headers=headers,
        json={"answers": [0, 0]},
    )
    assert submitted.status_code == 200
    assert submitted.json()["score"] == 1
    assert submitted.json()["feedback"][1]["explanation"] == "Giải thích câu 2."

    progress = client.get("/learning/progress", headers=headers).json()
    assert progress["topics"][0]["accuracy"] == 0.5
    assert progress["recommendations"][0]["topic"] == "Hàm số"


def test_study_plan_schedule_is_validated_and_owner_scoped(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, first_token = _register(client, "plan-student-one")
    _, second_token = _register(client, "plan-student-two")
    headers = {"X-Student-Token": first_token}

    async def fake_generate(_request, _prompt: str) -> str:
        return (
            '{"tasks":['
            '{"title":"Buổi 1","focus":"Khái niệm","activity":"Đọc bài"},'
            '{"title":"Buổi 2","focus":"Bài tập","activity":"Làm 5 câu"},'
            '{"title":"Buổi 3","focus":"Ôn tập","activity":"Tự kiểm tra"}'
            "]}"
        )

    monkeypatch.setattr(learning_api, "_generate_text", fake_generate)
    created = client.post(
        "/learning/plans",
        headers=headers,
        json={
            "subject": "Toán",
            "grade": 10,
            "goal": "Ôn hàm số",
            "start_date": "2026-01-05",
            "days": 8,
            "daily_minutes": 30,
            "weekdays": [0, 2],
        },
    )
    assert created.status_code == 200
    plan = created.json()
    assert [task["date"] for task in plan["tasks"]] == [
        "2026-01-05",
        "2026-01-07",
        "2026-01-12",
    ]

    forbidden = client.patch(
        f"/learning/plans/{plan['id']}/tasks/0",
        headers={"X-Student-Token": second_token},
        json={"completed": True},
    )
    assert forbidden.status_code == 404

    completed = client.patch(
        f"/learning/plans/{plan['id']}/tasks/0",
        headers=headers,
        json={"completed": True},
    )
    assert completed.status_code == 200
    assert completed.json()["tasks"][0]["completed"] is True
