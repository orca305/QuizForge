export type QuestionType = "multiple_choice" | "true_false" | "short_answer";
export type Answer = number | boolean | string | null;
export type Evidence = { start: number; end: number; quote: string };
export type Question = { id: number; type: QuestionType; prompt: string; options: string[] | null };
export type Quiz = {
  quiz_id: string; questions: Question[]; grading_token: string;
  expires_in_seconds: number; notice: string;
};
export type GradedQuestion = Question & {
  submitted_answer: Answer; is_correct: boolean; correct_answer: Exclude<Answer, null>;
  explanation: string; evidence: Evidence | null;
};
export type Grade = {
  quiz_id: string; total_questions: number; correct_count: number;
  score_percent: number; results: GradedQuestion[]; notice: string;
};
export type GenerationSettings = {
  count: 5 | 10 | 15 | 20;
  difficulty: "easy" | "medium" | "hard" | "mixed";
  question_types: QuestionType[];
  approach: "concepts" | "application" | "balanced";
  explanation_level: "brief" | "detailed";
  scope: "all";
};

const messages: Record<string, string> = {
  quota_exhausted: "Gemini 사용량 제한으로 퀴즈 생성이 중지되었습니다. 기존 퀴즈의 풀이와 채점은 가능합니다.",
  generation_paused: "퀴즈 생성이 일시 중지되었습니다. 나중에 다시 시도하세요.",
  not_configured: "서버 설정이 완료되지 않았습니다. 백엔드의 환경변수 설정을 확인하세요.",
  invalid_token: "만료되었거나 유효하지 않은 퀴즈입니다. 새 퀴즈를 생성하세요.",
  provider_timeout: "AI 응답 시간이 초과되었습니다. 자동 재시도는 하지 않습니다.",
  provider_error: "AI 서비스에 연결하지 못했습니다. 나중에 다시 시도하세요.",
  provider_unavailable: "AI 연결 권한을 확인해야 합니다.",
  invalid_ai_output: "생성된 문제의 형식이 올바르지 않습니다. 다시 시도하세요.",
  invalid_request: "입력 내용과 출제 설정을 확인하세요.",
  invalid_answers: "문항 유형에 맞는 답안을 입력하세요. 미응답 상태로 제출할 수 있습니다.",
  request_too_large: "입력 길이 제한을 초과했습니다. 내용을 줄여 다시 시도하세요.",
};

export class ApiError extends Error {
  constructor(public code: string) { super(messages[code] ?? "서버에 연결할 수 없습니다. 백엔드 실행 상태를 확인하세요."); }
}

export async function post<T>(path: "generate" | "grade", body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/quizzes/${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body), cache: "no-store", signal: AbortSignal.timeout(60000),
    });
  } catch { throw new ApiError("connection_error"); }
  let data;
  try { data = await response.json(); } catch { throw new ApiError("connection_error"); }
  if (!response.ok) throw new ApiError(typeof data?.error?.code === "string" ? data.error.code : "connection_error");
  return data as T;
}
