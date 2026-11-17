r"""Manual browser QA only. No Gemini call, no production app changes.

Run from project root:
  .venv\Scripts\python.exe -m uvicorn ui_mock_server:app --app-dir tests --port 18012
Point the frontend's QUIZFORGE_API_ORIGIN to http://127.0.0.1:18012.
Topic '테스트:한도초과' returns a quota error; all other topics use fixed sample data.
"""

import json

from cryptography.fernet import Fernet

from app.api.quizzes import get_grading_service, get_quiz_service
from app.core import QuizError, Settings
from app.grading_service import GradingService
from app.main import app
from app.quiz_service import QuizService

settings = Settings("mock-not-a-real-key", Fernet.generate_key().decode())


class BrowserTestProvider:
    async def generate(self, request):
        if request.topic == "테스트:한도초과":
            raise QuizError(429, "quota_exhausted", "테스트 서버의 한도 초과 예시입니다.")
        questions = []
        for index in range(request.settings.count):
            kind = request.settings.question_types[index % len(request.settings.question_types)]
            stem, options, answer = {
                "multiple_choice": ("Python 리스트의 특징은 무엇인가요?", ["변경 가능하다", "숫자만 저장한다", "중복을 허용하지 않는다", "요소를 교체할 수 없다"], 0),
                "true_false": ("리스트는 요소를 추가할 수 있다.", None, True),
                "short_answer": ("Python의 변경 가능한 순서형 자료형은?", None, "리스트"),
            }[kind]
            questions.append({"type": kind, "prompt": f"[테스트 데이터 {index + 1}] {stem}",
                              "options": options, "answer": answer,
                              "explanation": "브라우저 QA용 고정 해설입니다. 실제 AI 생성 결과가 아닙니다.",
                              "evidence": {"start": 0, "end": len(request.text), "quote": request.text} if request.mode == "text" else None})
        return json.dumps({"questions": questions}, ensure_ascii=False)


app.dependency_overrides[get_quiz_service] = lambda: QuizService(BrowserTestProvider(), settings)
app.dependency_overrides[get_grading_service] = lambda: GradingService(settings)
