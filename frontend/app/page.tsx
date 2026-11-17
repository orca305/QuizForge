"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ChangeEvent } from "react";
import { readTxtFile } from "@/lib/text-file";
import { ApiError, post } from "@/lib/api";
import type { Answer, GenerationSettings, Grade, GradedQuestion, Question, QuestionType, Quiz } from "@/lib/api";

const typeLabels: Record<QuestionType, string> = { multiple_choice: "객관식", true_false: "OX", short_answer: "단답형" };
const initialSettings: GenerationSettings = { count: 5, difficulty: "medium", question_types: ["multiple_choice"], approach: "balanced", explanation_level: "brief", scope: "all" };

function answerText(question: Question, answer: Answer) {
  if (answer === null || answer === "") return "미응답";
  if (question.type === "multiple_choice" && typeof answer === "number") return `${String.fromCharCode(65 + answer)}. ${question.options?.[answer] ?? ""}`;
  if (typeof answer === "boolean") return answer ? "O (맞다)" : "X (아니다)";
  return String(answer);
}

function QuestionInput({ question, value, onChange }: { question: Question; value: Answer; onChange: (answer: Answer) => void }) {
  if (question.type === "short_answer") return <label className="short-answer">답안<input type="text" maxLength={2000} value={typeof value === "string" ? value : ""} onChange={event => onChange(event.target.value)} placeholder="답안을 입력하세요" autoComplete="off" /></label>;
  const choices = question.type === "true_false" ? ["맞다", "아니다"] : question.options ?? [];
  return <div className={`answer-options ${question.type === "true_false" ? "ox-options" : ""}`}>
    {choices.map((choice, index) => {
      const answer = question.type === "true_false" ? index === 0 : index;
      return <label className={`answer-option ${value === answer ? "selected" : ""}`} key={index}>
        <input type="radio" name={`question-${question.id}`} checked={value === answer} onChange={() => onChange(answer)} />
        <span className="option-letter">{question.type === "true_false" ? (index === 0 ? "O" : "X") : String.fromCharCode(65 + index)}</span><span>{choice}</span>
      </label>;
    })}
    {value !== null ? <button className="text-button" type="button" onClick={() => onChange(null)}>선택 지우기</button> : null}
  </div>;
}

function ResultQuestion({ question }: { question: GradedQuestion }) {
  return <article className="question-card result-question">
    <div className="question-top"><span className="question-number">{String(question.id).padStart(2, "0")}</span><span className="type-tag">{typeLabels[question.type]}</span><span className={`verdict ${question.is_correct ? "correct" : "incorrect"}`}>{question.is_correct ? "✓ 정답" : "오답"}</span></div>
    <h3>{question.prompt}</h3>
    <dl className="answer-review"><div><dt>내 답안</dt><dd>{answerText(question, question.submitted_answer)}</dd></div><div><dt>정답</dt><dd>{answerText(question, question.correct_answer)}</dd></div></dl>
    <div className="explanation"><span className="small-heading">해설</span><p>{question.explanation}</p></div>
    {question.evidence ? <details className="evidence"><summary>학습자료 근거 확인</summary><blockquote>{question.evidence.quote}</blockquote><span>입력 텍스트 {question.evidence.start + 1}–{question.evidence.end}번째 문자</span></details> : null}
  </article>;
}

export default function Home() {
  const [mode, setMode] = useState<"topic" | "text">("topic");
  const [topic, setTopic] = useState("");
  const [text, setText] = useState("");
  const [consent, setConsent] = useState(false);
  const [settings, setSettings] = useState<GenerationSettings>(initialSettings);
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [answers, setAnswers] = useState<Record<number, Answer>>({});
  const [result, setResult] = useState<Grade | null>(null);
  const [busy, setBusy] = useState<"generate" | "grade" | "import" | null>(null);
  const [sourceFile, setSourceFile] = useState<string | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [paused, setPaused] = useState(false);
  const [expiresAt, setExpiresAt] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const requestInFlight = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const stage = result ? "result" : quiz ? "solve" : "create";
  const answered = quiz?.questions.filter(question => answers[question.id] !== null && answers[question.id] !== undefined && String(answers[question.id]).trim() !== "").length ?? 0;
  const currentValue = mode === "topic" ? topic : text;
  const sourceLength = Array.from(currentValue).length;
  const maxSourceLength = mode === "topic" ? 200 : 20000;
  const visibleError = error ?? (paused && stage === "create" ? {
    code: "generation_paused", message: "퀴즈 생성이 중지되었습니다. 다시 시도하려면 생성 재개를 선택하세요.",
  } : null);

  useEffect(() => {
    if (!quiz || result) return;
    const tick = () => setRemaining(Math.max(0, Math.floor((expiresAt - Date.now()) / 1000)));
    tick();
    const interval = window.setInterval(tick, 1000);
    return () => window.clearInterval(interval);
  }, [quiz, result, expiresAt]);

  useEffect(() => { if (stage !== "create") heading.current?.focus(); }, [stage]);

  function updateSetting<K extends keyof GenerationSettings>(key: K, value: GenerationSettings[K]) {
    setSettings(previous => ({ ...previous, [key]: value }));
  }
  function toggleType(type: QuestionType) {
    setSettings(previous => ({ ...previous, question_types: previous.question_types.includes(type) ? previous.question_types.filter(item => item !== type) : [...previous.question_types, type] }));
  }
  function handleError(cause: unknown) {
    const failure = cause instanceof ApiError ? cause : new ApiError("connection_error");
    setError({ code: failure.code, message: failure.message });
    if (failure.code === "quota_exhausted" || failure.code === "generation_paused") setPaused(true);
  }
  async function importTxt(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // Selecting the same file again must trigger change.
    if (!file || requestInFlight.current) return;
    if (text.trim() && !window.confirm("현재 입력 내용을 파일 내용으로 교체하시겠습니까?")) return;
    requestInFlight.current = true; setBusy("import"); setError(null);
    try {
      const content = await readTxtFile(file);
      setText(content); setSourceFile(file.name);
    } catch (cause) {
      setError({ code: "file_input", message: cause instanceof Error ? cause.message : "파일을 읽지 못했습니다." });
    } finally { setBusy(null); requestInFlight.current = false; }
  }
  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (requestInFlight.current || paused) return;
    const value = currentValue.trim();
    if (Array.from(value).length < (mode === "topic" ? 2 : 20) || Array.from(value).length > maxSourceLength || !settings.question_types.length || !consent) {
      setError({ code: "input", message: "학습 내용, 문제 유형, 외부 AI 전송 동의를 확인해주세요." }); return;
    }
    requestInFlight.current = true; setBusy("generate"); setError(null);
    try {
      const data = await post<Quiz>("generate", { mode, [mode === "topic" ? "topic" : "text"]: value, settings, external_ai_consent: true });
      setQuiz(data); setAnswers({}); setResult(null); setConfirmSubmit(false);
      setExpiresAt(Date.now() + data.expires_in_seconds * 1000); setRemaining(data.expires_in_seconds);
    } catch (cause) { handleError(cause); }
    finally { setBusy(null); requestInFlight.current = false; }
  }
  async function grade() {
    if (!quiz || requestInFlight.current || remaining === 0) return;
    requestInFlight.current = true; setBusy("grade"); setError(null);
    try {
      const data = await post<Grade>("grade", { quiz_id: quiz.quiz_id, grading_token: quiz.grading_token,
        answers: quiz.questions.map(question => ({ question_id: question.id, answer: typeof answers[question.id] === "string" ? (answers[question.id] as string).trim() || null : answers[question.id] ?? null })) });
      setResult(data); setConfirmSubmit(false);
    } catch (cause) { handleError(cause); }
    finally { setBusy(null); requestInFlight.current = false; }
  }
  function reset() {
    if (busy || (quiz && !result && !window.confirm("현재 풀이 중인 퀴즈를 닫고 새 퀴즈를 만들까요?"))) return;
    setQuiz(null); setResult(null); setAnswers({}); setError(null); setConfirmSubmit(false); setExpiresAt(0);
  }

  return <div className="app-shell">
    <header className="site-header"><div className="header-inner">
      <a className="brand" href="/" aria-label="QuizForge 홈"><span className="brand-mark">Q<span /></span>QuizForge<span className="brand-divider" /><span className="brand-caption">학습 퀴즈</span></a>
      <button type="button" className="new-quiz" disabled={!!busy} onClick={reset}><span aria-hidden="true">＋</span> 새 퀴즈</button>
    </div></header>
    <main className="page-container">
      <nav className="stepper" aria-label="학습 단계"><span className={stage === "create" ? "active" : "done"}><b>{stage === "create" ? "1" : "✓"}</b>입력·설정</span><i /><span className={stage === "solve" ? "active" : stage === "result" ? "done" : ""}><b>{stage === "result" ? "✓" : "2"}</b>문제 풀이</span><i /><span className={stage === "result" ? "active" : ""}><b>3</b>채점 결과</span></nav>
      <div className="page-heading"><div>
        <h1 ref={heading} tabIndex={-1}>{stage === "create" ? "퀴즈 생성" : stage === "solve" ? "문제 풀이" : "채점 결과"}</h1>
        <p className="heading-description">{stage === "create" ? "주제나 학습자료를 입력하고 출제 조건을 선택하세요." : stage === "solve" ? "문항별 답안을 입력하세요. 정답과 해설은 제출 후 표시됩니다." : "점수와 문항별 정답, 해설을 확인하세요."}</p></div></div>

      {visibleError ? <div role="alert" className="error-banner"><strong>{paused && stage === "create" ? "퀴즈 생성 중지" : "요청을 확인해주세요"}</strong><p>{visibleError.message}</p>{paused && stage === "create" ? <button type="button" className="text-button" onClick={() => { setPaused(false); setError(null); }}>생성 재개</button> : null}</div> : null}

      {stage === "create" ? <form onSubmit={generate}>
        <fieldset disabled={!!busy} className="workbench">
          <section className="panel source-panel" aria-labelledby="source-title"><div className="panel-heading"><div><span className="section-index">01</span><h2 id="source-title">학습 내용</h2></div><span className="subtle-tag">입력</span></div>
            <div className="mode-tabs" aria-label="학습 내용 입력 방식"><button type="button" aria-pressed={mode === "topic"} onClick={() => {setMode("topic");setError(null);}}>주제 입력</button><button type="button" aria-pressed={mode === "text"} onClick={() => {setMode("text");setError(null);}}>텍스트·TXT</button></div>
            {mode === "text" ? <div className="file-import"><button className="secondary-button" type="button" onClick={() => fileInput.current?.click()} disabled={!!busy}>{busy === "import" ? "파일 읽는 중…" : "TXT 파일 불러오기"}</button><input hidden ref={fileInput} type="file" accept=".txt,text/plain" aria-label="TXT 파일 선택" onChange={importTxt} /><span>{sourceFile ? `불러온 파일: ${sourceFile}` : "UTF-8 · 100KB 이하"}</span><p>파일을 불러온 뒤 내용을 확인·수정할 수 있습니다. 퀴즈 생성 시 텍스트가 서버와 Gemini로 전송됩니다.</p></div> : null}
            <div className="source-field"><label htmlFor="learning-source">{mode === "topic" ? "학습 주제" : "학습 텍스트"}<span>{mode === "topic" ? "2자 이상" : "20자 이상"}</span></label>
              <textarea key={mode} id="learning-source" value={currentValue} onChange={event => { if (mode === "topic") setTopic(event.target.value); else { setText(event.target.value); setSourceFile(null); } }} minLength={mode === "topic" ? 2 : 20} maxLength={maxSourceLength * 2} required placeholder={mode === "topic" ? "학습 주제를 입력하세요.\n예: Python 리스트와 튜플의 차이" : "학습 내용을 붙여 넣거나 TXT 파일을 불러오세요.\n입력한 내용을 기준으로 문제를 생성합니다."} />
              <div className="input-meta"><span>{mode === "topic" ? "입력한 주제의 일반 지식을 기준으로 출제합니다." : "직접 입력 또는 UTF-8 TXT 파일 · 최대 20,000자"}</span><span>{sourceLength.toLocaleString()} / {maxSourceLength.toLocaleString()}</span></div>
              {sourceLength > maxSourceLength ? <p className="field-error">최대 {maxSourceLength.toLocaleString()}자까지 입력할 수 있습니다.</p> : null}
            </div>
            {mode === "topic" ? <div className="suggestions"><span>주제 예시</span><div>{["Python 자료형", "HTTP와 REST API", "객체지향의 기본 원칙"].map(item => <button type="button" key={item} onClick={() => setTopic(item)}>{item}</button>)}</div></div> : null}
            <div className="source-note"><span className="note-icon" aria-hidden="true">i</span><div><strong>{mode === "topic" ? "주제 기반 출제" : "자료 기반 출제"}</strong><p>{mode === "topic" ? "주제 기반 문제에는 학습자료의 원문 근거가 포함되지 않습니다." : "제출 후 해설에서 입력한 원문의 인용과 위치를 확인할 수 있습니다."}</p></div></div>
            <div className="privacy-box"><label className="check-label"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} required /><span>입력 내용을 Google Gemini로 전송하는 데 동의합니다.</span></label><p>무료 구간의 입력은 Google 제품 개선에 사용될 수 있습니다.<br />개인정보나 회사 내부 자료는 입력하지 마세요.</p></div>
          </section>
          <aside className="panel settings-panel" aria-labelledby="settings-title"><div className="panel-heading"><div><span className="section-index">02</span><h2 id="settings-title">출제 설정</h2></div><span className="subtle-tag">설정</span></div>
            <div className="setting-block"><span className="field-label">문항 수</span><div className="count-options">{([5, 10, 15, 20] as const).map(count => <button type="button" aria-pressed={settings.count === count} onClick={() => updateSetting("count", count)} key={count}>{count}<small>문항</small></button>)}</div></div>
            <div className="setting-grid"><label>난이도<select value={settings.difficulty} onChange={event => updateSetting("difficulty", event.target.value as GenerationSettings["difficulty"])}><option value="easy">쉬움</option><option value="medium">보통</option><option value="hard">어려움</option><option value="mixed">혼합</option></select></label><label>출제 방식<select value={settings.approach} onChange={event => updateSetting("approach", event.target.value as GenerationSettings["approach"])}><option value="concepts">핵심 개념</option><option value="application">이해·응용</option><option value="balanced">골고루</option></select></label></div>
            <fieldset className="type-fieldset"><legend>문제 유형 <span>복수 선택 가능</span></legend><div className="type-options">{(Object.keys(typeLabels) as QuestionType[]).map(type => <label key={type} className={settings.question_types.includes(type) ? "checked" : ""}><input type="checkbox" checked={settings.question_types.includes(type)} onChange={() => toggleType(type)} /><span>{typeLabels[type]}</span></label>)}</div>{settings.question_types.length === 0 ? <p className="field-error">한 가지 이상 선택해주세요.</p> : null}</fieldset>
            <label className="setting-block">해설 수준<select value={settings.explanation_level} onChange={event => updateSetting("explanation_level", event.target.value as GenerationSettings["explanation_level"])}><option value="brief">간단</option><option value="detailed">자세히</option></select></label>
            <div className="scope-row"><span>출제 범위</span><span>입력 전체</span></div>
            <div className="generate-area"><div className="selection-summary"><span>{settings.count}문항</span><i />{settings.question_types.map(type => typeLabels[type]).join(" · ") || "유형 선택 필요"}</div><button className="primary-button" type="submit" disabled={!!busy || paused || !settings.question_types.length || sourceLength > maxSourceLength}>{busy === "generate" ? <><span className="spinner" aria-hidden="true" />퀴즈 생성 중</> : paused ? "생성 중지" : "퀴즈 생성"}</button><p role="status" aria-live="polite">{busy === "generate" ? "생성에 최대 1분이 걸릴 수 있습니다." : "정답과 해설은 제출 후 표시됩니다."}</p></div>
          </aside>
        </fieldset>
        <div className="bottom-note">AI 생성 문제에는 오류가 있을 수 있습니다. 중요한 내용은 원문과 대조하세요.</div>
      </form> : null}

      {stage === "solve" && quiz ? <div className="solve-layout"><section className="questions" aria-label="퀴즈 문제">
        <fieldset disabled={!!busy || remaining === 0}><legend className="sr-only">답안 작성</legend>{quiz.questions.map(question => <article key={question.id} className="question-card"><div className="question-top"><span className="question-number">{String(question.id).padStart(2, "0")}</span><span className="type-tag">{typeLabels[question.type]}</span></div><h2>{question.prompt}</h2><QuestionInput question={question} value={answers[question.id] ?? null} onChange={answer => {setAnswers(previous => ({...previous, [question.id]: answer}));setConfirmSubmit(false);}} /></article>)}</fieldset>
      </section><aside className="panel session-panel"><h2>풀이 현황</h2><div className="answered-count"><strong>{answered}</strong><span> / {quiz.questions.length}문항 작성</span></div><progress max={quiz.questions.length} value={answered} aria-label="답안 작성 진행" /><div className="question-map" aria-label="문항별 작성 여부">{quiz.questions.map(question => <span key={question.id} className={answers[question.id] !== undefined && answers[question.id] !== null && String(answers[question.id]).trim() !== "" ? "filled" : ""} aria-label={`${question.id}번 ${answers[question.id] !== undefined && answers[question.id] !== null && String(answers[question.id]).trim() !== "" ? "작성" : "미작성"}`}>{question.id}</span>)}</div><div className="time-label">{remaining > 0 ? <>제출 가능 시간 <strong>{Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}</strong></> : "제출 시간이 만료되었습니다."}</div><p className="session-help">미응답은 오답으로 처리됩니다. 제출 후 정답과 해설이 공개됩니다.</p>
        {confirmSubmit ? <div className="submit-confirm" role="group" aria-label="미응답 제출 확인"><strong>{quiz.questions.length - answered}문항이 미응답입니다.</strong><p>미응답 문항을 포함해 제출하시겠습니까?</p><button type="button" className="primary-button" disabled={!!busy || remaining === 0} onClick={grade}>{busy === "grade" ? "채점 중…" : "미응답 포함 제출"}</button><button className="text-button" type="button" disabled={!!busy} onClick={() => setConfirmSubmit(false)}>계속 풀기</button></div> : <button className="primary-button" type="button" disabled={!!busy || remaining === 0} onClick={() => answered < quiz.questions.length ? setConfirmSubmit(true) : void grade()}>{busy === "grade" ? "채점 중…" : "답안 제출"}</button>}
        <button type="button" className="text-button" disabled={!!busy} onClick={reset}>풀이 종료</button><p className="session-help">새로고침하거나 탭을 닫으면 현재 풀이가 삭제됩니다.</p></aside></div> : null}

      {stage === "result" && result ? <><section className="panel result-summary" aria-label="채점 요약"><div><h2>채점 요약</h2><p>{result.total_questions}문항 중 <strong>{result.correct_count}문항 정답</strong> · {result.total_questions - result.correct_count}문항 오답</p><button className="secondary-button" type="button" onClick={reset}>새 퀴즈 </button></div><div className="score-ring"><span><strong>{result.score_percent}</strong>점</span></div></section><div className="results-heading"><h2>정답과 해설</h2><span>문항별 채점 결과</span></div><div className="result-list">{result.results.map(question => <ResultQuestion key={question.id} question={question} />)}</div><div className="bottom-note">{result.notice}</div></> : null}
    </main>
    <footer className="site-footer"><span>QuizForge</span><span>학습자료 기반 퀴즈 생성 및 채점</span><span>Gemini 기반 생성</span></footer>
  </div>;
}
