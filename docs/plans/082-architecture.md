# 082_Simulation_v2 아키텍처

---

## 1. 시스템 전체 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                        클라이언트 (브라우저)                           │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────┐ ┌──────┐ │
│  │ login    │ │ register │ │ index  │ │ simul  │ │ quiz │ │ dict │ │
│  │ .html    │ │ .html    │ │ .html  │ │ .html  │ │ .html│ │ .html│ │
│  └──────────┘ └──────────┘ └────────┘ └────────┘ └──────┘ └──────┘ │
│  ┌──────────┐ ┌──────────┐                                         │
│  │ history  │ │ admin    │ ← admin만                                │
│  │ .html    │ │ .html    │                                         │
│  └──────────┘ └──────────┘                                         │
│                                                                     │
│  Vanilla HTML + Tailwind CSS (CDN) + Chart.js (CDN)                │
│  JWT 토큰: localStorage 저장 → 모든 fetch에 Bearer 헤더 첨부         │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP (JSON)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI 서버 (Uvicorn)                           │
│                     http://localhost:8000                            │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    인증 미들웨어 (JWT 검증)                     │    │
│  │  /login, /register, /api/auth/* → 통과                       │    │
│  │  그 외 모든 요청 → JWT 검증 → 실패 시 /login 리다이렉트         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─── 공개 API ──┐  ┌── 인증 필요 API ──┐  ┌── admin 전용 API ──┐  │
│  │               │  │                   │  │                    │  │
│  │ POST /api/    │  │ GET  /api/        │  │ GET  /api/admin/   │  │
│  │  auth/login   │  │  scenarios        │  │  overview          │  │
│  │ POST /api/    │  │ POST /api/        │  │ GET  /api/admin/   │  │
│  │  auth/register│  │  roleplay/start   │  │  members           │  │
│  │               │  │ POST /api/        │  │ GET  /api/admin/   │  │
│  │               │  │  roleplay/respond │  │  members/{id}      │  │
│  │               │  │ POST /api/        │  │ POST /api/admin/   │  │
│  │               │  │  roleplay/feedback│  │  report             │  │
│  │               │  │ GET  /api/quiz    │  │ GET  /api/admin/   │  │
│  │               │  │ GET  /api/glossary│  │  improvements      │  │
│  │               │  │ POST /api/        │  │                    │  │
│  │               │  │  history/roleplay │  │ role=="admin" 체크  │  │
│  │               │  │ POST /api/        │  │                    │  │
│  │               │  │  history/quiz     │  │                    │  │
│  │               │  │ GET  /api/        │  │                    │  │
│  │               │  │  history/*        │  │                    │  │
│  └───────────────┘  └───────────────────┘  └────────────────────┘  │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐   │
│  │ auth.py  │  │roleplay  │  │feedback  │  │ admin_report.py   │   │
│  │ 인증로직  │  │  .py     │  │  .py     │  │ AI 종합리포트     │   │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────────┘   │
└───────┬──────────────┬──────────────┬──────────────┬────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────┐
│   SQLite     │ │  ChromaDB    │ │Claude CLI│ │ HuggingFace  │
│  data/app.db │ │  chroma_db/  │ │ (Pro/Max)│ │  Embeddings  │
│              │ │              │ │          │ │   (로컬)     │
│ • users      │ │ • 312 chunks │ │ • 롤플레이│ │ • multilingual│
│ • roleplay_  │ │ • 12개 문서  │ │   응답   │ │   -e5-small  │
│   sessions   │ │              │ │ • 피드백  │ │              │
│ • quiz_      │ │              │ │ • 리포트  │ │              │
│   records    │ │              │ │          │ │              │
└──────────────┘ └──────────────┘ └──────────┘ └──────────────┘
```

---

## 2. 인증 플로우

```
┌─────────┐          ┌─────────┐          ┌─────────┐
│ 브라우저  │          │ FastAPI │          │ SQLite  │
└────┬────┘          └────┬────┘          └────┬────┘
     │                    │                    │
     │ ── 회원가입 ──────────────────────────────────
     │                    │                    │
     │  POST /api/auth/   │                    │
     │  register          │                    │
     │  {id, pw, name,    │                    │
     │   dept, position}  │                    │
     │ ──────────────────►│                    │
     │                    │  중복 체크          │
     │                    │ ──────────────────►│
     │                    │ ◄────────────────  │
     │                    │  bcrypt(pw)        │
     │                    │  INSERT users      │
     │                    │ ──────────────────►│
     │     {ok: true}     │                    │
     │ ◄──────────────────│                    │
     │                    │                    │
     │ ── 로그인 ────────────────────────────────────
     │                    │                    │
     │  POST /api/auth/   │                    │
     │  login             │                    │
     │  {id, pw}          │                    │
     │ ──────────────────►│                    │
     │                    │  SELECT user       │
     │                    │ ──────────────────►│
     │                    │ ◄────────────────  │
     │                    │  bcrypt.verify(pw) │
     │                    │  JWT 생성           │
     │  {token, user}     │  (id, role 포함)   │
     │ ◄──────────────────│                    │
     │                    │                    │
     │  localStorage      │                    │
     │  .setItem(token)   │                    │
     │                    │                    │
     │ ── 이후 모든 API 요청 ─────────────────────────
     │                    │                    │
     │  GET /api/scenarios│                    │
     │  Authorization:    │                    │
     │  Bearer <token>    │                    │
     │ ──────────────────►│                    │
     │                    │  JWT 검증           │
     │                    │  → user_id 추출     │
     │     {data}         │                    │
     │ ◄──────────────────│                    │
```

---

## 3. 데이터 플로우: 롤플레이 + 이력 저장

```
┌─────────────────────────────────────────────────────────┐
│                  simulation.html                         │
│                                                         │
│  1. 시나리오 선택 + 난이도 선택                             │
│  2. "시작" 클릭                                          │
│     ├─→ POST /api/roleplay/start                        │
│     │   ├─→ roleplay.py: build_system_prompt()          │
│     │   │   └─→ rag.py: retrieve() → ChromaDB 검색      │
│     │   └─→ llm.py: call_claude() → 첫 인사 생성         │
│     │                                                    │
│  3. 대화 루프 (사용자 입력 ↔ AI 응답)                      │
│     ├─→ POST /api/roleplay/respond                      │
│     │   └─→ llm.py: call_claude() → AI 고객 응답         │
│     │                                                    │
│  4. "종료 & 피드백" 클릭                                   │
│     ├─→ POST /api/roleplay/feedback                     │
│     │   └─→ feedback.py: analyze_roleplay()             │
│     │       └─→ llm.py: call_claude() → 피드백 JSON      │
│     │                                                    │
│  5. ★ 피드백 수신 후 자동 저장 (신규)                       │
│     └─→ POST /api/history/roleplay                      │
│         {user_id, scenario, persona, conversation,      │
│          feedback, grade, turn_count, duration}          │
│         └─→ db.py: INSERT roleplay_sessions             │
│             └─→ SQLite (data/app.db)                    │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 데이터 플로우: 관리자 대시보드

```
┌─────────────────────────────────────────────────────────────────┐
│                       admin.html                                 │
│                   (양준모 팀장만 접근)                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  A. 팀 전체 현황 카드                                    │        │
│  │  GET /api/admin/overview                              │        │
│  │                                                       │        │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐         │        │
│  │  │ 등록   │ │ 활성   │ │ 롤플레이│ │ 퀴즈   │         │        │
│  │  │ 10명   │ │ 7명    │ │ 45회   │ │ 230문제│         │        │
│  │  └────────┘ └────────┘ └────────┘ └────────┘         │        │
│  │                                                       │        │
│  │  [═══════ 일별 활동 추이 라인 차트 (Chart.js) ═══════]  │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  B. 팀원별 활동 현황 테이블                               │        │
│  │  GET /api/admin/members                               │        │
│  │                                                       │        │
│  │  이름   │ 직책 │ 롤플레이 │ 평균등급 │ 퀴즈 │ 정답률 │ 최근   │        │
│  │  ───────┼──────┼─────────┼────────┼──────┼───────┼──────│        │
│  │  김민식 │ 책임 │   8회   │   B    │  32  │  75%  │ 3/21 │        │
│  │  김준희 │ 선임 │   5회   │   C+   │  28  │  68%  │ 3/20 │        │
│  │  ...    │      │         │        │      │       │      │        │
│  │                                                       │        │
│  │  [행 클릭] → GET /api/admin/members/{user_id}         │        │
│  │  → 등급 추이 차트 + 시나리오별 성과 + 퀴즈 상세 펼침     │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  C. AI 종합 리포트                                      │        │
│  │                                                       │        │
│  │  [🤖 종합 리포트 생성] 버튼                               │        │
│  │       │                                               │        │
│  │       ▼                                               │        │
│  │  POST /api/admin/report                               │        │
│  │       │                                               │        │
│  │       ├─→ db.py: 전체 세션/퀴즈 데이터 집계             │        │
│  │       ├─→ llm.py: call_claude(집계 데이터 + 프롬프트)   │        │
│  │       └─→ 마크다운 리포트 렌더링                         │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  D. 개선점 트래킹                                       │        │
│  │  GET /api/admin/improvements                          │        │
│  │                                                       │        │
│  │  가격 협상 대응    ████████████████████  12건           │        │
│  │  기술 스펙 설명    ███████████████      9건            │        │
│  │  ROI 수치 제시    ██████████           7건            │        │
│  │  경쟁사 비교 대응  ████████             5건            │        │
│  │  ...              (Bar Chart — Chart.js)              │        │
│  └──────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. DB 스키마 (ERD)

```
┌──────────────────────────┐
│         users            │
├──────────────────────────┤
│ PK  id         TEXT      │──┐
│     password_hash TEXT   │  │
│     name        TEXT     │  │
│     department  TEXT     │  │
│     position    TEXT     │  │    position:
│     role        TEXT     │  │    사원/선임/책임/팀장/담당
│     created_at  DATETIME │  │
└──────────────────────────┘  │    role:
                              │    'user' | 'admin'
        ┌─────────────────────┤
        │                     │
        ▼                     ▼
┌────────────────────────┐  ┌────────────────────────┐
│   roleplay_sessions    │  │     quiz_records        │
├────────────────────────┤  ├────────────────────────┤
│ PK id    INTEGER (AI)  │  │ PK id    INTEGER (AI)  │
│ FK user_id    TEXT     │  │ FK user_id    TEXT     │
│    scenario_key TEXT   │  │    category   TEXT     │
│    scenario_title TEXT │  │    difficulty  TEXT     │
│    persona_level TEXT  │  │    question   TEXT     │
│    overall_grade TEXT  │  │    user_answer TEXT    │
│    conversation  TEXT  │  │    correct_answer TEXT │
│    feedback      TEXT  │  │    is_correct  BOOL    │
│    turn_count    INT   │  │    answered_at DATETIME│
│    started_at DATETIME │  └────────────────────────┘
│    ended_at   DATETIME │
│    duration_seconds INT│
└────────────────────────┘
```

---

## 6. 페이지 라우팅 & 권한 매트릭스

```
경로              │ HTML 파일           │ 비로그인 │ user │ admin │
──────────────────┼────────────────────┼─────────┼──────┼───────┤
/login            │ login.html         │   ✅    │  ✅  │  ✅   │
/register         │ register.html      │   ✅    │  ✅  │  ✅   │
/                 │ index.html         │   🔒    │  ✅  │  ✅   │
/simulation       │ simulation.html    │   🔒    │  ✅  │  ✅   │
/quiz             │ quiz.html          │   🔒    │  ✅  │  ✅   │
/dictionary       │ dictionary.html    │   🔒    │  ✅  │  ✅   │
/history          │ history.html       │   🔒    │  ✅  │  ✅   │
/admin            │ admin.html         │   🔒    │  🚫  │  ✅   │

🔒 = /login으로 리다이렉트
🚫 = 403 → /login으로 리다이렉트
```

---

## 7. 기술 스택 요약

```
┌─────────────────────────────────────────────────┐
│                  Frontend                        │
│  HTML + Tailwind CSS (CDN) + Chart.js (CDN)     │
│  Material Symbols + Manrope/Inter 폰트           │
│  LG U+ 브랜드 컬러 (#002859, #b50062)            │
├─────────────────────────────────────────────────┤
│                  Backend                         │
│  Python 3.9+ / FastAPI / Uvicorn                │
│  python-jose (JWT) / bcrypt (비밀번호)            │
├─────────────────────────────────────────────────┤
│                  Storage                         │
│  SQLite (data/app.db) — 유저, 세션, 퀴즈         │
│  ChromaDB (chroma_db/) — RAG 벡터 저장소         │
├─────────────────────────────────────────────────┤
│                  AI / ML                         │
│  Claude CLI (Pro/Max) — 롤플레이, 피드백, 리포트  │
│  HuggingFace (multilingual-e5-small) — 임베딩    │
│  LangChain — RAG 파이프라인                       │
└─────────────────────────────────────────────────┘
```

---

## 8. 081 → 082 변경 범위

```
081 (기존)                          082 (추가/변경)
──────────────                      ──────────────────
main.py                        →   main.py (+ 인증 미들웨어, 이력 API, 관리자 API)
config.py                      →   config.py (+ DB 경로, JWT 시크릿)
                                    auth.py ★ 신규
                                    db.py ★ 신규
                                    admin_report.py ★ 신규

static/index.html              →   static/index.html (+ 네비 유저 정보)
static/simulation.html         →   static/simulation.html (+ 이력 저장 fetch)
static/quiz.html               →   static/quiz.html (+ 이력 저장 fetch)
static/dictionary.html         →   static/dictionary.html (+ 네비 유저 정보)
                                    static/login.html ★ 신규
                                    static/register.html ★ 신규
                                    static/history.html ★ 신규
                                    static/admin.html ★ 신규

roleplay.py                    →   변경 없음
feedback.py                    →   변경 없음
quiz.py                        →   변경 없음
rag.py                         →   변경 없음
llm.py                         →   변경 없음
ingest.py                      →   변경 없음
```
