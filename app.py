"""IPCC/AICC 도메인 학습 — Stage 1 MVP"""
import streamlit as st

st.set_page_config(
    page_title="AICC 롤플레이 시뮬레이터",
    page_icon=""
    layout="wide",
)


# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.title(" AICC Role Play Simulator")
    st.caption("AI사업2팀 자기학습 도구 — Stage 1 MVP")
    st.divider()

    st.markdown("""
    **사용법**
    1. 첫 사용 시 '지식베이스 구축' 실행
    2. 롤플레이로 고객 대응 연습!
    """)
    st.divider()
    st.caption("Claude CLI 기반 (Pro/Max 구독 — 무료)")


# ── 지식베이스 구축 ──────────────────────────────────────
def is_db_ready() -> bool:
    from config import CHROMA_DIR
    return CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir())


if not is_db_ready():
    st.warning("지식베이스가 아직 구축되지 않았습니다. 아래 버튼을 눌러 구축하세요.")
    if st.button("🔨 지식베이스 구축", type="primary"):
        with st.spinner("문서를 임베딩하고 벡터 저장소를 구축 중입니다..."):
            from ingest import ingest
            ingest()
            st.success("지식베이스 구축 완료!")
            st.rerun()
    st.stop()


# ── 메인 탭 ────────────────────────────────────────────
tab_roleplay, tab_quiz, tab_glossary, tab_arch = st.tabs([
    "🎭 롤플레이",
    "🎯 도메인 퀴즈",
    "📖 용어 사전",
    "🏗️ 아키텍처 가이드",
])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 탭 1: 롤플레이 (메인 기능)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_roleplay:
    from roleplay import SCENARIOS, PERSONAS, build_system_prompt, get_ai_response, get_opening_message
    from feedback import analyze_roleplay

    # ── 세션 상태 초기화 ──
    if "rp_phase" not in st.session_state:
        st.session_state.rp_phase = "setup"  # setup / playing / feedback
    if "rp_history" not in st.session_state:
        st.session_state.rp_history = []
    if "rp_system_prompt" not in st.session_state:
        st.session_state.rp_system_prompt = ""
    if "rp_scenario" not in st.session_state:
        st.session_state.rp_scenario = ""
    if "rp_persona" not in st.session_state:
        st.session_state.rp_persona = ""
    if "rp_feedback" not in st.session_state:
        st.session_state.rp_feedback = None

    # ── Phase 1: 시나리오 선택 ──
    if st.session_state.rp_phase == "setup":
        st.header("고객 미팅 롤플레이")
        st.markdown("**실제 고객 미팅을 기반으로 AI 고객과 사업 대응을 연습하세요.**")
        st.caption("당신 =AI사업2팀 사업담당자 | AI = 고객")

        st.divider()

        # 시나리오 선택
        st.subheader("1. 시나리오 선택")
        scenario_options = {k: v["title"] for k, v in SCENARIOS.items()}

        for key, scenario in SCENARIOS.items():
            stars = {"솔루션 시연": "★★★★", "기술 견적": "★★★★★",
                     "보이스봇 요건정의": "★★★", "KMS/RAG 상품소개": "★★★",
                     "AICC 도입 초기": "★★★★"}
            with st.expander(f"**{scenario['title']}** ({stars.get(key, '★★★')}) — {scenario['source']}"):
                st.markdown(f"**상황:** {scenario['situation']}")
                st.markdown(f"**고객 역할:** {scenario['customer_role']}")
                st.markdown("**예상 질문:**")
                for q in scenario["key_questions"][:3]:
                    st.markdown(f"- _{q}_")

        selected_scenario = st.selectbox(
            "시나리오",
            options=list(SCENARIOS.keys()),
            format_func=lambda x: SCENARIOS[x]["title"],
        )

        st.divider()

        # 페르소나 난이도
        st.subheader("2. 고객 난이도")
        selected_persona = st.radio(
            "고객 성격",
            options=list(PERSONAS.keys()),
            format_func=lambda x: PERSONAS[x]["label"],
            horizontal=True,
        )

        st.divider()

        # 시작 버튼
        if st.button("🚀 롤플레이 시작", type="primary", use_container_width=True):
            st.session_state.rp_scenario = selected_scenario
            st.session_state.rp_persona = selected_persona
            st.session_state.rp_history = []
            st.session_state.rp_feedback = None

            with st.spinner("AI 고객을 준비하고 있습니다..."):
                system_prompt = build_system_prompt(selected_scenario, selected_persona)
                st.session_state.rp_system_prompt = system_prompt

                # AI 고객 첫 인사
                opening = get_opening_message(system_prompt)
                st.session_state.rp_history.append({
                    "role": "assistant", "content": opening
                })

            st.session_state.rp_phase = "playing"
            st.rerun()

    # ── Phase 2: 롤플레이 대화 ──
    elif st.session_state.rp_phase == "playing":
        scenario = SCENARIOS[st.session_state.rp_scenario]
        persona = PERSONAS[st.session_state.rp_persona]

        st.header(f"🎭 {scenario['title']}")
        col_info, col_end = st.columns([3, 1])
        with col_info:
            st.caption(
                f"고객: {scenario['customer_role']} | "
                f"난이도: {persona['label']} | "
                f"대화 {len([m for m in st.session_state.rp_history if m['role'] == 'user'])}턴"
            )
        with col_end:
            if st.button("⏹️ 롤플레이 종료 & 피드백 받기"):
                if len(st.session_state.rp_history) < 2:
                    st.warning("최소 1턴 이상 대화 후 종료하세요.")
                else:
                    st.session_state.rp_phase = "feedback"
                    st.rerun()

        st.divider()

        # 힌트 버튼 (show_hints가 True인 경우에만 표시)
        if persona.get("show_hints", False):
            user_turn_count = len([m for m in st.session_state.rp_history if m["role"] == "user"])
            questions = scenario["key_questions"]
            with st.expander("💡 막히면 눌러보세요 — 예상 질문 힌트"):
                for i, q in enumerate(questions):
                    if i < user_turn_count:
                        st.markdown(f"- ~~{q}~~ ✅")
                    elif i == user_turn_count:
                        st.markdown(f"- **👉 {q}**")
                    else:
                        st.markdown(f"- {q}")
                remaining = max(0, len(questions) - user_turn_count)
                st.caption(f"남은 예상 질문: {remaining}개 — 다음 질문에 대한 답변을 준비하세요.")

        # 대화 표시
        for msg in st.session_state.rp_history:
            role = "assistant" if msg["role"] == "assistant" else "user"
            avatar = "👤" if role == "assistant" else "🧑"
            name = scenario["customer_role"] if role == "assistant" else "나 (사업담당)"
            with st.chat_message(role, avatar=avatar):
                st.markdown(f"**{name}**")
                st.markdown(msg["content"])

        # 사용자 입력
        user_input = st.chat_input("사업담당자로서 응답하세요...")

        if user_input:
            st.session_state.rp_history.append({"role": "user", "content": user_input})

            with st.chat_message("user", avatar="🧑"):
                st.markdown(f"**나 (사업담당)**")
                st.markdown(user_input)

            # AI 고객 응답
            with st.chat_message("assistant", avatar="👤"):
                st.markdown(f"**{scenario['customer_role']}**")
                with st.spinner("고객이 생각 중..."):
                    ai_response = get_ai_response(
                        st.session_state.rp_system_prompt,
                        st.session_state.rp_history,
                    )
                st.markdown(ai_response)

            st.session_state.rp_history.append({"role": "assistant", "content": ai_response})

            # 마무리 멘트 감지
            endings = ["내부적으로 검토", "다시 연락", "오늘은 여기까지", "감사합니다. 검토"]
            if any(e in ai_response for e in endings):
                st.info("고객이 미팅 마무리를 시사했습니다. '롤플레이 종료 & 피드백 받기' 버튼을 눌러주세요.")

            st.rerun()

    # ── Phase 3: 피드백 ──
    elif st.session_state.rp_phase == "feedback":
        scenario = SCENARIOS[st.session_state.rp_scenario]
        persona = PERSONAS[st.session_state.rp_persona]

        st.header("📊 롤플레이 피드백")
        st.caption(f"{scenario['title']} | {persona['label']}")

        # 피드백 생성
        if st.session_state.rp_feedback is None:
            with st.spinner("대화를 분석하고 피드백을 생성 중입니다..."):
                fb = analyze_roleplay(
                    st.session_state.rp_history,
                    scenario["title"],
                    st.session_state.rp_persona,
                )
                st.session_state.rp_feedback = fb

        fb = st.session_state.rp_feedback

        if "error" in fb:
            st.error(fb["error"])
        else:
            # 종합 점수
            grade_colors = {"A": "green", "B": "blue", "C": "orange", "D": "red"}
            grade = fb.get("overall_score", "?")
            st.markdown(f"### 종합 등급: :{grade_colors.get(grade, 'gray')}[**{grade}**]")

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("✅ 잘한 점")
                for s in fb.get("strengths", []):
                    st.markdown(f"- {s}")

            with col2:
                st.subheader("📈 개선할 점")
                for s in fb.get("improvements", []):
                    st.markdown(f"- {s}")

            st.divider()

            # 용어 체크
            term_check = fb.get("terminology_check", {})
            if term_check:
                st.subheader("📝 도메인 용어 사용 분석")
                tc1, tc2 = st.columns(2)
                with tc1:
                    used = term_check.get("correctly_used", [])
                    if used:
                        st.success("정확히 사용한 용어: " + ", ".join(used))
                with tc2:
                    missed = term_check.get("missed_or_wrong", [])
                    if missed:
                        st.warning("놓쳤거나 부정확한 용어: " + ", ".join(missed))
                tip = term_check.get("tip", "")
                if tip:
                    st.info(f"💡 {tip}")

            st.divider()

            # Best / Worst moment
            col3, col4 = st.columns(2)
            with col3:
                st.subheader("🌟 베스트 모먼트")
                st.markdown(fb.get("best_moment", "-"))
            with col4:
                st.subheader("😅 아쉬운 모먼트")
                st.markdown(fb.get("worst_moment", "-"))

            # 전문가 모범 답변
            expert = fb.get("expert_answer", "")
            if expert:
                st.subheader("🎓 전문가 모범 답변")
                st.info(expert)

            # 다음 집중 포인트
            next_focus = fb.get("next_focus", "")
            if next_focus:
                st.subheader("🎯 다음 연습 집중 포인트")
                st.warning(next_focus)

        st.divider()

        # 대화 기록 보기
        with st.expander("📜 전체 대화 기록"):
            for msg in st.session_state.rp_history:
                role = "👤 고객" if msg["role"] == "assistant" else "🧑 나"
                st.markdown(f"**{role}:** {msg['content']}")
                st.markdown("---")

        # 다시 하기
        col_retry, col_new = st.columns(2)
        with col_retry:
            if st.button("🔄 같은 시나리오 다시 연습", use_container_width=True):
                st.session_state.rp_phase = "playing"
                st.session_state.rp_history = []
                st.session_state.rp_feedback = None
                with st.spinner("AI 고객을 준비하고 있습니다..."):
                    opening = get_opening_message(st.session_state.rp_system_prompt)
                    st.session_state.rp_history.append({
                        "role": "assistant", "content": opening
                    })
                st.rerun()
        with col_new:
            if st.button("🆕 새 시나리오 선택", use_container_width=True):
                st.session_state.rp_phase = "setup"
                st.session_state.rp_history = []
                st.session_state.rp_feedback = None
                st.session_state.rp_persona = ""
                st.session_state.rp_scenario = ""
                st.session_state.rp_system_prompt = ""
                st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 탭 2: 도메인 퀴즈
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_quiz:
    st.header("🎯 IPCC/AICC 도메인 퀴즈")
    st.caption("도메인 지식을 퀴즈로 테스트해보세요. 사전 생성된 문제 풀에서 즉시 출제됩니다.")

    from quiz import QUIZ_CATEGORIES, load_quiz_from_pool

    col1, col2 = st.columns(2)
    with col1:
        quiz_cat = st.selectbox("카테고리", ["랜덤"] + QUIZ_CATEGORIES)
    with col2:
        quiz_diff = st.selectbox("난이도", ["초급", "중급", "고급"])

    if "quiz_data" not in st.session_state:
        st.session_state.quiz_data = None
    if "quiz_answered" not in st.session_state:
        st.session_state.quiz_answered = False
    if "quiz_score" not in st.session_state:
        st.session_state.quiz_score = {"correct": 0, "total": 0}

    score = st.session_state.quiz_score
    if score["total"] > 0:
        st.metric(
            "현재 점수",
            f"{score['correct']}/{score['total']}",
            f"{score['correct']/score['total']*100:.0f}%",
        )

    if st.button("🎲 새 문제", type="primary"):
        cat = None if quiz_cat == "랜덤" else quiz_cat
        quiz_from_pool = load_quiz_from_pool(category=cat, difficulty=quiz_diff)
        if quiz_from_pool:
            st.session_state.quiz_data = quiz_from_pool
            st.session_state.quiz_answered = False
        else:
            with st.spinner("퀴즈 풀이 없어서 실시간 생성 중..."):
                import asyncio
                from quiz import generate_quiz
                st.session_state.quiz_data = asyncio.run(generate_quiz(category=cat, difficulty=quiz_diff))
                st.session_state.quiz_answered = False

    quiz = st.session_state.quiz_data
    if quiz:
        st.divider()
        st.subheader(f"📝 [{quiz['category']}] {quiz['difficulty']}")
        st.markdown(f"**{quiz['question']}**")

        selected = st.radio(
            "답을 선택하세요:",
            quiz["options"],
            key=f"quiz_answer_{quiz['question'][:20]}",
        )

        if st.button("✅ 정답 확인") and not st.session_state.quiz_answered:
            st.session_state.quiz_answered = True
            user_answer = selected[0]
            correct = quiz["answer"]
            st.session_state.quiz_score["total"] += 1
            if user_answer == correct:
                st.session_state.quiz_score["correct"] += 1
                st.success(f"🎉 정답! ({correct})")
            else:
                st.error(f"❌ 오답. 정답은 **{correct}** 입니다.")
            st.info(f"📚 **해설:** {quiz['explanation']}")
            st.rerun()

        if st.session_state.quiz_answered:
            user_answer = selected[0]
            correct = quiz["answer"]
            if user_answer == correct:
                st.success(f"🎉 정답! ({correct})")
            else:
                st.error(f"❌ 오답. 정답은 **{correct}** 입니다.")
            st.info(f"📚 **해설:** {quiz['explanation']}")

    if st.button("🔄 점수 초기화"):
        st.session_state.quiz_score = {"correct": 0, "total": 0}
        st.session_state.quiz_data = None
        st.session_state.quiz_answered = False
        st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 탭 3: 용어 사전
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_glossary:
    st.header("📖 컨택센터 용어 사전")
    st.caption("교육자료의 정식 용어와 고객이 현장에서 사용하는 표현을 매핑합니다.")

    @st.cache_data
    def load_glossary():
        from config import GLOSSARY_PATH
        text = GLOSSARY_PATH.read_text(encoding="utf-8")
        categories = {}
        current_cat = None
        rows = []
        for line in text.split("\n"):
            if line.startswith("## ") and not line.startswith("## 교육"):
                if current_cat and rows:
                    categories[current_cat] = rows
                current_cat = line.replace("## ", "").strip()
                rows = []
            elif line.startswith("|") and current_cat and "---" not in line and "정식 용어" not in line:
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if len(cells) >= 4:
                    rows.append({
                        "정식 용어": cells[0],
                        "약어": cells[1],
                        "교육자료 정의": cells[2],
                        "고객 실제 표현": cells[3],
                        "비고": cells[4] if len(cells) > 4 else "",
                    })
        if current_cat and rows:
            categories[current_cat] = rows
        return categories

    glossary = load_glossary()
    search = st.text_input("🔍 용어 검색 (정식 용어, 약어, 고객 표현 모두 검색)")
    selected_cats = st.multiselect(
        "카테고리 필터",
        options=list(glossary.keys()),
        default=list(glossary.keys()),
    )

    for cat_name in selected_cats:
        terms = glossary.get(cat_name, [])
        if search:
            search_lower = search.lower()
            terms = [t for t in terms if any(
                search_lower in str(v).lower() for v in t.values()
            )]
        if not terms:
            continue
        st.subheader(f"📂 {cat_name} ({len(terms)}개)")
        for term in terms:
            with st.expander(f"**{term['정식 용어']}** ({term['약어']})"):
                st.markdown(f"**교육자료 정의:** {term['교육자료 정의']}")
                st.markdown(f"**고객 실제 표현:** {term['고객 실제 표현']}")
                if term['비고']:
                    st.info(f"💡 {term['비고']}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 탭 4: 아키텍처 가이드
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_arch:
    st.header("🏗️ IPCC 아키텍처 & AICC 기능 가이드")
    arch_section = st.radio(
        "섹션 선택",
        ["IPCC 전체 구조", "콜 플로우", "AICC 전환", "벤더 비교"],
        horizontal=True,
    )

    if arch_section == "IPCC 전체 구조":
        st.subheader("IPCC 전체 아키텍처")
        st.code("""
고객 전화 → 통신사(PSTN) → E1/PRI 회선 → 보이스 게이트웨이
    → IP-PBX(교환기) → IVR → CTI → 상담원(Softphone + 상담AP)
    → CRM/기관계/녹취
        """, language="text")
        st.markdown("""
#### 핵심 구성요소

| 구성요소 | 역할 | 핵심 포인트 |
|----------|------|------------|
| **PBX** | 교환기 — 전화 통신 관리 | 대표번호, 회선번호, 내선번호, 스킬그룹 보유 |
| **CTI** | 미들웨어 — 교환기+컴퓨터 통합 | "CTI 없으면 IPCC 아니다" |
| **IVR** | 자동응답 시스템 | ARS(일방향) vs IVR(양방향) 구분 중요 |
| **녹취** | 통화 녹음/저장 | 스테레오 녹취 = AI의 전제조건 (화자분리) |
| **상담AP** | 상담원 통합 업무 화면 | 소프트폰 + CRM + 기관계 연동 |

#### IPT vs IPCC 차이

| 구분 | IPT | IPCC |
|------|-----|------|
| 구성 | PBX + IVR | PBX + IVR + **CTI** + 녹취 + 상담AP |
| 기능 | 단순 전화 연결 | 고객정보 연동, 라우팅, 통계 |
| 데이터 | 통신 데이터만 | 기관계 연동 고객 정보 |
        """)

    elif arch_section == "콜 플로우":
        st.subheader("인바운드 콜 플로우")
        st.markdown("""
```
1. 고객 → PSTN → E1/PRI → 보이스 게이트웨이 (TDM→IP 변환)
2. → PBX (교환기): 대표번호로 인입
3. → IVR: "1번 상담, 2번 조회..." 안내
4. → CTI: 고객 정보 조회 + 적합한 상담원 그룹으로 라우팅
5. → 상담원 소프트폰 울림 + 상담AP에 고객 정보 팝업
6. → 통화 중: 녹취 시작 + STT(실시간) + 상담 어드바이저
7. → 통화 종료: TA(Text Analytics) → 상담 요약/분류
```

#### ACD 라우팅 방식
- **스킬 기반**: 상담 유형별 그룹 → 해당 스킬 보유 상담원에게 배분
- **우선순위**: 대기 시간, 상담원 숙련도 등 기준
- **오버플로우**: 특정 그룹 포화 시 → 다른 그룹으로 넘김
        """)

    elif arch_section == "AICC 전환":
        st.subheader("IPCC → AICC 전환")
        st.markdown("""
#### AICC = IPCC + AI 기술

| AI 기능 | 설명 | 기반 기술 |
|---------|------|----------|
| **실시간 STT** | 통화 내용 실시간 텍스트화 | EC STT (97% 인식률) |
| **상담 어드바이저** | 상담 중 지식 추천/가이드 | STT + RAG |
| **AI 콜봇** | 음성 자동 응답 | STT + LLM + TTS |
| **AI 챗봇** | 텍스트 자동 응답 | LLM + RAG |
| **TA (Text Analytics)** | 상담 후 분석/요약 | STT + NLP |
| **QA 자동화** | 상담 품질 자동 평가 | STT + 규칙/AI |

#### 전환 시 핵심 고려사항
1. **녹취 방식**: 모노 → **스테레오** 전환 필수 (화자분리 전제)
2. **SBC/SIPREC**: RTP 스트리밍으로 AI에 실시간 음성 전달
3. **온프레미스 vs 클라우드**: 금융권은 온프렘 선호
4. **레이턴시**: 콜봇 응답 2.5초 → 고객 수용 가능 기준
        """)

    elif arch_section == "벤더 비교":
        st.subheader("주요 IPCC/AICC 벤더")
        st.markdown("""
| 벤더 | 특징 | 점유율 |
|------|------|--------|
| **어바이어 (Avaya)** | 글로벌 1위, 전용 장비(어플라이언스) | 국내 대형 금융사 다수 |
| **시스코 (Cisco)** | 네트워크 기반, 자체 VGW | 대기업 선호 |
| **제네시스 (Genesys)** | 클라우드 강점, PureCloud | 클라우드 전환 시 선호 |
| **브리지텍/EICN** | 국산, 범용서버+SW 방식, SBC 사용 | 국내 중소형 |

#### LG U+ AICC 솔루션 차별점
- **EC STT/TTS**: 자체 음성엔진 (익시젠 기반)
- **구축형 + 클라우드 하이브리드**: 금융권 온프렘 대응
- **LLM 콜봇**: 룰베이스 + LLM 하이브리드 아키텍처
- **캐싱**: 반복 질문 → LLM 미경유 → 즉시 답변
        """)
