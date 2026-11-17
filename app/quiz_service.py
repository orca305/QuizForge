import json
from uuid import uuid4

from pydantic import ValidationError

from app.ai import QuizProvider
from app.core import Settings, TOKEN_TTL, invalid_output
from app.schemas.quiz import GenerateRequest, GenerateResponse, GeneratedQuiz, PublicQuestion


class QuizService:
    def __init__(self, provider: QuizProvider, settings: Settings):
        self.provider = provider
        self.settings = settings

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        cipher = self.settings.cipher()  # Fail before any external call if keys are missing.
        raw = await self.provider.generate(request)
        try:
            quiz = GeneratedQuiz.model_validate_json(raw)
            if len(quiz.questions) != request.settings.count:
                raise ValueError("count mismatch")
            if {q.type for q in quiz.questions} != set(request.settings.question_types):
                raise ValueError("type mismatch")
            prompts = [" ".join(q.prompt.split()).casefold() for q in quiz.questions]
            if len(set(prompts)) != len(prompts):
                raise ValueError("duplicate questions")
            for question in quiz.questions:
                evidence = question.evidence
                if request.mode == "topic":
                    if evidence is not None:
                        raise ValueError("fabricated source")
                elif (evidence is None or not 0 <= evidence.start < evidence.end <= len(request.text)
                      or request.text[evidence.start:evidence.end] != evidence.quote):
                    raise ValueError("invalid evidence")
        except (ValidationError, ValueError):
            raise invalid_output() from None
        quiz_id = str(uuid4())
        # Bind the full public quiz to its answers; Phase 3 must use this payload, not client edits.
        payload = {"version": 1, "quiz_id": quiz_id, "mode": request.mode, "quiz": quiz.model_dump()}
        token = cipher.encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
        return GenerateResponse(
            quiz_id=quiz_id,
            questions=[PublicQuestion(id=i, type=q.type, prompt=q.prompt, options=q.options)
                       for i, q in enumerate(quiz.questions, 1)],
            grading_token=token,
            expires_in_seconds=TOKEN_TTL,
            notice="AI가 생성한 문제입니다. 구조 검증은 사실적 정확성을 보장하지 않습니다.",
        )
