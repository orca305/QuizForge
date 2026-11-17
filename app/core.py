import os
from dataclasses import dataclass, field

from cryptography.fernet import Fernet, InvalidToken


class QuizError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(code)


def invalid_output():
    return QuizError(502, "invalid_ai_output", "AI 응답을 검증하지 못했습니다. 나중에 다시 시도해주세요.")


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    token_key: str = field(repr=False)
    enabled: bool = True
    model: str = "gemini-3.1-flash-lite"

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            token_key=os.getenv("QUIZFORGE_TOKEN_KEY", "").strip(),
            enabled=os.getenv("QUIZFORGE_GENERATION_ENABLED", "true").lower() == "true",
        )

    def cipher(self):
        if not self.enabled:
            raise QuizError(503, "generation_paused", "퀴즈 생성 기능이 일시 중지되었습니다.")
        if not self.api_key:
            raise QuizError(503, "not_configured", "퀴즈 생성 서버 설정이 필요합니다.")
        return self.token_cipher()

    def token_cipher(self):
        # Grading remains available without Gemini credentials or generation enabled.
        if not self.token_key:
            raise QuizError(503, "not_configured", "퀴즈 암호화 서버 설정이 필요합니다.")
        try:
            return Fernet(self.token_key.encode("ascii"))
        except (ValueError, UnicodeError):
            raise QuizError(503, "not_configured", "퀴즈 암호화 서버 설정이 필요합니다.") from None


TOKEN_TTL = 3600


def decrypt_quiz(token: str, key: str) -> bytes:
    """Authenticate and enforce expiry before reading any quiz answers."""
    try:
        return Fernet(key.encode("ascii")).decrypt(token.encode("ascii"), ttl=TOKEN_TTL)
    except (InvalidToken, ValueError, UnicodeError):
        raise QuizError(400, "invalid_token", "유효하지 않거나 만료된 퀴즈입니다.") from None
