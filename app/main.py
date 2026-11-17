from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.quizzes import router as quiz_router
from app.core import QuizError

app = FastAPI(
    title="QuizForge API",
    description="Python/FastAPI quiz backend — Phase 3. 생성 시 입력은 외부 AI로 전송됩니다. 채점은 서버에서 수행합니다.",
    version="0.3.0",
)
app.include_router(health_router, prefix="/api")
app.include_router(quiz_router, prefix="/api")


@app.exception_handler(QuizError)
async def quiz_error_handler(request, exc: QuizError):
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}},
                        headers={"Cache-Control": "no-store"})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    # FastAPI's default errors echo input; never return source text or secrets.
    return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": "입력 형식과 생성 설정을 확인해주세요."}})


class RequestLimitMiddleware:
    """Bound quiz API bodies before JSON parsing, including chunked requests."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        limits = {"/api/quizzes/generate": 128000, "/api/quizzes/grade": 600000}
        if scope["type"] != "http" or scope["path"] not in limits:
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > limits[scope["path"]]:
                response = JSONResponse(status_code=413, content={"error": {"code": "request_too_large", "message": "입력이 너무 큽니다."}})
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break

        async def replay():
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        async def no_cache(message):
            if message["type"] == "http.response.start":
                message["headers"] = [(key, value) for key, value in message["headers"] if key.lower() != b"cache-control"]
                message["headers"].append((b"cache-control", b"no-store"))
            await send(message)

        await self.app(scope, replay, no_cache)


app.add_middleware(RequestLimitMiddleware)
