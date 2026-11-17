# QuizForge

Python/FastAPI 기반 AI 퀴즈 백엔드 포트폴리오입니다. Python 3.13.15를 사용합니다.
Phase 1 Health API, Phase 2 텍스트·주제 기반 생성 API, Phase 3 서버 채점 API를 구현했습니다.
Phase 4에서는 Next.js 프런트엔드를 추가했습니다. 가이드 시안의 보라색 계열과
워크벤치 시안의 좌우 배치를 사용합니다. Phase 5에서는 TXT 파일 불러오기를 추가했습니다.
PDF/PPTX/DOCX/이미지 파서, DB, 인증, 배포는 아직 없습니다.

## TXT 파일 입력 — Phase 5

웹 화면에서 **텍스트·TXT → TXT 파일 불러오기**를 선택합니다.
파일은 브라우저에서 읽고 텍스트 입력란에 표시합니다. 파일 원본을 서버에 업로드하거나
디스크에 저장하지 않습니다. 내용을 확인·수정하고 외부 AI 전송에 동의한 뒤
퀴즈 생성을 눌러야 텍스트가 기존 생성 API를 거쳐 Gemini로 전송됩니다.

- UTF-8 TXT만 지원하며 UTF-8 BOM은 처리합니다. UTF-16/CP949 자동 변환은 하지 않습니다.
- 파일 최대 100,000바이트(100KB), 양끝 공백 제거 후 20~20,000자
- 잘못된 인코딩, 텍스트가 아닌 제어 문자, 길이·크기 초과를 거부합니다.
- 파일을 다시 불러오면 기존 입력 교체를 확인합니다. 읽기 실패 시 기존 내용은 유지합니다.
- 파일 이름과 내용은 현재 탭에만 유지하며 파일 이름은 생성 API로 전송하지 않습니다.
- TXT에는 페이지/슬라이드 번호가 없으므로 출제 범위는 입력 전체입니다.
- TXT 근거 위치는 불러온 뒤 편집하고 양끝 공백을 제거한 최종 텍스트를 기준으로 합니다.

브라우저에서는 `File.arrayBuffer()`와 UTF-8 `TextDecoder`를 사용합니다.
추가 패키지나 파일 저장 계층 없이 기존 텍스트 생성/채점 흐름을 재사용했습니다.
서버의 입력 검증과 자원 제한은 그대로 적용됩니다. PDF 등에는 이후 서버 파서를 추가할 예정입니다.

화면의 화살표 버튼 아이콘과 홍보성 문구를 제거하고 퀴즈 생성/문제 풀이/채점 결과로
기능명을 표시합니다. 개인정보·외부 AI 전송·정답 오류 가능성에 관한 안내는 유지합니다.

```powershell
cd C:\dev\QuizForge\frontend
npm test
npm run typecheck
npm run build
```

2026-11-18 검증: TXT 테스트 9개 통과, 백엔드 테스트 112개 통과(기존 경고 1개).
브라우저에서 정상 TXT 불러오기, 잘못된 인코딩의 거부 및 기존 내용 보존,
모킹 생성 → 답안 제출 → 1/5 정답 20점 → 원문 근거 표시를 확인했습니다.
이번 단계에서도 실제 Gemini 호출은 하지 않았습니다.
주요 파일은 frontend/lib/text-file.ts, frontend/tests/text-file.test.ts,
frontend/app/page.tsx입니다. 테스트는 기존 TypeScript 컴파일러와 Node 내장 테스트 도구로 실행합니다.

## 웹 화면 실행 — Phase 4

백엔드는 아래 기존 실행 방법으로 **8000번 포트에서 한 번만** 실행합니다.
이미 실행 중이면 같은 포트에 서버를 추가로 띄우지 마세요. Gemini/API 암호화 키는
백엔드를 실행하는 PowerShell에 설정하며 프런트엔드에 복사하지 않습니다.

새 PowerShell에서:

```powershell
cd C:\dev\QuizForge\frontend
npm ci
npm run dev -- --port 3002
```

웹 화면: <http://127.0.0.1:3002>. Node.js 20.9 이상이 필요하며 Node.js 24.21.0에서 확인했습니다.
3000/3001번 포트의 기존 서비스를 건드리지 않도록 3002번을 사용합니다.

브라우저 → Next.js의 /api rewrites → FastAPI → Gemini(생성만) 또는 서버 채점 → 화면 순서로 동작합니다.
프런트엔드는 기본적으로 http://127.0.0.1:8000에 연결합니다. 다른 주소가 필요하면
frontend/.env.local에 QUIZFORGE_API_ORIGIN을 설정하고 Next.js를 재시작합니다.
이 값은 서버 전용입니다. GEMINI_API_KEY와 QUIZFORGE_TOKEN_KEY는 프런트엔드에 넣지 마세요.
같은 출처의 /api 요청을 사용하므로 백엔드 CORS 허용 범위를 넓히지 않았습니다.

지원 흐름:

- 주제/텍스트 입력, 출제 설정, 외부 AI 전송 동의 → 실제 생성 API 호출
- 중복 클릭 방지, 생성 대기 표시, 안전한 API 오류 안내
- 객관식/OX/단답형 풀이, 작성 문항 수, 약 1시간의 제출 가능 시간 안내
- 미응답 제출 확인 → 실제 서버 채점 → 점수, 정답, 해설, 텍스트 모드 원문 근거
- 429 또는 생성 중지 응답 시 생성 버튼 비활성화; 사용자가 직접 열기 전 자동 재시도 없음
- 좁은 화면에서는 입력/설정을 세로로 배치

생성 버튼을 누르면 실제 Gemini를 호출할 수 있습니다. 화면 확인만으로는 호출하지 않습니다.
생성 응답에는 평문 정답/해설이 없으며 채점 성공 응답을 받은 뒤에만 결과 화면에서 표시합니다.
퀴즈·암호화 토큰·답안은 현재 탭의 React 상태에만 보관하며 localStorage/쿠키/URL에 저장하지 않습니다.
새로고침이나 탭 종료 시 풀이가 사라집니다. 서버의 정답 저장은 기존 인증 암호화 토큰 방식을 유지합니다.
앱은 서비스의 결제 등급을 확인하지 못하므로 Gemini 프로젝트의 Free 등급을 별도로 유지해야 합니다.

프런트엔드 파일:

| 파일 | 역할 |
| --- | --- |
| frontend/app/page.tsx | 입력 → 풀이 → 결과 상태와 화면, 서버 요청 연결 |
| frontend/lib/api.ts | API 타입, 60초 클라이언트 제한, 오류 코드별 안전한 안내 |
| frontend/app/globals.css | 보라색 팔레트, 워크벤치 배치, 모바일 스타일 |
| frontend/app/layout.tsx | 한국어 문서와 메타데이터 |
| frontend/next.config.ts | 고정 API 경로만 백엔드로 전달; 로컬 프록시 제한 55초 |
| frontend/package-lock.json | 재현 가능한 npm 의존성 잠금 |

Next.js의 서버/클라이언트 분리로 layout은 Server Component이며, 상태·입력·이벤트가 있는
page는 Client Component입니다. Spring 관점에서 브라우저는 화면 상태를 관리하고,
업무 검증과 채점은 기존 FastAPI Controller/Service가 담당합니다.
프런트엔드에는 비밀키나 정답 생성 로직이 없습니다.
이번에 Next.js/React/React DOM, TypeScript 및 타입 정의, Tailwind CSS/PostCSS를 추가했습니다.
별도 UI 라이브러리, 전역 상태 관리 라이브러리, AI SDK는 추가하지 않았습니다.

검사 명령:

```powershell
cd C:\dev\QuizForge\frontend
npm run typecheck
npm run build
```

### 비용 없는 브라우저 QA

실제 앱에는 예시 응답으로 성공하는 fallback이 없습니다. 별도 테스트 서버만 Gemini를 모킹합니다.

```powershell
# 프로젝트 루트의 별도 터미널: 실제 생성용 서버와 구분해서 실행
cd C:\dev\QuizForge
& .\.venv\Scripts\python.exe -m uvicorn ui_mock_server:app --app-dir tests --host 127.0.0.1 --port 18012
```

```powershell
# 프런트엔드 QA용 터미널: 실제 화면 서버와 동시에 같은 .next 폴더를 사용하지 마세요.
cd C:\dev\QuizForge\frontend
$env:QUIZFORGE_API_ORIGIN = "http://127.0.0.1:18012"
npm run dev -- --port 3100
```

테스트 문제/해설에는 테스트 데이터임을 표시합니다. 주제 '테스트:한도초과'는 429를 반환합니다.
그 외 요청은 요청한 개수/유형에 맞춘 고정 문제를 반환하고, 암호화와 채점은 실제 로직을 사용합니다.
QA 종료 시 두 테스트 서버를 종료하세요. 실제 사용 화면은 별도 터미널에서
QUIZFORGE_API_ORIGIN이 기본 실제 백엔드 주소인지 확인한 뒤 실행합니다.
2026-11-18 브라우저 검증에서 세 유형 혼합 퀴즈 3/5 정답 → 60점, 미응답 확인,
텍스트 모드 제출 후 근거 표시, 429 생성 중지/수동 재개, 390px/320px의 세로 배치를 확인했습니다.
최종 npm run typecheck 및 npm run build가 통과했고 npm 설치 감사에서 알려진 취약점은 0개였습니다.
기존 백엔드 회귀 테스트도 112 passed, 1 warning입니다(기존 Starlette 경고 유지).
이번 프런트엔드 작업에서는 실제 Gemini를 호출하지 않았습니다.

## 로컬 실행 (Windows PowerShell)

```powershell
cd C:\dev\QuizForge
py -3.13 -m uv sync

$geminiKey = Read-Host "Gemini API 키" -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", $geminiKey).Password
Remove-Variable geminiKey

# 최초 한 번 생성 후 유지. 다시 생성하면 이전 퀴즈 토큰은 복호화할 수 없습니다.
$env:QUIZFORGE_TOKEN_KEY = (& .\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
$env:QUIZFORGE_GENERATION_ENABLED = "true"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

서버는 키를 설정한 같은 PowerShell에서 실행하세요. 가상환경 활성화 여부와 무관하게
위 명령은 동작합니다. uv는 시스템 Python에 설치되어 있어 py -3.13 -m uv로 실행하고,
Uvicorn과 pytest는 프로젝트 가상환경 Python으로 직접 실행합니다.
환경변수는 다른 터미널/Codex에
자동 공유되지 않습니다. 키를 채팅·소스·Git에 넣지 마세요.
.env.example은 항목 안내이며 앱은 .env를 자동으로 읽지 않습니다.
.env와 .env.*는 Git 제외 대상입니다(.env.example 제외).
서버 재시작 후에도 기존 퀴즈를 유지하려면 TOKEN_KEY를 안전한 서버 비밀 저장소에 보관하고
동일한 값을 설정하세요. 서버리스의 모든 인스턴스도 동일한 키를 사용해야 합니다.

- Health: <http://127.0.0.1:8000/api/health> → {"status":"ok"}
- Swagger: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>
- 종료: Ctrl+C

키가 없어도 Health와 모킹 테스트는 동작합니다. 생성은 Gemini/API 암호화 키가 모두 필요하고,
채점은 생성 시 사용한 암호화 키만 필요합니다. 필요한 키가 없으면 해당 API는 503을 반환합니다.

## 생성 API

POST /api/quizzes/generate 요청 예시입니다. 실제 실행하면 Google로 입력이 전송됩니다.
무료 구간의 입력은 제품 개선에 사용될 수 있으므로 공개 자료를 사용하고 개인정보·기밀을
보내지 마세요. external_ai_consent: true가 필수입니다.

```json
{
  "mode": "topic",
  "topic": "Python 리스트와 튜플의 차이",
  "external_ai_consent": true,
  "settings": {
    "count": 5,
    "difficulty": "medium",
    "question_types": ["multiple_choice", "true_false", "short_answer"],
    "approach": "balanced",
    "explanation_level": "brief",
    "scope": "all"
  }
}
```

자료 기반은 mode를 text로 바꾸고 topic을 제거한 뒤 text를 넣습니다.
양끝 공백 제거 후 텍스트는 20~20,000자, 주제는 2~200자입니다.
두 입력 동시 사용, 파일·페이지 필드, 알 수 없는 필드는 422로 거부합니다.

| 설정 | 허용 값 |
| --- | --- |
| count | 5 / 10 / 15 / 20 |
| difficulty | easy(쉬움) / medium(보통) / hard(어려움) / mixed(혼합) |
| question_types | multiple_choice(4지선다) / true_false(OX) / short_answer(단답형); 중복 없이 복수 선택 |
| approach | concepts(핵심 개념) / application(이해·응용) / balanced(골고루) |
| explanation_level | brief(간단) / detailed(자세히) |
| scope | all(현재 입력 전체)만 지원; 페이지·슬라이드 지정 미지원 |

모델은 gemini-3.1-flash-lite로 고정합니다. latest 별칭, 유료 대체 모델, 검색 도구를 사용하지 않습니다.
난이도·출제 방식·해설 수준은 프롬프트로 전달하며 의미상의 준수 여부까지 보장하지 않습니다.
문항 수, 요청 유형(각 선택 유형 최소 1개), 중복 문제, 선택지 정확히 4개·공백·중복,
유형별 정답 형식과 필수 해설을 서버에서 검증합니다.
객관식 정답은 0~3 정수, OX는 boolean, 단답형은 비어 있지 않은 문자열입니다.

텍스트 기반은 원문 인용과 Python 문자 위치 [start, end)를 필수로 받습니다.
양끝 공백 제거 후 입력의 실제 부분 문자열과 인용문이 같은지 검사합니다.
페이지 번호나 UTF-16 위치가 아닙니다. 주제 기반 evidence는 반드시 null입니다.
**구조 검증과 인용 위치 검증은 사실적 정확성이나 근거의 의미적 적합성을 보장하지 않습니다.**

## 정답 보호

응답은 quiz_id, questions(id/type/prompt/options), grading_token,
expires_in_seconds(3600), AI 생성 안내문만 포함합니다.
정답·해설·원문 근거는 공개 필드에서 제외합니다.
문제/선택지에 정답·해설을 쓰지 않도록 모델에 지시하지만 의미상 정답 암시를
완벽하게 자동 탐지하는 기능은 없습니다.

grading_token은 전체 문제·정답·해설·근거·quiz_id·버전을 Fernet으로 인증 암호화합니다.
서명만 된 JWT와 달리 내용이 읽히지 않으며 변조 검증과 1시간 만료 검증을 제공합니다.
생성 시각과 대략적인 길이는 숨기지 않습니다. 서버 메모리에 정답을 저장하지 않습니다.
토큰에는 전체 원문이나 API 키를 넣지 않습니다. 생성 응답은 Cache-Control: no-store입니다.
서버 비밀키를 잃으면 기존 토큰은 복호화할 수 없습니다.

Phase 3 채점 API는 토큰을 서버에서 검증·복호화하고 내장 문제와 ID로 채점합니다.
클라이언트가 수정한 문제/정답은 받지 않습니다. 별도 복호화 API도 없습니다.
DB·인증이 없어 사용자 소유권, 일회성 제출, 재사용 차단은 제공하지 않습니다.

## 채점 API — Phase 3

`POST /api/quizzes/grade`는 Gemini 호출 없이 서버에서 채점합니다.
생성이 중지되거나 무료 사용량이 소진돼도, 암호화 키가 같고 토큰이 유효하면 채점할 수 있습니다.
생성 응답의 quiz_id와 grading_token을 그대로 보내고 공개 questions의 id에 답안을 연결합니다.
모든 문제를 한 번씩 포함해야 하며 미응답은 null로 제출합니다.
아래 예시의 quiz_id와 grading_token은 실제 생성 응답의 값으로 교체하세요.

```json
{
  "quiz_id": "00000000-0000-0000-0000-000000000000",
  "grading_token": "생성 응답의 grading_token 전체를 여기에 붙여 넣으세요",
  "answers": [
    {"question_id": 1, "answer": 0},
    {"question_id": 2, "answer": 2},
    {"question_id": 3, "answer": 1},
    {"question_id": 4, "answer": 3},
    {"question_id": 5, "answer": null}
  ]
}
```

위 예시는 객관식 5문항 기준입니다. **선택지는 0부터 셉니다**(첫 번째=0, 네 번째=3).
OX는 true/false boolean, 단답형은 문자열을 사용합니다. 문자열 "true"나 숫자 1은 OX 답안이 아닙니다.
중복/누락/알 수 없는 문항 ID, 유형에 맞지 않는 답안, 문제·정답을 덧붙인 요청은 422입니다.
단답형은 Unicode NFC, 대소문자, 양끝/연속 공백을 정규화한 후 정확 일치로 비교합니다.
문장부호·동의어·띄어쓰기 유무·부분 일치·의미적 유사성을 판정하지 않습니다.

성공 응답은 quiz_id, total_questions, correct_count, score_percent,
results(문항·제출 답안·정오·정답·해설·근거), 채점 방식 안내를 포함합니다.
모든 문항은 같은 배점이며 score_percent는 정답 수/전체 수 × 100을 소수 둘째 자리로 반올림합니다.
미응답은 오답입니다. 저장된 AI 정답과의 일치 여부이지 사실성 재검증은 아닙니다.
오류 응답에서는 정답·해설·토큰을 공개하지 않고 성공한 전체 제출 후에만 공개합니다.
전체 미응답 제출도 최종 제출로 취급하며, 정답 공개 후 재제출을 차단하지 않습니다.
토큰을 가진 누구나 제출할 수 있습니다. 시험 부정행위 방지가 필요한 서비스에는 DB/인증이 필요합니다.

Swagger 사용 순서:

1. 서버 실행 후 /docs를 새로고침합니다. 자동 reload 시 암호화 키를 다시 생성하지 마세요.
2. 기존에 생성한 퀴즈가 1시간 이내이고 같은 키를 사용했다면 그 응답을 재사용할 수 있습니다.
3. POST /api/quizzes/grade → Try it out을 누릅니다.
4. Request body에 실제 quiz_id, grading_token, 문항별 답안을 입력하고 Execute를 누릅니다.
5. Server response의 200과 correct_count/score_percent/results를 확인합니다.

채점은 외부 호출 비용이 없습니다. 만료되거나 키를 바꾼 토큰은 400 invalid_token입니다.
이 경우 새 퀴즈 생성은 별도의 실제 Gemini 호출을 발생시킵니다.

## 무료 한도와 중지

AI Studio에서 Free 등급을 확인하고 **결제 계정을 연결하지 마세요**.
앱은 Google 결제 상태나 무료 잔량을 확인하지 못합니다.
유료 프로젝트의 키를 쓰면 같은 모델이라도 과금될 수 있습니다.

Gemini가 429를 반환하면 API도 quota_exhausted 코드와 429를 반환합니다.
한도에 걸린 생성은 일시 이용 불가이며 자동 재시도·모델 전환은 없습니다. Health와 채점은 유지됩니다.
이후 사용자의 새 요청에는 한 번만 호출하며 Google 한도가 해제되면 생성이 재개됩니다.
분당/일일 제한의 복구 시점은 다르므로 임의의 복구 시간을 표시하지 않습니다.
DB 없이 전 인스턴스의 차단 상태를 저장하지 않고 메모리 차단에도 의존하지 않습니다.

운영자가 전체 생성을 중지하려면 아래 값을 설정하고 해당 PowerShell에서 서버를 재시작합니다.

```powershell
$env:QUIZFORGE_GENERATION_ENABLED = "false"
```

## 제한과 오류

- 생성 본문 128,000바이트 / 채점 본문 600,000바이트 제한(파싱 전, chunked 포함)
- 채점 토큰 최대 400,000자, 답안 최대 20개, 단답형 최대 2,000자
- 외부 요청 전체 45초, HTTP 읽기 40초/연결 5초, 최대 출력 12,000토큰
- 외부 응답 최대 256,000바이트, 차단/미완료/잘못된 JSON 거부
- 요청당 외부 호출 1회, 자동 재시도 없음
- 413 본문 초과 / 422 요청 오류 / 429 사용량 제한
- 400 토큰 변조·만료·잘못된 키·quiz_id 불일치(토큰 형식/버전 오류 포함)
- 502 외부 연결 실패·잘못된 출력 / 503 설정 누락·중지·권한 문제 / 504 시간 초과

오류는 안전한 error.code와 error.message만 반환합니다.
오류에 원문·정답·외부 오류 본문·키를 반환하거나 앱 로그에 기록하지 않습니다.
FastAPI 기본 검증 오류의 입력 에코도 제거했습니다.
HTTP 디버그/프록시 로그에 키·본문이 남지 않도록 운영해야 합니다.
공개 배포 전 인증·접근 제한·분산 사용량 제한이 필요합니다. 현재는 로컬 MVP입니다.

## 구조와 Spring 비교

| 파일 | 책임 | Spring 대응 개념 |
| --- | --- | --- |
| app/main.py | 앱 조립, 오류 응답, 본문 제한 | 설정 클래스 / ControllerAdvice / Filter |
| app/api/health.py, app/api/quizzes.py | 요청/HTTP 응답, 의존성 연결 | RestController / 생성자 주입 |
| app/schemas/health.py, app/schemas/quiz.py | 요청·AI 내부·공개 응답 모델 | DTO / Bean Validation |
| app/quiz_service.py | 생성 흐름과 출력 검증 | Service |
| app/grading_service.py | 토큰 검증과 결정적 채점 | Service |
| app/ai.py | 최소 Protocol과 Gemini REST 호출 | 외부 클라이언트 인터페이스와 구현 |
| app/core.py | 환경변수, 안전한 예외, 암호화 | ConfigurationProperties / 도메인 예외 |

Depends(get_quiz_service)가 요청마다 서비스를 구성하고 테스트는 dependency_overrides로 교체합니다.
서비스는 SDK 대신 generate(request) → JSON 문자열 Protocol에 의존합니다.
Pydantic은 신뢰 경계에서 검증하고 공개 응답 DTO를 따로 만들어 정답 필드를 제외합니다.
비동기 HTTPX 호출 동안 이벤트 루프는 다른 요청을 처리할 수 있습니다.
채점 서비스는 외부 AI Provider에 의존하지 않습니다. Spring Service에서 토큰을 검증한 뒤
저장된 정답과 제출 DTO를 비교하는 것과 같습니다. GradingService를 Depends로 주입합니다.

## 의존성과 테스트

- 기존 FastAPI / Pydantic / Uvicorn: HTTP API, 검증, 서버
- HTTPX: 기존 테스트 의존성을 실행 의존성으로 이동, Gemini REST 호출에도 사용
- cryptography: 직접 암호를 구현하지 않고 Fernet 인증 암호화 사용
- 기존 pytest: 테스트 실행; Google SDK, DB, Redis 등 추가하지 않음

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

자동 테스트는 FakeProvider와 HTTPX MockTransport를 사용해 비용 없이 실행합니다.
2026-11-17 Phase 2 실행: 73 passed, 1 warning.
Phase 3 실행: **112 passed, 1 warning**. 추가 패키지는 없습니다. uv lock --check도 통과했습니다.
별도 Uvicorn 프로세스와 테스트용 암호화 토큰으로 실제 HTTP 채점 200(5/5, 100%),
변조 토큰 400, 생성 중지 503, Health 200을 확인했습니다. 외부 AI는 호출하지 않았습니다.
실제 Uvicorn 프로세스의 Health 200 및 생성 수동 중지 503을 HTTP로 확인했습니다.
수정한 텍스트 파일은 BOM 없는 UTF-8로 저장합니다.
Phase 1 테스트 5개를 유지합니다. 입력·설정, AI 출력, 한도·실패·시간 초과,
정답 비노출, 토큰 변조·만료, HTTP 상태코드를 검사합니다.
Phase 3는 생성 토큰→채점 흐름, 세 유형, 공백/대소문자/Unicode 정규화,
오답·미응답·점수, ID/유형 오류, 변조·만료·키/퀴즈 불일치, 비밀 비노출을 검사합니다.
Starlette TestClient의 HTTPX 사용 중단 경고를 숨기거나 의존성을 임의 변경하지 않았습니다.

Phase 1은 Python 3.13.15 테스트, Uvicorn 실행 및 사용자 Swagger 200 확인이 완료됐습니다.
2026-11-17 사용자가 Swagger에서 실제 Gemini 주제 모드(리스트와 튜플, 객관식 5문항)를
실행하고 성공 응답을 제공했습니다. 5문항·각 4개 선택지·암호화 토큰과 평문 정답/해설 제외를
응답에서 확인했습니다. 텍스트 모드와 OX/단답형의 실제 모델 호출은 아직 미검증입니다.
실제 반환 정답은 복호화하지 않았고 정답 정확성이나 전체 생성 품질을 보증하지 않습니다.
모킹 테스트와 실제 모델 호출 검증을 구분합니다.
초기 작업 폴더는 .git 없는 복사본이었습니다. 2026-11-18 원격 main의 초기 커밋
92b1c7d25e320e6b1014c25308f91e8489dd829b(README만 추적)을 가져와 로컬 Git 이력을 연결했습니다.
기존 소스 파일은 덮어쓰지 않았습니다. 원격 주소는 https://github.com/orca305/QuizForge.git 입니다.
현재 커밋/동기화 상태는 git status와 git log -1로 확인할 수 있습니다. 배포는 하지 않았습니다.
다른 PC에서 이어서 작업할 때는 [인수인계 문서](docs/HANDOFF.md)를 참고하세요.

## 공식 문서와 다음 단계

[Gemini 키](https://ai.google.dev/gemini-api/docs/api-key),
[REST API](https://ai.google.dev/api/generate-content),
[구조화 출력](https://ai.google.dev/gemini-api/docs/structured-output),
[요금/데이터 조건](https://ai.google.dev/gemini-api/docs/pricing),
[한도](https://ai.google.dev/gemini-api/docs/rate-limits),
[Fernet](https://cryptography.io/en/latest/fernet/).

다음 파일 입력 단계는 텍스트형 PDF의 추출 및 페이지별 출제 범위입니다.
스캔 PDF/OCR, PPTX/DOCX/이미지 입력은 그 이후로 확장합니다.
실제 Gemini 생성 품질 검증은 호출 범위를 정한 뒤 진행하며 배포는 별도 단계입니다.
