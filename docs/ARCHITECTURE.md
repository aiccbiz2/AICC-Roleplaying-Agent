# AICC Meeting Simulator — 회의록

## 안건 목록

- [ ] 사전컨설팅 WBS
- [ ] 파트너사 TMM 후보
- [ ] PQ 진행현황
- [ ] 상담어드바이저 아웃소싱사 분석 (기능별 상세) 회의
- [ ] News PRD → 최종우님
- [ ] C Agent Module → Github Push (배홍주님)
- [ ] 견적표준화를 위한 논의 (견적서 모음)
- [ ] AICC_Meeting_Simulator

---

## AICC Meeting Simulator — 아키텍처 구성도

### 전체 시스템 아키텍처

```mermaid
graph TB
    subgraph Frontend["🖥️ Frontend (Vanilla HTML + Tailwind CSS)"]
        IDX["index.html<br/>대시보드"]
        SIM["simulation.html<br/>롤플레이 시뮬레이션"]
        QUIZ["quiz.html<br/>10문제 퀴즈 모드"]
        DICT["dictionary.html<br/>도메인 용어사전"]
    end

    subgraph Backend["⚙️ Backend (FastAPI · Python)"]
        MAIN["main.py<br/>FastAPI 서버<br/>:8000"]
        RP["roleplay.py<br/>25 시나리오<br/>8단계 × 6업종"]
        QZ["quiz.py<br/>퀴즈 풀 로딩<br/>+ LLM 생성"]
        FB["feedback.py<br/>롤플레이<br/>피드백 분석"]
        RAG["rag.py<br/>RAG 파이프라인<br/>질문→검색→답변"]
        CFG["config.py<br/>설정 관리"]
    end

    subgraph LLM["🤖 LLM (Claude CLI · Pro/Max 구독)"]
        CLI["llm.py<br/>subprocess 래퍼"]
        CLAUDE["Claude CLI<br/>model: sonnet<br/>OAuth 인증"]
    end

    subgraph VectorDB["📦 Vector Store"]
        ING["ingest.py<br/>문서 인제스트"]
        EMB["HuggingFace<br/>intfloat/<br/>multilingual-e5-small<br/>(로컬 · CPU)"]
        CHROMA["ChromaDB<br/>chroma_db/"]
    end

    subgraph Docs["📁 docs/ (지식 베이스)"]
        ED["교육자료/"]
        MT["고객미팅/"]
        GL["도메인_용어사전.md"]
        QP["고객질문_패턴DB.md"]
        SC["롤플레이_시나리오.md"]
        POOL["quiz_pool.json<br/>(80문제)"]
    end

    %% Frontend → Backend
    IDX -->|"GET /"| MAIN
    SIM -->|"GET /simulation"| MAIN
    QUIZ -->|"GET /quiz"| MAIN
    DICT -->|"GET /dictionary"| MAIN

    %% API Routes
    SIM -->|"POST /api/roleplay/start"| RP
    SIM -->|"POST /api/roleplay/respond"| RP
    SIM -->|"POST /api/roleplay/feedback"| FB
    SIM -->|"GET /api/scenarios<br/>GET /api/stages<br/>GET /api/industries"| RP
    QUIZ -->|"GET /api/quiz/set<br/>GET /api/quiz/categories"| QZ
    DICT -->|"GET /api/glossary"| MAIN

    %% Backend → LLM
    RP --> CLI
    QZ --> CLI
    FB --> CLI
    RAG --> CLI
    CLI --> CLAUDE

    %% Backend → RAG
    RP -->|"retrieve(query, top_k=3)"| RAG
    QZ -->|"retrieve(category, top_k=4)"| RAG
    RAG -->|"similarity_search"| CHROMA

    %% Ingest Pipeline
    Docs -->|"*.md, *.txt"| ING
    ING -->|"TextLoader<br/>→ chunk(1000/200)"| EMB
    EMB -->|"embedding vectors"| CHROMA

    %% Quiz Pool
    POOL -.->|"즉시 로딩<br/>(LLM 불필요)"| QZ

    %% Styling
    classDef frontend fill:#dbeafe,stroke:#3b82f6,color:#1e3a5f
    classDef backend fill:#fef3c7,stroke:#f59e0b,color:#78350f
    classDef llm fill:#ede9fe,stroke:#8b5cf6,color:#4c1d95
    classDef vector fill:#d1fae5,stroke:#10b981,color:#065f46
    classDef docs fill:#fce7f3,stroke:#ec4899,color:#831843

    class IDX,SIM,QUIZ,DICT frontend
    class MAIN,RP,QZ,FB,RAG,CFG backend
    class CLI,CLAUDE llm
    class ING,EMB,CHROMA vector
    class ED,MT,GL,QP,SC,POOL docs
```

### 데이터 플로우 (롤플레이 시뮬레이션)

```mermaid
sequenceDiagram
    participant U as 👤 사용자
    participant FE as 🖥️ simulation.html
    participant API as ⚙️ FastAPI
    participant RP as 🎭 roleplay.py
    participant RAG as 📚 RAG (ChromaDB)
    participant LLM as 🤖 Claude CLI

    U->>FE: 1. 단계 탭 + 업종 필터 선택
    FE->>API: GET /api/scenarios, /api/stages
    API-->>FE: 25개 시나리오 + 8단계 반환

    U->>FE: 2. 시나리오 + 난이도 선택 → 시작
    FE->>API: POST /api/roleplay/start
    API->>RP: build_system_prompt(scenario, persona)
    RP->>RAG: retrieve(query, top_k=3)
    RAG-->>RP: 관련 문서 3건
    RP->>LLM: call_claude(시스템프롬프트 + 미팅시작)
    LLM-->>RP: AI 고객 첫 인사
    RP-->>FE: system_prompt + opening message

    loop 대화 반복 (8~15턴)
        U->>FE: 3. 사업담당자로서 응답 입력
        FE->>API: POST /api/roleplay/respond
        API->>LLM: call_claude(시스템프롬프트 + 대화이력)
        LLM-->>FE: AI 고객 응답
    end

    U->>FE: 4. 피드백 요청
    FE->>API: POST /api/roleplay/feedback
    API->>LLM: call_claude(피드백 프롬프트 + 전체대화)
    LLM-->>FE: 종합 평가 (A~D등급 + 상세 분석)
```

### 기술 스택 요약

| 레이어 | 기술 | 비고 |
|--------|------|------|
| **Frontend** | Vanilla HTML + Tailwind CSS + JS | SPA (단일 페이지) |
| **Backend** | FastAPI (Python) | uvicorn, port 8000 |
| **LLM** | Claude CLI (sonnet) | Pro/Max 구독 OAuth · API Key 불필요 |
| **Embedding** | intfloat/multilingual-e5-small | HuggingFace · 로컬 CPU |
| **Vector DB** | ChromaDB | 로컬 저장 (chroma_db/) |
| **RAG** | LangChain | chunk 1000/200, top_k=5 |
| **데이터** | 170+ 실제 미팅 트랜스크립트 | Discord → docs/ |

### 시나리오 매트릭스

```mermaid
graph LR
    subgraph Axis1["축1: 영업 단계 (필수)"]
        A["A. 첫 미팅"]
        B["B. 시연/데모"]
        C["C. 기술 Q&A"]
        D["D. 견적/제안서"]
        E["E. PoC 사전"]
        F["F. PoC 리뷰"]
        G["G. 운영 안정화"]
        H["H. 경쟁 입찰"]
    end

    subgraph Axis2["축2: 업종 (선택 필터)"]
        I1["금융 증권/보험"]
        I2["금융 은행/캐피탈"]
        I3["물류/유통"]
        I4["여행/서비스"]
        I5["이커머스"]
        I6["공공/특수"]
    end

    A --> |"4개"| SC1["25개 시나리오"]
    B --> |"3개"| SC1
    C --> |"3개"| SC1
    D --> |"3개"| SC1
    E --> |"3개"| SC1
    F --> |"3개"| SC1
    G --> |"3개"| SC1
    H --> |"3개"| SC1

    SC1 --- |"× 3 난이도"| P["초급 · 중급 · 고급<br/>= 75가지 조합"]

    classDef stage fill:#dbeafe,stroke:#3b82f6
    classDef ind fill:#fef3c7,stroke:#f59e0b
    classDef result fill:#d1fae5,stroke:#10b981

    class A,B,C,D,E,F,G,H stage
    class I1,I2,I3,I4,I5,I6 ind
    class SC1,P result
```

> **GitHub:** https://github.com/aiccbiz2/aicc_meeting_simulator (private)
> **실행:** `python main.py` → http://localhost:8000

