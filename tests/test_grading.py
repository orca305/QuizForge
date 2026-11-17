import asyncio
import json
import unicodedata

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.api.quizzes import get_grading_service
from app.core import Settings
from app.grading_service import GradingService
from app.main import app
from app.quiz_service import QuizService
from app.schemas.quiz import GenerateRequest

QUIZ_ID = "1305d00b-0062-4da6-a047-e4b8ae53e8f2"


def quiz_payload():
    questions = []
    for i, (kind, answer) in enumerate([
        ("multiple_choice", 0), ("true_false", False), ("short_answer", "Python List"),
        ("short_answer", "리스트"), ("multiple_choice", 3),
    ], 1):
        questions.append({"type": kind, "prompt": f"문제 {i}",
                          "options": ["a", "b", "c", "d"] if kind == "multiple_choice" else None,
                          "answer": answer, "explanation": f"비공개해설 {i}", "evidence": None})
    return {"version": 1, "quiz_id": QUIZ_ID, "mode": "topic", "quiz": {"questions": questions}}


@pytest.fixture
def api():
    # No API key, generation disabled: grading must still work without an AI call.
    settings = Settings("", Fernet.generate_key().decode(), enabled=False)
    app.dependency_overrides[get_grading_service] = lambda: GradingService(settings)
    with TestClient(app) as client:
        yield client, settings
    app.dependency_overrides.clear()


def submission(settings, payload=None):
    token = Fernet(settings.token_key.encode()).encrypt(json.dumps(payload or quiz_payload(), ensure_ascii=False).encode()).decode()
    return {"quiz_id": QUIZ_ID, "grading_token": token, "answers": [
        {"question_id": 1, "answer": 0}, {"question_id": 2, "answer": False},
        {"question_id": 3, "answer": "  PYTHON\t list  "},
        {"question_id": 4, "answer": unicodedata.normalize("NFD", "리스트")},
        {"question_id": 5, "answer": 3},
    ]}


def test_grade_correct_and_normalized(api):
    client, settings = api
    response = client.post("/api/quizzes/grade", json=submission(settings))
    assert response.status_code == 200
    result = response.json()
    assert result["correct_count"] == 5
    assert result["total_questions"] == 5
    assert result["score_percent"] == 100.0
    assert all(q["is_correct"] for q in result["results"])
    assert result["results"][0]["correct_answer"] == 0
    assert result["results"][0]["explanation"] == "비공개해설 1"
    assert response.headers["cache-control"] == "no-store"
    assert "grading_token" not in result


def test_incorrect_unanswered_and_shuffled(api):
    client, settings = api
    body = submission(settings)
    body["answers"][0]["answer"] = 2
    body["answers"][1]["answer"] = None
    body["answers"][2]["answer"] = "list"  # No synonym/partial matching.
    body["answers"].reverse()
    response = client.post("/api/quizzes/grade", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["correct_count"] == 2
    assert result["score_percent"] == 40.0
    assert [q["id"] for q in result["results"]] == [1, 2, 3, 4, 5]
    assert result["results"][1]["submitted_answer"] is None
    assert result["results"][1]["is_correct"] is False


@pytest.mark.parametrize("question_id,answer", [
    (1, True), (1, "0"), (1, -1), (1, 4), (1, 0.0),
    (2, 0), (2, 1), (2, "false"), (3, False), (3, 1),
    (3, " "), (3, "x" * 2001), (1, []),
])
def test_wrong_answer_types_do_not_reveal_solutions(api, question_id, answer):
    client, settings = api
    body = submission(settings)
    body["answers"][question_id - 1]["answer"] = answer
    response = client.post("/api/quizzes/grade", json=body)
    assert response.status_code == 422
    assert "correct_answer" not in response.text
    assert "비공개해설" not in response.text
    assert body["grading_token"] not in response.text


@pytest.mark.parametrize("case", ["missing", "duplicate", "unknown", "boolean_id", "extra", "missing_answer"])
def test_invalid_submissions(api, case):
    client, settings = api
    body = submission(settings)
    if case == "missing":
        body["answers"].pop()
    elif case == "duplicate":
        body["answers"][1]["question_id"] = 1
    elif case == "unknown":
        body["answers"][1]["question_id"] = 6
    elif case == "boolean_id":
        body["answers"][0]["question_id"] = True
    elif case == "extra":
        body["answers"][0]["correct_answer"] = 0
    else:
        del body["answers"][0]["answer"]
    assert client.post("/api/quizzes/grade", json=body).status_code == 422


@pytest.mark.parametrize("case", ["tampered", "expired", "wrong_key", "quiz_id", "version", "payload", "not_json"])
def test_invalid_tokens(api, case, caplog):
    client, settings = api
    body = submission(settings)
    cipher = Fernet(settings.token_key.encode())
    if case == "tampered":
        token = body["grading_token"]
        body["grading_token"] = token[:30] + ("A" if token[30] != "A" else "B") + token[31:]
    elif case == "expired":
        body["grading_token"] = cipher.encrypt_at_time(json.dumps(quiz_payload()).encode(), 1).decode()
    elif case == "wrong_key":
        body["grading_token"] = Fernet(Fernet.generate_key()).encrypt(b"{}").decode()
    elif case == "quiz_id":
        body["quiz_id"] = "00000000-0000-0000-0000-000000000000"
    elif case == "not_json":
        body["grading_token"] = cipher.encrypt(b"PRIVATE_INVALID_JSON").decode()
    else:
        payload = quiz_payload()
        if case == "version":
            payload["version"] = 2
        else:
            payload["quiz"]["questions"][0]["answer"] = "SECRET_WRONG_TYPE"
        body["grading_token"] = cipher.encrypt(json.dumps(payload).encode()).decode()
    response = client.post("/api/quizzes/grade", json=body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_token"
    assert body["grading_token"] not in response.text
    assert "SECRET_WRONG_TYPE" not in response.text + caplog.text
    assert "PRIVATE_INVALID_JSON" not in response.text + caplog.text


@pytest.mark.parametrize("key", ["", "invalid"])
def test_server_key_configuration(key):
    app.dependency_overrides[get_grading_service] = lambda: GradingService(Settings("", key))
    try:
        with TestClient(app) as client:
            body = submission(Settings("", Fernet.generate_key().decode()))
            assert client.post("/api/quizzes/grade", json=body).status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_evidence_revealed_only_after_submission(api):
    client, settings = api
    payload = quiz_payload()
    payload["mode"] = "text"
    payload["quiz"]["questions"][0]["evidence"] = {"start": 0, "end": 4, "quote": "근거자료"}
    response = client.post("/api/quizzes/grade", json=submission(settings, payload))
    assert response.status_code == 200
    assert response.json()["results"][0]["evidence"]["quote"] == "근거자료"


def test_request_limits_and_method(api):
    client, settings = api
    assert client.post("/api/quizzes/grade", content=b"x" * 600001).status_code == 413
    body = submission(settings)
    body["grading_token"] = "x" * 400001
    assert client.post("/api/quizzes/grade", json=body).status_code == 422
    assert client.get("/api/quizzes/grade").status_code == 405


def test_no_one_time_submission_guarantee(api):
    client, settings = api
    body = submission(settings)
    first = client.post("/api/quizzes/grade", json=body)
    second = client.post("/api/quizzes/grade", json=body)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_generate_then_grade_with_same_token(api):
    client, settings = api
    enabled = Settings("fake-key-only", settings.token_key)

    class Provider:
        async def generate(self, request):
            return json.dumps(quiz_payload()["quiz"], ensure_ascii=False)

    generated = asyncio.run(QuizService(Provider(), enabled).generate(GenerateRequest.model_validate({
        "mode": "topic", "topic": "Python 자료형", "external_ai_consent": True,
        "settings": {"question_types": ["multiple_choice", "true_false", "short_answer"]},
    })))
    assert "correct_answer" not in generated.model_dump()
    assert all("answer" not in q for q in generated.model_dump()["questions"])
    body = submission(settings)
    body.update(quiz_id=generated.quiz_id, grading_token=generated.grading_token)
    response = client.post("/api/quizzes/grade", json=body)
    assert response.status_code == 200
    assert response.json()["correct_count"] == 5


def test_openapi_topic_example_is_valid_and_grade_documented(api):
    client, settings = api
    schema = client.get("/openapi.json").json()
    example = schema["components"]["schemas"]["GenerateRequest"]["examples"][0]
    GenerateRequest.model_validate(example)
    assert "text" not in example
    assert "/api/quizzes/grade" in schema["paths"]


@pytest.mark.parametrize("count,correct,score", [(5, 0, 0.0), (10, 7, 70.0), (15, 1, 6.67), (20, 19, 95.0)])
def test_score_calculation_for_supported_counts(api, count, correct, score):
    client, settings = api
    payload = quiz_payload()
    source = payload["quiz"]["questions"][0]
    payload["quiz"]["questions"] = [dict(source, prompt=f"문제 {i}") for i in range(count)]
    body = submission(settings, payload)
    body["answers"] = [{"question_id": i + 1, "answer": 0 if i < correct else None} for i in range(count)]
    response = client.post("/api/quizzes/grade", json=body)
    assert response.status_code == 200
    assert response.json()["total_questions"] == count
    assert response.json()["correct_count"] == correct
    assert response.json()["score_percent"] == score
