from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai import GeminiProvider
from app.core import Settings
from app.grading_service import GradingService
from app.quiz_service import QuizService
from app.schemas.quiz import GenerateRequest, GenerateResponse, GradeRequest, GradeResponse

router = APIRouter(tags=["quizzes"])


def get_quiz_service() -> QuizService:
    settings = Settings.from_env()
    return QuizService(GeminiProvider(settings), settings)


def get_grading_service() -> GradingService:
    return GradingService(Settings.from_env())


@router.post("/quizzes/generate", response_model=GenerateResponse,
             responses={422: {"description": "Invalid input"}, 429: {"description": "AI quota exhausted"},
                        502: {"description": "Invalid AI output or upstream failure"},
                        503: {"description": "Paused or not configured"}, 504: {"description": "AI timeout"}})
async def generate_quiz(request: GenerateRequest, service: Annotated[QuizService, Depends(get_quiz_service)]) -> GenerateResponse:
    """입력은 Google Gemini로 전송됩니다. 공개 자료만 사용하세요. 페이지/파일 입력은 지원하지 않습니다."""
    return await service.generate(request)


@router.post("/quizzes/grade", response_model=GradeResponse,
             responses={400: {"description": "Invalid, mismatched, or expired token"},
                        413: {"description": "Request too large"}, 422: {"description": "Invalid answers"},
                        503: {"description": "Token key not configured"}})
def grade_quiz(request: GradeRequest, service: Annotated[GradingService, Depends(get_grading_service)]) -> GradeResponse:
    """전체 답안을 제출하면 정답과 해설을 공개합니다. 객관식은 0~3, OX는 true/false, 단답형은 문자열, 미응답은 null입니다. 외부 AI를 호출하지 않습니다."""
    return service.grade(request)
