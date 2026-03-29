# 082_Simulation_v2 구현 프롬프트

- **작성일**: 2026-03-22
- **목적**: 081_Simulation(MVP)을 기반으로 인증, 이력 저장, 관리자 대시보드를 추가한 v2 구현
- **기반**: 081_Simulation (FastAPI + Vanilla HTML/Tailwind CSS + Claude CLI + ChromaDB)

---

## 1. 프로젝트 개요

081_Simulation(AICC 롤플레이 시뮬레이터 MVP)에 다음 3가지 기능을 추가하여 082_Simulation_v2로 업그레이드한다.

### 현재 기술 스택 (081)
- **Backend**: FastAPI + Uvicorn
- **Frontend**: Vanilla HTML + Tailwind CSS (CDN) + Material Symbols
- **LLM**: Claude CLI (Pro/Max 구독)
- **임베딩**: intfloat/multilingual-e5-small (로컬)
- **벡터 DB**: ChromaDB (로컬)
- **폰트**: Manrope (Headline) + Inter (Body)
- **디자인 시스템**: LG U+ 브랜드 컬러 (#002859 primary, #b50062 secondary)

### 추가할 기능

| # | 기능 | 설명 |
|---|------|------|
| 1 | **로그인/인증** | 부서명·이름·직책 필수 입력, ID/PW 기반 로그인 |
| 2 | **시뮬레이션 이력 저장** | 모든 롤플레이·퀴즈 이력을 사용자별로 저장, 본인 조회 가능 |
| 3 | **관리자 대시보드** | 팀장(양준모)만 접근 가능한 팀원 활동 현황 + 종합 평가 페이지 |

---

## 2. 기능 상세

### 2.1 로그인/인증 시스템

#### 요구사항
- 앱 접속 시 **로그인 페이지** (`/login`)를 먼저 표시
- 로그인하지 않으면 모든 API/페이지 접근 차단
- 최초 사용 시 **회원가입** (`/register`)

#### 회원가입 필수 필드

| 필드 | HTML 타입 | 필수 | 비고 |
|------|----------|------|------|
| 아이디 | text | ✅ | 영문+숫자, 4자 이상, 중복 불가 |
| 비밀번호 | password | ✅ | 8자 이상 |
| 비밀번호 확인 | password | ✅ | 일치 검증 |
| 이름 | text | ✅ | 한글 실명 |
| 부서명 | select | ✅ | "AI사업2팀" 등 선택지 제공 + "직접입력" 옵션 |
| 직책 | select | ✅ | 사원/선임/책임/팀장/담당 |

#### 로그인 페이지 (`/login`)
- 아이디 / 비밀번호 입력 폼
- "로그인" 버튼 + "회원가입" 링크
- 기존 081 디자인 시스템 (Tailwind + LG U+ 컬러) 준수
- 로그인 성공 시 JWT 토큰 발급 → `localStorage`에 저장
- 모든 페이지 상단 네비게이션에 "OOO 과장님 (AI사업2팀)" + 로그아웃 버튼 표시

#### 기술 구현
- **Backend**: FastAPI에 인증 라우터 추가 (`/api/auth/login`, `/api/auth/register`)
- **저장소**: SQLite (`data/app.db`) — users 테이블
- **비밀번호**: `bcrypt` 해싱 (평문 저장 절대 금지)
- **세션**: JWT 토큰 (python-jose) — `Authorization: Bearer <token>` 헤더
- **Frontend**: `localStorage`에 토큰 저장, 모든 fetch 요청에 헤더 추가
- **미들웨어**: FastAPI 미들웨어로 `/api/*` 경로 인증 체크 (로그인/가입 API 제외)

#### 관리자 계정 (하드코딩)
- 앱 최초 실행 시 관리자 계정 자동 생성 (DB에 없을 때만)
  - **ID**: `admin`
  - **PW**: `admin1234` (최초 로그인 후 변경 권장)
  - **이름**: 양준모
  - **부서**: AI사업2팀
  - **직책**: 팀장
  - **역할**: `admin`
- **관리자는 이 1명(양준모)만 존재.** 다른 사용자는 모두 `role = "user"`
- 관리자 추가/변경은 DB 직접 수정으로만 가능 (UI 미제공)

---

### 2.2 시뮬레이션 이력 저장

#### 저장 대상

| 활동 유형 | 저장 항목 |
|-----------|----------|
| **롤플레이** | 시나리오명, 난이도, 전체 대화 내용, 피드백(JSON), 종합등급, 시작/종료 시간, 대화 턴 수 |
| **퀴즈** | 카테고리, 난이도, 문제, 선택한 답, 정답 여부, 풀이 시간 |

#### 저장 시점
- **롤플레이**: 피드백 생성 완료 시 → `POST /api/history/roleplay` 자동 호출
- **퀴즈**: 정답 확인 클릭 시 → `POST /api/history/quiz` 자동 호출

#### 개인 이력 조회 (새 페이지: `/history`)

네비게이션에 "📊 내 학습 이력" 메뉴 추가

**롤플레이 이력**
- 날짜별 목록 (최신순) — 카드 또는 테이블 레이아웃
- 각 세션: 시나리오명 | 난이도 | 종합등급 (A/B/C/D 배지) | 대화 턴 수 | 소요시간
- 카드 클릭 시 상세 모달/페이지: 전체 대화 + 피드백 내용
- 등급 추이 차트 (시간순 A/B/C/D 변화) — Chart.js 또는 Canvas 직접 렌더링

**퀴즈 이력**
- 카테고리별 정답률 요약 (프로그레스 바)
- 날짜별 상세 기록
- 카테고리별 정답률 바 차트

#### 기술 구현
- **Backend API**:
  - `POST /api/history/roleplay` — 롤플레이 세션 저장
  - `POST /api/history/quiz` — 퀴즈 기록 저장
  - `GET /api/history/roleplay` — 본인 롤플레이 이력 조회
  - `GET /api/history/quiz` — 본인 퀴즈 이력 조회
  - `GET /api/history/roleplay/{id}` — 롤플레이 상세 조회
- **Frontend**: `/history` 페이지 (static/history.html) — 기존 디자인 시스템 활용
- **저장소**: SQLite (`data/app.db`) — roleplay_sessions, quiz_records 테이블

```sql
-- 사용자
CREATE TABLE users (
    id TEXT PRIMARY KEY,             -- 로그인 ID
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    position TEXT NOT NULL,          -- 직책
    role TEXT DEFAULT 'user',        -- 'user' | 'admin'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 롤플레이 세션
CREATE TABLE roleplay_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    scenario_key TEXT NOT NULL,
    scenario_title TEXT NOT NULL,
    persona_level TEXT NOT NULL,
    overall_grade TEXT,              -- A/B/C/D
    conversation TEXT NOT NULL,      -- JSON 문자열
    feedback TEXT,                   -- JSON 문자열
    turn_count INTEGER,
    started_at DATETIME,
    ended_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration_seconds INTEGER
);

-- 퀴즈 기록
CREATE TABLE quiz_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    category TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    question TEXT NOT NULL,
    user_answer TEXT,
    correct_answer TEXT,
    is_correct BOOLEAN,
    answered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

### 2.3 관리자 대시보드 (새 페이지: `/admin`)

#### 접근 권한
- **양준모(admin) 1명만** 접근 가능
- Backend: JWT 토큰에서 `role == "admin"` 체크 → 아니면 403
- Frontend: 네비게이션에서 admin이 아닌 사용자에게는 메뉴 자체를 숨김
- URL 직접 접근해도 API에서 403 반환 → 로그인 페이지로 리다이렉트

#### 대시보드 구성

**A. 팀 전체 현황 (상단 카드)**

| 지표 | 표시 방식 |
|------|----------|
| 총 등록 사용자 수 | 숫자 카드 (Material Symbol: `group`) |
| 이번 주 / 이번 달 활성 사용자 수 | 숫자 카드 |
| 총 롤플레이 실행 횟수 | 숫자 카드 |
| 총 퀴즈 풀이 횟수 | 숫자 카드 |
| 일별/주별 활동 추이 | 라인 차트 |

**B. 팀원별 활동 현황 (테이블)**

| 컬럼 | 내용 |
|------|------|
| 이름 | 실명 |
| 부서 | 부서명 |
| 직책 | 직책 |
| 롤플레이 횟수 | 총 실행 횟수 |
| 평균 등급 | A/B/C/D 평균 |
| 퀴즈 수 | 총 풀이 횟수 |
| 퀴즈 정답률 | % |
| 최근 활동일 | YYYY-MM-DD |

행 클릭 시 해당 팀원의 상세 데이터 펼침:
- 롤플레이 등급 추이 차트
- 시나리오별 성과
- 퀴즈 카테고리별 정답률

**C. 종합 평가 리포트 (AI 분석)**

"🤖 종합 리포트 생성" 버튼 클릭 시 → `POST /api/admin/report` → Claude 호출하여 자동 생성:

```
## 팀 종합 평가 리포트

### 1. 전체 요약
- 총 N명 중 M명이 활발히 학습 (활성률 X%)
- 평균 롤플레이 등급: B+
- 가장 많이 연습한 시나리오: AICC 도입 초기 미팅

### 2. 팀원별 평가
| 이름 | 롤플레이 횟수 | 평균 등급 | 등급 추이 | 퀴즈 정답률 | 강점 | 개선점 |
|------|-------------|----------|----------|-----------|------|--------|
| 김OO | 12회 | B | C→B→B→A | 78% | 용어 활용 우수 | 가격 협상 대응 부족 |

### 3. 시나리오별 분석
- 가장 어려워하는 시나리오: 기술 견적 (평균 C+)
- 가장 잘하는 시나리오: 솔루션 시연 (평균 B+)

### 4. 공통 개선점
- 전체적으로 가격 협상/견적 대응이 약함
- STT/TTS 기술 스펙 설명이 부정확한 경우가 많음

### 5. 추천 액션
- 기술 견적 시나리오 집중 연습 권장
- STT/TTS 관련 교육자료 보충 필요
```

**D. 개선점 트래킹**

- 전체 롤플레이 피드백에서 `improvements` 필드 수집
- 빈도순 정렬: 가장 많이 나온 개선점 TOP 10
- 바 차트로 시각화

#### Backend API

| 엔드포인트 | 메서드 | 설명 | 권한 |
|-----------|--------|------|------|
| `/api/admin/overview` | GET | 팀 전체 현황 집계 | admin |
| `/api/admin/members` | GET | 팀원별 활동 현황 | admin |
| `/api/admin/members/{user_id}` | GET | 특정 팀원 상세 | admin |
| `/api/admin/report` | POST | AI 종합 리포트 생성 | admin |
| `/api/admin/improvements` | GET | 개선점 트래킹 데이터 | admin |

---

## 3. 파일 구조 (082_Simulation_v2)

```
082_Simulation_v2/
├── main.py                       # FastAPI 서버 (081 기반 + 인증 미들웨어 + 관리자 API)
├── config.py                     # 설정 (081 기반 + DB 경로 + JWT 시크릿)
├── auth.py                       # 인증 모듈 (회원가입, 로그인, JWT, 비밀번호 해싱)
├── db.py                         # SQLite 초기화 + CRUD (users, sessions, quiz)
├── llm.py                        # Claude CLI 래퍼 (081 그대로)
├── rag.py                        # RAG 파이프라인 (081 그대로)
├── ingest.py                     # 문서 임베딩 (081 그대로)
├── roleplay.py                   # 롤플레이 엔진 (081 그대로)
├── feedback.py                   # 피드백 분석 (081 그대로)
├── quiz.py                       # 퀴즈 (081 그대로)
├── admin_report.py               # AI 종합 리포트 생성 로직
├── generate_quiz_pool.py         # 퀴즈 풀 생성 (081 그대로)
├── quiz_pool.json                # 사전 생성 퀴즈
├── static/                       # Frontend (Vanilla HTML + Tailwind CSS)
│   ├── shared.css                # 공통 스타일 (081 그대로)
│   ├── index.html                # 대시보드 (081 기반)
│   ├── login.html                # ★ 신규: 로그인 페이지
│   ├── register.html             # ★ 신규: 회원가입 페이지
│   ├── simulation.html           # 롤플레이 (081 기반 + 이력 저장 fetch 추가)
│   ├── quiz.html                 # 퀴즈 (081 기반 + 이력 저장 fetch 추가)
│   ├── dictionary.html           # 용어사전 (081 그대로)
│   ├── history.html              # ★ 신규: 내 학습 이력 페이지
│   └── admin.html                # ★ 신규: 관리자 대시보드 페이지
├── data/                         # DB 파일
│   └── app.db                    # SQLite (users + roleplay_sessions + quiz_records)
├── chroma_db/                    # 벡터 저장소
├── docs/                         # 학습 데이터 (081 그대로)
└── requirements.txt              # 의존성 (+ bcrypt, python-jose)
```

---

## 4. 주요 UX 플로우

### 플로우 1: 일반 사용자
```
http://localhost:8000 접속
→ /login 페이지 표시 → ID/PW 입력 → POST /api/auth/login → JWT 발급
→ localStorage에 토큰 저장 → / (대시보드)로 리다이렉트
→ 네비게이션: 대시보드 | 롤플레이 | 퀴즈 | 용어사전 | 📊 내 학습 이력
→ 롤플레이 완료 → 피드백 생성 → POST /api/history/roleplay 자동 저장
→ /history에서 이력 확인
→ 네비게이션 "로그아웃" → localStorage 토큰 삭제 → /login으로 이동
```

### 플로우 2: 관리자 (양준모 팀장)
```
http://localhost:8000 접속
→ /login → admin / admin1234 → JWT 발급
→ 네비게이션: 대시보드 | 롤플레이 | 퀴즈 | 용어사전 | 📊 내 학습 이력 | 🔑 관리자
→ /admin에서:
  - 팀 전체 현황 카드 확인
  - 팀원별 활동 테이블 조회
  - "종합 리포트 생성" 클릭 → Claude가 분석 → 마크다운 리포트 렌더링
  - 개선점 TOP 10 바 차트 확인
```

### 플로우 3: 최초 접속 (회원가입)
```
/login → "회원가입" 링크 클릭 → /register
→ 부서명, 이름, 직책, ID, PW 입력 → POST /api/auth/register
→ 성공 시 /login으로 리다이렉트 → "가입 완료! 로그인하세요" 메시지
```

---

## 5. 기술 제약 & 결정

| 항목 | 결정 | 이유 |
|------|------|------|
| Backend | FastAPI | 081 기존 구조 유지 |
| Frontend | Vanilla HTML + Tailwind CSS (CDN) | 081 기존 구조 유지, 빌드 도구 불필요 |
| DB | SQLite (단일 파일 `data/app.db`) | 서버 설치 불필요, 10명 규모에 충분 |
| 비밀번호 | bcrypt | 업계 표준 해싱, 솔트 자동 생성 |
| 인증 | JWT (python-jose) | Stateless, localStorage 기반, FastAPI와 호환 |
| 차트 | Chart.js (CDN) | 별도 빌드 불필요, Tailwind와 조화 |
| AI 리포트 | Claude CLI 호출 | 기존 llm.py 활용 |

---

## 6. 네비게이션 구조

### 일반 사용자 (로그인 후)
```
[대시보드] [롤플레이] [퀴즈] [용어사전] [📊 내 이력]     OOO 과장님 (AI사업2팀) [로그아웃]
```

### 관리자 — 양준모 팀장 (로그인 후)
```
[대시보드] [롤플레이] [퀴즈] [용어사전] [📊 내 이력] [🔑 관리자]     양준모 팀장님 (AI사업2팀) [로그아웃]
```

- "🔑 관리자" 메뉴는 `role === 'admin'`일 때만 렌더링
- 기존 081 네비게이션 스타일 그대로 사용 (Tailwind + LG U+ 컬러)

---

## 7. 구현 우선순위

| 순서 | 작업 | 파일 | 규모 |
|------|------|------|------|
| 1 | SQLite 스키마 + 초기화 + 관리자 시드 | `db.py` | 소 |
| 2 | 인증 API (bcrypt + JWT) | `auth.py`, `main.py` | 중 |
| 3 | 로그인/회원가입 페이지 | `static/login.html`, `static/register.html` | 중 |
| 4 | 인증 미들웨어 + 전체 페이지/API 보호 | `main.py` | 중 |
| 5 | 기존 페이지 네비게이션에 유저 정보 + 로그아웃 추가 | `static/*.html` | 소 |
| 6 | 이력 저장 API + simulation/quiz 페이지 연동 | `main.py`, `static/simulation.html`, `static/quiz.html` | 중 |
| 7 | 내 학습 이력 페이지 | `static/history.html`, `main.py` | 중 |
| 8 | 관리자 대시보드 페이지 + API | `static/admin.html`, `main.py`, `admin_report.py` | 대 |

---

*이 프롬프트를 기반으로 082_Simulation_v2 프로젝트를 구현합니다.*
