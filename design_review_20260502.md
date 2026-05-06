# Design Review — 082 AICC Role Play Agent
**날짜:** 2026-05-02  
**대상:** http://localhost:8000  
**분류:** HYBRID (랜딩 페이지 + App UI)

---

## First Impression

**사이트가 말하는 것:** "B2B 내부 학습 플랫폼인데, 외부 제품처럼 보이고 싶다."

**눈이 먼저 가는 3가지:**
1. "Become the AICC Domain Expert" — 강렬한 흰 타이포에 시아노 accent, 즉시 목적 파악 ✓
2. "시작하기 →" 파란 CTA 버튼
3. LG U+ 폰 이미지 — 브랜드 신뢰감

**한 단어:** *Ambitious* — 내부 팀 도구치고 과감하게 마케팅 랜딩을 만들었다. 의도는 선명하지만 실행에 구멍이 있다.

---

## 점수

| 카테고리 | 등급 | 이유 |
|---------|------|------|
| Visual Hierarchy | B | 섹션 리듬 좋음, H2/H3 scale 이슈 |
| Typography | C | system-ui 포기, 계층 붕괴 |
| Spacing & Layout | B | 전반적으로 깔끔 |
| Color & Contrast | B | LG U+ 팔레트 일관성 |
| Interaction States | D | 모바일 invisible, 터치 타겟 실패 |
| Responsive | D | 모바일 hero 이후 전부 흰 화면 |
| Content Quality | B | 카피 선명, 한영 혼용만 아쉬움 |
| AI Slop | B | system-ui 제외 slop 패턴 적음 |
| Motion | C | reduced-motion fallback 없음 |
| Performance | A | 167ms, 매우 빠름 |

**Design Score: C+ | AI Slop Score: B**

---

## 발견된 문제 (11개)

### HIGH — 즉시 수정

**FINDING-001: 모바일에서 Hero 아래 모든 섹션 invisible**  
`.fade-in` 섹션 6개가 `opacity: 0`으로 시작하고 IntersectionObserver로 트리거되는데, `prefers-reduced-motion` 미디어 쿼리 fallback이 없다. headless·SSR 환경에서도 완전히 보이지 않음. 모바일 반응형 스크린샷에서 hero 이후 **전부 빈 흰 페이지**.

**FINDING-002: system-ui가 유일한 폰트**  
`-apple-system, system-ui`가 primary font. Apple 기기에선 SF Pro라 괜찮지만 Windows에선 Segoe UI/Arial로 렌더링. 시네마틱 hero를 만들어놓고 서체를 포기한 셈. 커스텀 display font 하나면 인상이 달라짐.

**FINDING-003: 터치 타겟 44px 미달**  
- nav 로고 링크: 173×32px ❌  
- nav "로그인" 버튼: 76×34px ❌

**FINDING-004: Tailwind CDN 프로덕션 사용**  
콘솔 경고 4회 반복: `cdn.tailwindcss.com should not be used in production`. CDN 의존 + 전체 Tailwind 번들 로드 = 불필요한 외부 의존성.

### MEDIUM — 다음 단계

**FINDING-005: H2(40px) ↔ H3(36px) 계층 붕괴**  
Voice 섹션 H2가 40px인데 Features 서브헤딩 H3이 36px. 4px 차이는 계층을 읽을 수 없게 만든다. 1.333 perfect fourth 스케일이면 H2=56px → H3=42px이어야 함.

**FINDING-006: CSS 변수 없음 — 값이 전부 하드코딩**  
브랜드 컬러(`rgb(0, 113, 227)`), spacing 등이 파일 전체에 산재. 변경 시 전수 검색 필요. `--color-primary`, `--color-accent` 2개만 있어도 유지보수 비용 절반.

**FINDING-007: 한/영 혼용 섹션 헤딩**  
"Strategic Growth: A Phased Evolution" 섹션만 100% 영문. 나머지는 한국어 or 한/영 혼합. 한 페이지 안에서 언어 톤이 튄다.

**FINDING-008: 로그인 후 첫 화면이 에러 상태**  
Simulation 페이지 진입 시 "데이터를 불러올 수 없습니다. 서버가 실행 중인지 확인해주세요." — 랜딩의 강렬한 첫인상이 로그인 직후 에러 상태로 무너짐.

**FINDING-009: Roadmap Stage 2/3 카드가 빈 느낌**  
Stage 1은 "NOW" 뱃지 + "MVP 완료" + 진한 배경. Stage 2/3는 아무 상태 표시 없이 옅은 카드. 미완성처럼 보임.

### POLISH

**FINDING-010: 사이드바 nav 아이콘 없음**  
Dashboard/Simulation/Quiz 등 텍스트만. "Start New Roleplay"는 + 아이콘 있는데 나머지 항목은 없어 시각적 스캔이 느려짐.

**FINDING-011: Dictionary·Simulation 에러 메시지 품질**  
"데이터를 불러올 수 없습니다"는 원인도 없고 액션도 약함. "서버가 실행 중인지 확인해주세요"는 유저 잘못이 아닌데 유저에게 책임 전가하는 표현.

---

## Quick Wins (30분 내 수정 가능)

1. **FINDING-001** — `@media (prefers-reduced-motion: reduce)` fallback 추가 → `.fade-in { opacity: 1; transform: none; }`
2. **FINDING-003** — 터치 타겟 `min-height: 44px; padding` 추가
3. **FINDING-005** — H2/H3 폰트 사이즈 스케일 조정
