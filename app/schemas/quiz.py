from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
QuestionType = Literal["multiple_choice", "true_false", "short_answer"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class GenerationSettings(StrictModel):
    count: Literal[5, 10, 15, 20] = 5
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "medium"
    question_types: list[QuestionType] = Field(default_factory=lambda: ["multiple_choice"], min_length=1, max_length=3)
    approach: Literal["concepts", "application", "balanced"] = "balanced"
    explanation_level: Literal["brief", "detailed"] = "brief"
    scope: Literal["all"] = "all"

    @model_validator(mode="after")
    def unique_types(self):
        if len(set(self.question_types)) != len(self.question_types):
            raise ValueError("question_types must be unique")
        return self


class GenerateRequest(StrictModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "mode": "topic", "topic": "Python 리스트와 튜플의 차이", "external_ai_consent": True,
        "settings": {"count": 5, "difficulty": "medium", "question_types": ["multiple_choice"],
                     "approach": "balanced", "explanation_level": "brief", "scope": "all"},
    }]})
    mode: Literal["text", "topic"]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=20000)] | None = None
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)] | None = None
    settings: GenerationSettings = Field(default_factory=GenerationSettings)
    external_ai_consent: Literal[True]

    @field_validator("external_ai_consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("explicit consent required")
        return value

    @model_validator(mode="after")
    def check_source(self):
        if self.mode == "text" and (self.text is None or self.topic is not None):
            raise ValueError("text mode requires only text")
        if self.mode == "topic" and (self.topic is None or self.text is not None):
            raise ValueError("topic mode requires only topic")
        return self


class Evidence(StrictModel):
    # Python character offsets into the normalized request text: [start, end).
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: Text


class GeneratedQuestion(StrictModel):
    type: QuestionType
    prompt: Text
    options: list[Text] | None
    answer: int | bool | Text
    explanation: Text
    evidence: Evidence | None

    @model_validator(mode="after")
    def check_answer(self):
        if self.type == "multiple_choice":
            if self.options is None or len(self.options) != 4:
                raise ValueError("multiple choice requires four options")
            normalized = [" ".join(x.split()).casefold() for x in self.options]
            if len(set(normalized)) != 4:
                raise ValueError("duplicate options")
            if type(self.answer) is not int or not 0 <= self.answer <= 3:
                raise ValueError("answer must be a zero-based option index")
        else:
            if self.options is not None:
                raise ValueError("options must be null")
            if self.type == "true_false" and type(self.answer) is not bool:
                raise ValueError("answer must be boolean")
            if self.type == "short_answer" and not isinstance(self.answer, str):
                raise ValueError("answer must be text")
        return self


class GeneratedQuiz(StrictModel):
    questions: list[GeneratedQuestion] = Field(min_length=5, max_length=20)


class PublicQuestion(StrictModel):
    id: int
    type: QuestionType
    prompt: Text
    options: list[Text] | None


class GenerateResponse(StrictModel):
    quiz_id: str
    questions: list[PublicQuestion]
    grading_token: str
    expires_in_seconds: int
    notice: str


QuizId = Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]
SubmittedAnswer = int | bool | Text | None


class QuizTokenPayload(StrictModel):
    version: Literal[1]
    quiz_id: QuizId
    mode: Literal["text", "topic"]
    quiz: GeneratedQuiz


class AnswerSubmission(StrictModel):
    question_id: int = Field(ge=1, le=20)
    answer: SubmittedAnswer = Field(description="객관식: 0~3 정수(첫 선택지=0), OX: true/false, 단답형: 문자열, 미응답: null")


class GradeRequest(StrictModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "quiz_id": "00000000-0000-0000-0000-000000000000",
        "grading_token": "생성 응답의 grading_token으로 교체하세요",
        "answers": [{"question_id": 1, "answer": 0}, {"question_id": 2, "answer": 1},
                    {"question_id": 3, "answer": 2}, {"question_id": 4, "answer": 3},
                    {"question_id": 5, "answer": None}],
    }]})
    quiz_id: QuizId
    grading_token: str = Field(min_length=1, max_length=400000, repr=False)
    answers: list[AnswerSubmission] = Field(min_length=5, max_length=20)

    @model_validator(mode="after")
    def unique_question_ids(self):
        ids = [item.question_id for item in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate question ids")
        return self


class GradedQuestion(StrictModel):
    id: int
    type: QuestionType
    prompt: Text
    options: list[Text] | None
    submitted_answer: SubmittedAnswer
    is_correct: bool
    correct_answer: int | bool | Text
    explanation: Text
    evidence: Evidence | None


class GradeResponse(StrictModel):
    quiz_id: QuizId
    total_questions: int
    correct_count: int
    score_percent: float
    results: list[GradedQuestion]
    notice: str
