import asyncio
import copy
import json

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.ai import GeminiProvider, MAX_RESPONSE_BYTES
from app.api.quizzes import get_quiz_service
from app.core import QuizError, Settings, TOKEN_TTL, decrypt_quiz
from app.main import app
from app.quiz_service import QuizService
from app.schemas.quiz import GenerateRequest


@pytest.fixture
def settings():
    return Settings("test-key-only", Fernet.generate_key().decode())


def request_body(mode="topic"):
    body = {"mode": mode, "external_ai_consent": True, "settings": {"count": 5}}
    body["topic" if mode == "topic" else "text"] = "Python 자료형" if mode == "topic" else "Python의 리스트는 순서가 있고 변경 가능한 자료형입니다."
    return body


def quiz_data(mode="topic", kind="multiple_choice"):
    result = {"questions": []}
    for i in range(5):
        q = {"type": kind, "prompt": f"자료형에 대한 문제 {i + 1}",
             "options": ["리스트", "튜플", "집합", "정수"] if kind == "multiple_choice" else None,
             "answer": {"multiple_choice": 0, "true_false": True, "short_answer": "리스트"}[kind],
             "explanation": "비밀 해설: 리스트는 변경할 수 있습니다.", "evidence": None}
        if mode == "text":
            source = request_body("text")["text"]
            q["evidence"] = {"start": 0, "end": len(source), "quote": source}
        result["questions"].append(q)
    return result


class FakeProvider:
    def __init__(self, data):
        self.data = data
        self.calls = 0

    async def generate(self, request):
        self.calls += 1
        return json.dumps(self.data, ensure_ascii=False)


@pytest.fixture
def api(settings):
    provider = FakeProvider(quiz_data())
    app.dependency_overrides[get_quiz_service] = lambda: QuizService(provider, settings)
    with TestClient(app) as client:
        yield client, provider
    app.dependency_overrides.clear()


@pytest.mark.parametrize("mode", ["topic", "text"])
@pytest.mark.parametrize("kind", ["multiple_choice", "true_false", "short_answer"])
def test_generate_and_encrypt(api, settings, mode, kind):
    client, provider = api
    provider.data = quiz_data(mode, kind)
    body = request_body(mode)
    body["settings"]["question_types"] = [kind]
    response = client.post("/api/quizzes/generate", json=body)
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    data = response.json()
    assert len(data["questions"]) == 5
    assert all(set(q) == {"id", "type", "prompt", "options"} for q in data["questions"])
    assert "비밀 해설" not in response.text
    assert '"answer"' not in response.text
    assert '"evidence"' not in response.text
    payload = json.loads(decrypt_quiz(data["grading_token"], settings.token_key))
    assert payload["quiz_id"] == data["quiz_id"]
    assert payload["quiz"]["questions"][0]["answer"] == provider.data["questions"][0]["answer"]
    assert provider.calls == 1


@pytest.mark.parametrize("field,value", [
    ("count", 7), ("count", "5"), ("difficulty", "expert"),
    ("question_types", []), ("question_types", ["essay"]),
    ("question_types", ["true_false", "true_false"]),
    ("scope", "pages"), ("approach", "random"), ("explanation_level", "none"),
])
def test_invalid_settings(api, field, value):
    client, provider = api
    body = request_body()
    body["settings"][field] = value
    assert client.post("/api/quizzes/generate", json=body).status_code == 422
    assert provider.calls == 0


@pytest.mark.parametrize("patch", [
    {"topic": " "}, {"topic": "a"}, {"topic": "x" * 201},
    {"text": "x" * 20}, {"mode": "file"}, {"pages": [1]},
    {"external_ai_consent": False}, {"external_ai_consent": 1}, {"external_ai_consent": "true"},
    {"mode": "text", "topic": None, "text": "short"},
    {"mode": "text", "topic": None, "text": "x" * 20001},
])
def test_invalid_input(api, patch):
    client, provider = api
    body = request_body()
    body.update(patch)
    response = client.post("/api/quizzes/generate", json=body)
    assert response.status_code == 422
    assert "x" * 100 not in response.text
    assert provider.calls == 0


@pytest.mark.parametrize("patch", [
    {"options": ["a", "b", "c"]}, {"options": ["a", "A", "c", "d"]},
    {"options": ["a", "b", "c", " "]}, {"answer": 4}, {"answer": True},
    {"answer": "0"}, {"explanation": " "}, {"explanation": None},
    {"unexpected": "secret"}, {"type": "short_answer", "options": None, "answer": 3},
    {"type": "true_false", "options": None, "answer": "true"},
    {"evidence": {"start": 0, "end": 2, "quote": "없는"}},
])
def test_invalid_ai_question(api, patch):
    client, provider = api
    provider.data["questions"][0].update(patch)
    response = client.post("/api/quizzes/generate", json=request_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_ai_output"
    assert "secret" not in response.text


@pytest.mark.parametrize("case", ["count", "types", "duplicate", "missing_evidence", "wrong_evidence"])
def test_invalid_quiz_rules(api, case):
    client, provider = api
    body = request_body("text" if "evidence" in case else "topic")
    provider.data = quiz_data(body["mode"])
    if case == "count":
        body["settings"]["count"] = 10
    elif case == "types":
        body["settings"]["question_types"] = ["true_false"]
    elif case == "duplicate":
        provider.data["questions"][1] = copy.deepcopy(provider.data["questions"][0])
    elif case == "missing_evidence":
        provider.data["questions"][0]["evidence"] = None
    else:
        provider.data["questions"][0]["evidence"]["end"] = 999
    assert client.post("/api/quizzes/generate", json=body).status_code == 502


@pytest.mark.parametrize("count", [5, 10, 15, 20])
def test_allowed_counts_and_mixed_types(api, count):
    client, provider = api
    source = quiz_data()["questions"][0]
    provider.data["questions"] = [dict(source, prompt=f"문제 {i}") for i in range(count)]
    provider.data["questions"][0].update(type="true_false", options=None, answer=False)
    body = request_body()
    body["settings"].update(count=count, question_types=["multiple_choice", "true_false"],
                            difficulty="mixed", approach="application", explanation_level="detailed")
    assert client.post("/api/quizzes/generate", json=body).status_code == 200


def test_tokens_tamper_expiry_and_wrong_key(settings):
    cipher = Fernet(settings.token_key.encode())
    token = cipher.encrypt(b"secret").decode()
    mutated = token[:20] + ("A" if token[20] != "A" else "B") + token[21:]
    expired = cipher.encrypt_at_time(b"secret", 1).decode()
    for candidate, key in [(mutated, settings.token_key), (expired, settings.token_key),
                           (token, Fernet.generate_key().decode())]:
        with pytest.raises(QuizError, match="invalid_token"):
            decrypt_quiz(candidate, key)
    assert TOKEN_TTL == 3600


@pytest.mark.parametrize("config", [Settings("", ""), Settings("key", "invalid"), Settings("key", "", enabled=False)])
def test_configuration_prevents_ai_calls(config):
    provider = FakeProvider(quiz_data())
    service = QuizService(provider, config)
    with pytest.raises(QuizError) as error:
        asyncio.run(service.generate(GenerateRequest.model_validate(request_body())))
    assert error.value.status == 503
    assert provider.calls == 0


def install_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr("app.ai.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


@pytest.mark.parametrize("upstream,status,code", [(429, 429, "quota_exhausted"), (401, 503, "provider_unavailable"),
    (403, 503, "provider_unavailable"), (500, 502, "provider_error"), (400, 502, "provider_error")])
def test_provider_errors_http(monkeypatch, settings, upstream, status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(upstream, json={"secret": "DO_NOT_EXPOSE"})
    install_transport(monkeypatch, handler)
    app.dependency_overrides[get_quiz_service] = lambda: QuizService(GeminiProvider(settings), settings)
    try:
        with TestClient(app) as client:
            response = client.post("/api/quizzes/generate", json=request_body())
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert "DO_NOT_EXPOSE" not in response.text
        assert len(calls) == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("failure,status", [("timeout", 504), ("network", 502), ("invalid_json", 502),
    ("truncated", 502), ("blocked", 502), ("oversized", 502), ("bad_quiz", 502)])
def test_transport_failures(monkeypatch, settings, failure, status):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("DO_NOT_EXPOSE", request=request)
        if failure == "network":
            raise httpx.ConnectError("DO_NOT_EXPOSE", request=request)
        if failure == "invalid_json":
            return httpx.Response(200, text="not json")
        if failure == "oversized":
            return httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1))
        if failure == "blocked":
            return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
        return httpx.Response(200, json={"candidates": [{"finishReason": "MAX_TOKENS" if failure == "truncated" else "STOP",
            "content": {"parts": [{"text": "{}"}]}}]})
    install_transport(monkeypatch, handler)
    service = QuizService(GeminiProvider(settings), settings)
    with pytest.raises(QuizError) as error:
        asyncio.run(service.generate(GenerateRequest.model_validate(request_body())))
    assert error.value.status == status
    assert "DO_NOT_EXPOSE" not in error.value.message


def test_gemini_request_contract(monkeypatch, settings):
    def handler(request):
        assert request.url.path.endswith("/gemini-3.1-flash-lite:generateContent")
        assert request.url.query == b""
        assert request.headers["x-goog-api-key"] == "test-key-only"
        body = json.loads(request.content)
        assert body["generationConfig"]["maxOutputTokens"] == 12000
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert "responseJsonSchema" in body["generationConfig"]
        assert "tools" not in body
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "private thought", "thought": True}, {"text": json.dumps(quiz_data())}]}}]})
    install_transport(monkeypatch, handler)
    response = asyncio.run(QuizService(GeminiProvider(settings), settings).generate(GenerateRequest.model_validate(request_body())))
    assert len(response.questions) == 5


def test_large_body_and_methods(api):
    client, provider = api
    assert client.post("/api/quizzes/generate", content=b"x" * 128001).status_code == 413
    assert client.post("/api/quizzes/generate", content=b"{broken", headers={"content-type": "application/json"}).status_code == 422
    assert client.get("/api/quizzes/generate").status_code == 405
    assert provider.calls == 0


def test_missing_server_configuration(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("QUIZFORGE_TOKEN_KEY", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/quizzes/generate", json=request_body()).status_code == 503


def test_pause_environment_keeps_health(monkeypatch):
    monkeypatch.setenv("QUIZFORGE_GENERATION_ENABLED", "false")
    with TestClient(app) as client:
        response = client.post("/api/quizzes/generate", json=request_body())
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "generation_paused"
        assert client.get("/api/health").json() == {"status": "ok"}


def test_sensitive_invalid_input_not_echoed_or_logged(api, caplog):
    client, provider = api
    body = request_body()
    body["topic"] = "PRIVATE_SOURCE_SENTINEL" * 20
    response = client.post("/api/quizzes/generate", json=body)
    assert response.status_code == 422
    assert "PRIVATE_SOURCE_SENTINEL" not in response.text
    assert "PRIVATE_SOURCE_SENTINEL" not in caplog.text
    assert provider.calls == 0
