# QuizForge 작업 인수인계

기준일: 2026-11-18 (한국 시간)

## 현재 상태

- 저장소: https://github.com/orca305/QuizForge.git / main
- 데스크톱 작업 위치: C:\dev\QuizForge
- Python 3.13.15 / uv 0.13.9 / FastAPI / Pydantic v2
- Next.js 16.4.6 / React 19.3.1 / TypeScript / Tailwind CSS 4
- 프런트엔드: 가이드 시안의 보라색, 워크벤치 시안의 좌우 배치
- 버튼 화살표와 홍보성 문구 제거, 기능 중심의 한국어 문구 적용

## 구현된 기능

1. GET /api/health
2. POST /api/quizzes/generate: 텍스트·주제 입력, Gemini 단일 제공업체, 요청 및 AI 결과 검증
3. POST /api/quizzes/grade: 암호화 토큰 검증, 세 유형의 서버 채점, 제출 후 정답·해설·근거 반환
4. 웹 화면: 입력·설정 → 풀이 → 결과, 미응답 확인, 만료 안내, 오류/429 처리
5. TXT 파일 불러오기: 브라우저에서 읽기 → 내용 확인·수정 → 기존 텍스트 생성 API 사용

TXT는 UTF-8, 최대 100,000바이트, 앞뒤 공백 제외 20~20,000자입니다.
파일 자체는 서버에 저장하지 않으며 퀴즈 생성 때 텍스트만 전송합니다.
잘못된 파일을 선택해도 기존 입력을 보존합니다. PDF 등과 페이지 지정은 아직 지원하지 않습니다.

## 검증 결과

- 백엔드 pytest: 112 passed, 1 warning (기존 Starlette HTTPX TestClient 경고)
- 프런트엔드 npm test: 9 passed
- npm run typecheck 및 npm run build 통과
- 브라우저: 세 유형 혼합 채점, 미응답, 429 중지/수동 재개, 텍스트 원문 근거 확인
- TXT 파일 선택/인코딩 오류/내용 보존 → 모킹 생성 → 실제 채점 로직 → 점수·근거 표시 확인
- 320px/390px 화면의 가로 넘침 없는 배치 확인
- 실제 Gemini: 사용자가 주제 모드의 객관식 5문항 생성 성공을 확인함
- 최근 UI/TXT 작업은 모킹으로 검증했으며 실제 Gemini를 추가 호출하지 않았음

현재 화면 참고: [TXT 입력 화면](ui-txt.jpg). ui-workbench.jpg는 문구 수정 전 화면입니다.

## 노트북에서 시작

새 작업 폴더라면:

```powershell
git clone https://github.com/orca305/QuizForge.git
cd QuizForge
```

이미 복제한 저장소라면 먼저 git status로 변경사항을 확인한 뒤 git pull --ff-only를 실행합니다.
로컬 변경을 버리는 reset --hard나 강제 푸시는 사용하지 마세요.
다른 프로젝트 폴더(AURORE/dev-portfolio 등)는 수정하지 않습니다.

Python 3.13과 uv를 준비한 뒤 프로젝트 루트에서:

```powershell
py -3.13 -m uv sync

$geminiKey = Read-Host "Gemini API 키" -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", $geminiKey).Password
Remove-Variable geminiKey

# 노트북의 새 학습 세션용 암호화 키
$env:QUIZFORGE_TOKEN_KEY = (& .\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
$env:QUIZFORGE_GENERATION_ENABLED = "true"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

환경변수와 비밀키는 Git에 포함하지 않습니다. 노트북에서 별도로 설정해야 합니다.
키를 채팅에 붙여 넣거나 NEXT_PUBLIC 환경변수에 넣지 마세요.
암호화 키가 바뀌면 이전 키로 생성한 퀴즈는 채점할 수 없습니다. 서버 재시작 때도 키를 유지하세요.
Gemini 프로젝트는 Free 등급이며 결제 계정을 연결하지 않는 운영 방침입니다.
앱 자체는 결제 등급/잔량을 확인하지 못하고, 상위 서비스의 429에 따라 생성 중지 안내를 제공합니다.

별도 PowerShell에서 (프로젝트 경로는 실제 복제 위치로 변경):

```powershell
cd QuizForge\frontend
npm ci
npm run dev -- --port 3002
```

프런트엔드: http://127.0.0.1:3002 / Swagger: http://127.0.0.1:8000/docs
Node.js 20.9 이상이 필요합니다. 데스크톱에서는 Node.js 24.21.0으로 검증했습니다.
각 포트의 서버는 한 번만 실행합니다. 백엔드가 중복 실행되어 이전 환경변수의 서버에
연결된 사례가 있었으므로 not_configured 오류가 반복되면 포트 소유 프로세스를 확인하세요.

가상환경에는 uv가 설치되어 있지 않습니다. uv는 py -3.13 -m uv로,
앱과 pytest는 .venv\Scripts\python.exe로 실행하면 활성화 여부에 관계없이 동작합니다.

## 테스트

```powershell
# 프로젝트 루트
& .\.venv\Scripts\python.exe -m pytest -q

# frontend 폴더
npm test
npm run typecheck
npm run build
```

자동 테스트에는 API 키가 필요 없고 Gemini도 호출하지 않습니다.
브라우저 QA용 별도 모킹 서버는 tests/ui_mock_server.py이며 실행법은 README에 있습니다.
실제 앱에는 모킹 응답으로 성공 처리하는 fallback이 없습니다.

## 다음 작업

**텍스트형 PDF 읽기와 페이지별 출제 범위 지정**부터 진행합니다.

- 파일 크기/페이지 수/추출 길이를 제한하고 공식 파서 문서를 확인한 뒤 최소 패키지 선택
- 페이지 번호와 원문 근거 위치를 유지하도록 입력·출력 스키마 확장
- 빈 PDF, 손상/암호화 파일, 텍스트 없는 스캔 PDF를 안전하게 처리
- 스캔 PDF/OCR은 별도 단계로 명시하고 지원한다고 표시하지 않기
- 프런트엔드에서 추출 내용을 확인한 후 생성하도록 연결
- 외부 LLM은 모킹해 비용 없이 테스트; 실제 호출 범위는 사용자와 먼저 확인

이후 PPTX/DOCX/이미지를 순차적으로 검토합니다. 배포는 별도 요청 전까지 하지 않습니다.

## 유지할 제약

- 정답·해설·근거는 제출 전 공개 응답에 포함하지 않기
- 서버 메모리에 정답을 보관하지 않고 Fernet 인증 암호화 토큰 사용 (유효기간 1시간)
- 서명만 된 토큰을 비밀 보관 수단으로 쓰지 않기
- DB/인증이 없어 일회성 제출, 사용자 소유권, 재제출 차단은 보장하지 않음
- 단답형은 Unicode/공백/대소문자 정규화 후 정확 일치; 의미 유사성 채점 없음
- 구조와 원문 인용 위치 검증이 사실 정확성을 보장하지 않음
- 자동 재시도·유료 대체 모델·추가 인프라(DB/Redis/Celery 등) 추가하지 않기
- 비밀키·민감한 원문·정답을 오류나 로그에 노출하지 않기
- 소스 파일은 BOM 없는 UTF-8로 저장하기 (잘못된 인코딩의 테스트 fixture는 예외)
