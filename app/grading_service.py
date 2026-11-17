import unicodedata

from pydantic import ValidationError

from app.core import QuizError, Settings, decrypt_quiz
from app.schemas.quiz import GradeRequest, GradeResponse, GradedQuestion, QuizTokenPayload


def normalize_answer(value: str) -> str:
    """Normalize canonical Unicode, case and whitespace; no synonym guessing."""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


class GradingService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def grade(self, request: GradeRequest) -> GradeResponse:
        self.settings.token_cipher()  # Distinguish invalid server config from invalid tokens.
        raw = decrypt_quiz(request.grading_token, self.settings.token_key)
        try:
            payload = QuizTokenPayload.model_validate_json(raw)
        except ValidationError:
            raise QuizError(400, "invalid_token", "유효하지 않거나 만료된 퀴즈입니다.") from None
        if payload.quiz_id != request.quiz_id:
            raise QuizError(400, "invalid_token", "유효하지 않거나 만료된 퀴즈입니다.")

        questions = payload.quiz.questions
        answers = {item.question_id: item.answer for item in request.answers}
        if set(answers) != set(range(1, len(questions) + 1)):
            raise QuizError(422, "invalid_answers", "모든 문항의 답안을 한 번씩 제출해주세요. 미응답은 null로 표시합니다.")

        results = []
        for question_id, question in enumerate(questions, 1):
            submitted = answers[question_id]
            if submitted is None:
                correct = False
            else:
                valid = (
                    (question.type == "multiple_choice" and type(submitted) is int and 0 <= submitted <= 3)
                    or (question.type == "true_false" and type(submitted) is bool)
                    or (question.type == "short_answer" and isinstance(submitted, str))
                )
                if not valid:
                    # Do not include answers, token payload, or input in errors/logs.
                    raise QuizError(422, "invalid_answers", "문항 유형에 맞는 답안 형식을 사용해주세요.")
                correct = (normalize_answer(submitted) == normalize_answer(question.answer)
                           if question.type == "short_answer" else submitted == question.answer)
            results.append(GradedQuestion(
                id=question_id, type=question.type, prompt=question.prompt, options=question.options,
                submitted_answer=submitted, is_correct=correct, correct_answer=question.answer,
                explanation=question.explanation, evidence=question.evidence,
            ))

        correct_count = sum(result.is_correct for result in results)
        return GradeResponse(
            quiz_id=payload.quiz_id, total_questions=len(questions), correct_count=correct_count,
            score_percent=round(correct_count / len(questions) * 100, 2), results=results,
            notice="단답형은 공백과 대소문자 차이를 제외하고 정답과 일치해야 합니다. 동의어나 유사한 표현은 오답일 수 있습니다. AI 정답에는 오류가 있을 수 있습니다.",
        )
