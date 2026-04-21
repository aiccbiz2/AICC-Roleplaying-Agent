"""FastAPI 서버 — AICC 롤플레이 시뮬레이터 v2"""
from __future__ import annotations

import importlib
import logging
import os
import threading
import time
import uvicorn
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

from db import (
    init_db, get_user, verify_password, log_access,
    save_roleplay_session, save_quiz_record,
    get_user_roleplay_sessions, get_user_quiz_records, get_roleplay_detail,
    get_overview_stats, get_all_members_summary, get_member_detail,
    get_access_logs, get_improvements_ranking, get_user_dashboard_stats,
    change_password,
)
from auth import create_token, get_current_user, require_admin


# ── 메모리 워치독 ──
_mem_logger = logging.getLogger("memory")


def _memory_watchdog(interval: int = 60):
    """주기적으로 프로세스 메모리를 로깅 (데몬 스레드)"""
    try:
        import psutil
    except ImportError:
        _mem_logger.warning("psutil 미설치 — 메모리 워치독 비활성화 (pip install psutil)")
        return

    proc = psutil.Process(os.getpid())
    _mem_logger.info("메모리 워치독 시작 (간격=%ds, PID=%d)", interval, os.getpid())

    while True:
        try:
            mem = proc.memory_info()
            cpu = proc.cpu_percent(interval=1)
            threads = proc.num_threads()
            try:
                handles = proc.num_handles()
            except AttributeError:
                handles = -1  # Linux/macOS

            rss_mb = mem.rss / 1024 / 1024
            vms_mb = mem.vms / 1024 / 1024

            _mem_logger.info(
                "RSS=%.0fMB VMS=%.0fMB CPU=%.1f%% Threads=%d Handles=%d",
                rss_mb, vms_mb, cpu, threads, handles,
            )

            # 경고 임계치: RSS 1GB 초과
            if rss_mb > 1024:
                _mem_logger.warning(
                    "HIGH MEMORY: RSS=%.0fMB (>1GB) — 메모리 누수 의심", rss_mb
                )
        except Exception as e:
            _mem_logger.error("워치독 에러: %s", e)

        time.sleep(interval)


# ── Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logging.getLogger("main").info("DB initialized, admin seeded")

    # 메모리 워치독 시작
    watchdog_interval = int(os.environ.get("MEM_WATCHDOG_INTERVAL", "60"))
    t = threading.Thread(target=_memory_watchdog, args=(watchdog_interval,), daemon=True)
    t.start()

    yield

app = FastAPI(title="AICC Roleplay Simulator", lifespan=lifespan)


# ── 메모리 모니터링 미들웨어 ──
@app.middleware("http")
async def memory_logging_middleware(request: Request, call_next):
    """요청별 메모리 변화를 추적하는 미들웨어"""
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem_before = proc.memory_info().rss / 1024 / 1024
    except ImportError:
        return await call_next(request)

    start_time = time.time()
    response = await call_next(request)
    elapsed = time.time() - start_time

    mem_after = proc.memory_info().rss / 1024 / 1024
    diff = mem_after - mem_before

    # 5MB 이상 증가하거나 3초 이상 걸린 요청만 로깅
    if abs(diff) > 5 or elapsed > 3:
        _mem_logger.warning(
            "%s %s — %.0fMB→%.0fMB (Δ%.1fMB) %.1fs",
            request.method, request.url.path,
            mem_before, mem_after, diff, elapsed,
        )

    return response


# ── Prometheus 메트릭 (설치 시 자동 활성화) ──
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    from prometheus_client import Gauge, REGISTRY
    import psutil as _psutil

    def _get_or_create_gauge(name, desc):
        """중복 등록 방지: 이미 존재하면 기존 것 반환"""
        try:
            return Gauge(name, desc)
        except ValueError:
            return REGISTRY._names_to_collectors.get(name)

    # 커스텀 시스템 메트릭 정의 (중복 방지)
    PROCESS_RSS = _get_or_create_gauge("process_memory_rss_mb", "Process RSS memory in MB")
    PROCESS_VMS = _get_or_create_gauge("process_memory_vms_mb", "Process VMS memory in MB")
    PROCESS_CPU = _get_or_create_gauge("process_cpu_percent", "Process CPU usage percent")
    PROCESS_THREADS = _get_or_create_gauge("process_thread_count", "Process thread count")
    PROCESS_HANDLES = _get_or_create_gauge("process_handle_count", "Process handle count (Windows)")
    SYSTEM_MEM_TOTAL = _get_or_create_gauge("system_memory_total_mb", "System total memory in MB")
    SYSTEM_MEM_AVAILABLE = _get_or_create_gauge("system_memory_available_mb", "System available memory in MB")
    SYSTEM_MEM_PERCENT = _get_or_create_gauge("system_memory_used_percent", "System memory used percent")
    SYSTEM_CPU_PERCENT = _get_or_create_gauge("system_cpu_percent", "System CPU usage percent")
    LLM_SEMAPHORE_AVAILABLE = _get_or_create_gauge("llm_semaphore_available", "LLM semaphore available slots")

    _proc = _psutil.Process(os.getpid())

    def _update_system_metrics(info):
        """Prometheus 스크래핑 시마다 시스템 메트릭 업데이트"""
        try:
            mem = _proc.memory_info()
            PROCESS_RSS.set(round(mem.rss / 1024 / 1024, 1))
            PROCESS_VMS.set(round(mem.vms / 1024 / 1024, 1))
            PROCESS_CPU.set(_proc.cpu_percent())
            PROCESS_THREADS.set(_proc.num_threads())
            try:
                PROCESS_HANDLES.set(_proc.num_handles())
            except AttributeError:
                pass

            sys_mem = _psutil.virtual_memory()
            SYSTEM_MEM_TOTAL.set(round(sys_mem.total / 1024 / 1024, 1))
            SYSTEM_MEM_AVAILABLE.set(round(sys_mem.available / 1024 / 1024, 1))
            SYSTEM_MEM_PERCENT.set(sys_mem.percent)
            SYSTEM_CPU_PERCENT.set(_psutil.cpu_percent())

            try:
                from llm import _llm_semaphore
                if _llm_semaphore is not None:
                    LLM_SEMAPHORE_AVAILABLE.set(_llm_semaphore._value)
            except Exception:
                pass
        except Exception:
            pass

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_group_untemplated=True,
        excluded_handlers=["/metrics", "/api/debug/health"],
    )
    instrumentator.add(lambda info: _update_system_metrics(info))
    instrumentator.instrument(app).expose(app, endpoint="/metrics")
    logging.getLogger("main").info("Prometheus metrics enabled at /metrics (with system metrics)")

except ImportError:
    logging.getLogger("main").info(
        "prometheus-fastapi-instrumentator 미설치 — /metrics 비활성 (pip install prometheus-fastapi-instrumentator)"
    )

# ── Static files ──
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Pydantic Models ──
class LoginRequest(BaseModel):
    id: str
    password: str

class StartRoleplayRequest(BaseModel):
    scenario: str
    persona: str

class RoleplayRespondRequest(BaseModel):
    system_prompt: str
    history: list[dict]
    mode: str = "free_text"
    persona: str = ""  # "free_text" | "multiple_choice"

class FeedbackRequest(BaseModel):
    history: list[dict]
    scenario_title: str
    persona_level: str
    mode: str = "free_text"
    answer_history: list[dict] | None = None

class SaveRoleplayRequest(BaseModel):
    scenario_key: str
    scenario_title: str
    persona_level: str
    overall_grade: str | None = None
    conversation: list[dict]
    feedback: dict | None = None
    turn_count: int
    started_at: str | None = None
    duration_seconds: int | None = None

class UpdateRoleplayRequest(BaseModel):
    conversation: list[dict] | None = None
    feedback: dict | None = None
    overall_grade: str | None = None
    turn_count: int | None = None
    duration_seconds: int | None = None

class SaveQuizRequest(BaseModel):
    category: str
    difficulty: str
    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class AccessLogRequest(BaseModel):
    action: str
    page: str | None = None


# ══════════════════════════════════════════════════════════
# 공개 API (인증 불필요)
# ══════════════════════════════════════════════════════════

# ── Auth API ──
@app.post("/api/auth/login")
async def api_login(req: LoginRequest, request: Request):
    user = get_user(req.id)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    token = create_token(user["id"], user["role"], user["name"], user["department"], user["position"])
    # 로그인 접속 로그
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    log_access(user["id"], "login", "/login", ip, ua)
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "department": user["department"],
            "position": user["position"],
            "role": user["role"],
        },
    }


# ── Page Routes ──
@app.get("/login")
async def page_login():
    return FileResponse("static/hero.html")

@app.get("/")
async def page_dashboard():
    return FileResponse("static/index.html")

@app.get("/simulation")
async def page_simulation():
    return FileResponse("static/simulation.html")

@app.get("/quiz")
async def page_quiz():
    return FileResponse("static/quiz.html")

@app.get("/dictionary")
async def page_dictionary():
    return FileResponse("static/dictionary.html")

@app.get("/lectures")
async def page_lectures():
    return FileResponse("static/lectures.html")

@app.get("/history")
async def page_history():
    return FileResponse("static/history.html")

@app.get("/admin")
async def page_admin():
    return FileResponse("static/admin.html")


# ══════════════════════════════════════════════════════════
# 인증 필요 API
# ══════════════════════════════════════════════════════════

# ── Auth: 현재 사용자 ──
@app.get("/api/auth/me")
async def api_me(user: dict = Depends(get_current_user)):
    return user


# ── 접속 로그 ──
@app.post("/api/access-log")
async def api_access_log(req: AccessLogRequest, request: Request, user: dict = Depends(get_current_user)):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    log_access(user["id"], req.action, req.page, ip, ua)
    return {"ok": True}


# ── API: Scenarios & Personas ──
@app.get("/api/scenarios")
async def get_scenarios(user: dict = Depends(get_current_user)):
    import roleplay
    importlib.reload(roleplay)
    return roleplay.SCENARIOS

@app.get("/api/personas")
async def get_personas(user: dict = Depends(get_current_user)):
    from roleplay import PERSONAS
    return PERSONAS

@app.get("/api/stages")
async def get_stages(user: dict = Depends(get_current_user)):
    from roleplay import STAGES
    return STAGES

@app.get("/api/industries")
async def get_industries(user: dict = Depends(get_current_user)):
    from roleplay import INDUSTRIES
    return INDUSTRIES


# ── API: Roleplay ──
@app.post("/api/roleplay/start")
async def start_roleplay(req: StartRoleplayRequest, user: dict = Depends(get_current_user)):
    from roleplay import (
        build_system_prompt, build_system_prompt_mc,
        get_opening_message_async, get_opening_with_choices_async,
        PERSONAS,
    )
    persona = PERSONAS.get(req.persona, {})
    mode = persona.get("mode", "free_text")

    if mode == "multiple_choice":
        system_prompt = build_system_prompt_mc(req.scenario)
        result = await get_opening_with_choices_async(system_prompt)
        return {
            "system_prompt": system_prompt,
            "opening": result.get("response", ""),
            "mode": "multiple_choice",
            "choices": result.get("choices", []),
            "correct_index": result.get("correct_index", 0),
            "explanation": result.get("explanation", ""),
            "show_hints": False,
        }
    else:
        system_prompt = build_system_prompt(req.scenario, req.persona)
        opening = await get_opening_message_async(system_prompt)

        # 힌트는 시작 시점에 생성하지 않음 (응답 시간 단축)
        # 첫 사업담당자 응답 이후 turn부터 /api/roleplay/respond에서 생성됨
        return {
            "system_prompt": system_prompt,
            "opening": opening,
            "mode": "free_text",
            "choices": [],
            "show_hints": persona.get("show_hints", False),
            "keywords": [],
        }

@app.post("/api/roleplay/respond")
async def roleplay_respond(req: RoleplayRespondRequest, user: dict = Depends(get_current_user)):
    from roleplay import get_ai_response_async, get_ai_response_with_choices_async, generate_dynamic_hints_async, PERSONAS

    if req.mode == "multiple_choice":
        result = await get_ai_response_with_choices_async(req.system_prompt, req.history)
        return {
            "response": result.get("response", ""),
            "choices": result.get("choices", []),
            "correct_index": result.get("correct_index", 0),
            "explanation": result.get("explanation", ""),
        }
    else:
        try:
            response = await get_ai_response_async(req.system_prompt, req.history)
        except Exception as e:
            logging.getLogger("main").error(
                "roleplay_respond LLM 호출 실패: %s", e, exc_info=True,
            )
            raise HTTPException(
                status_code=503,
                detail=f"LLM 응답 생성 실패: {str(e)[:200]}",
            )
        if not response:
            raise HTTPException(
                status_code=503,
                detail="LLM이 빈 응답을 반환했습니다. Ollama 상태를 확인해주세요.",
            )
        # 힌트는 별도 /api/roleplay/hint 엔드포인트에서 비동기 처리 (응답 속도 우선)
        return {"response": response}

class HintRequest(BaseModel):
    message: str
    scenario: str = ""


@app.post("/api/roleplay/hint")
async def roleplay_hint(req: HintRequest, user: dict = Depends(get_current_user)):
    """사전 정의 키워드 힌트 반환 (LLM 호출 없음, 즉시 응답)"""
    from roleplay import match_hints
    keywords = match_hints(req.scenario, req.message) if req.scenario else []
    return {"keywords": keywords}


@app.post("/api/roleplay/feedback")
async def roleplay_feedback(req: FeedbackRequest, user: dict = Depends(get_current_user)):
    from feedback import analyze_roleplay_async
    result = await analyze_roleplay_async(
        req.history, req.scenario_title, req.persona_level,
        mode=req.mode, answer_history=req.answer_history,
    )
    return result


# ── API: Quiz ──
@app.get("/api/quiz")
async def get_quiz(category: str = None, difficulty: str = "중급", user: dict = Depends(get_current_user)):
    from quiz import load_quiz_from_pool, generate_quiz
    quiz = load_quiz_from_pool(category=category, difficulty=difficulty)
    if quiz:
        return quiz
    return await generate_quiz(category=category, difficulty=difficulty)

@app.get("/api/quiz/set")
async def get_quiz_set(category: str = None, difficulty: str = "중급", count: int = 10, user: dict = Depends(get_current_user)):
    from quiz import load_quiz_set_from_pool
    quizzes = load_quiz_set_from_pool(category=category, difficulty=difficulty, count=count)
    return {"quizzes": quizzes, "total": len(quizzes)}

@app.get("/api/quiz/categories")
async def get_quiz_categories(user: dict = Depends(get_current_user)):
    from quiz import QUIZ_CATEGORIES
    return QUIZ_CATEGORIES


# ── API: Glossary (캐시 적용) ──
_glossary_cache: dict | None = None
_glossary_mtime: float = 0.0


@app.get("/api/glossary")
async def get_glossary(user: dict = Depends(get_current_user)):
    global _glossary_cache, _glossary_mtime
    from config import GLOSSARY_PATH

    current_mtime = GLOSSARY_PATH.stat().st_mtime
    if _glossary_cache is not None and current_mtime == _glossary_mtime:
        return _glossary_cache

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
                    "term": cells[0],
                    "abbr": cells[1],
                    "definition": cells[2],
                    "field_expression": cells[3],
                    "note": cells[4] if len(cells) > 4 else "",
                })
    if current_cat and rows:
        categories[current_cat] = rows

    _glossary_cache = categories
    _glossary_mtime = current_mtime
    return categories


# ── API: Change Password ──
@app.post("/api/auth/change-password")
async def api_change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    db_user = get_user(user["id"])
    if not db_user or not verify_password(req.current_password, db_user["password_hash"]):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")
    if len(req.new_password) < 4:
        raise HTTPException(status_code=400, detail="새 비밀번호는 4자 이상이어야 합니다.")
    change_password(user["id"], req.new_password)
    return {"message": "비밀번호가 변경되었습니다."}

# ── API: Dashboard Stats ──
@app.get("/api/my-stats")
async def my_stats(user: dict = Depends(get_current_user)):
    return get_user_dashboard_stats(user["id"])

# ── API: DB Status ──
@app.get("/api/db-status")
async def db_status(user: dict = Depends(get_current_user)):
    from config import CHROMA_DIR
    ready = CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir())
    return {"ready": ready}

@app.post("/api/build-db")
async def build_db(user: dict = Depends(get_current_user)):
    from ingest import ingest
    ingest()
    return {"status": "ok"}


# ══════════════════════════════════════════════════════════
# 이력 저장/조회 API
# ══════════════════════════════════════════════════════════

@app.post("/api/history/roleplay")
async def save_roleplay(req: SaveRoleplayRequest, user: dict = Depends(get_current_user)):
    session_id = save_roleplay_session(
        user_id=user["id"],
        scenario_key=req.scenario_key,
        scenario_title=req.scenario_title,
        persona_level=req.persona_level,
        overall_grade=req.overall_grade,
        conversation=req.conversation,
        feedback=req.feedback,
        turn_count=req.turn_count,
        started_at=req.started_at,
        duration_seconds=req.duration_seconds,
    )
    return {"id": session_id}

@app.post("/api/history/quiz")
async def save_quiz(req: SaveQuizRequest, user: dict = Depends(get_current_user)):
    record_id = save_quiz_record(
        user_id=user["id"],
        category=req.category,
        difficulty=req.difficulty,
        question=req.question,
        user_answer=req.user_answer,
        correct_answer=req.correct_answer,
        is_correct=req.is_correct,
    )
    return {"id": record_id}

@app.get("/api/history/roleplay")
async def get_my_roleplay(user: dict = Depends(get_current_user)):
    return get_user_roleplay_sessions(user["id"])

@app.get("/api/history/quiz")
async def get_my_quiz(user: dict = Depends(get_current_user)):
    return get_user_quiz_records(user["id"])

@app.get("/api/history/roleplay/{session_id}")
async def get_my_roleplay_detail(session_id: int, user: dict = Depends(get_current_user)):
    detail = get_roleplay_detail(session_id, user_id=user["id"])
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail

@app.patch("/api/history/roleplay/{session_id}")
async def update_roleplay(session_id: int, req: UpdateRoleplayRequest, user: dict = Depends(get_current_user)):
    from db import update_roleplay_session
    success = update_roleplay_session(
        session_id=session_id,
        user_id=user["id"],
        conversation=req.conversation,
        feedback=req.feedback,
        overall_grade=req.overall_grade,
        turn_count=req.turn_count,
        duration_seconds=req.duration_seconds,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or not owned by user")
    return {"ok": True}


# ══════════════════════════════════════════════════════════
# 관리자 전용 API
# ══════════════════════════════════════════════════════════

@app.get("/api/admin/overview")
async def admin_overview(user: dict = Depends(require_admin)):
    return get_overview_stats()

@app.get("/api/admin/members")
async def admin_members(user: dict = Depends(require_admin)):
    return get_all_members_summary()

@app.get("/api/admin/members/{member_id}")
async def admin_member_detail(member_id: str, user: dict = Depends(require_admin)):
    try:
        return get_member_detail(member_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Member not found")

@app.get("/api/admin/access-logs")
async def admin_access_logs(
    user_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    return get_access_logs(user_id=user_id, start_date=start_date, end_date=end_date, page=page)

@app.post("/api/admin/report")
async def admin_report(user: dict = Depends(require_admin)):
    from admin_report import generate_team_report
    members = get_all_members_summary()
    detail_list = []
    for m in members:
        detail_list.append(get_member_detail(m["id"]))
    report = await generate_team_report(members, detail_list)
    return {"report": report}

@app.get("/api/admin/improvements")
async def admin_improvements(user: dict = Depends(require_admin)):
    return get_improvements_ranking()


# ══════════════════════════════════════════════════════════
# LLM 설정 & Gemini 사용량 (관리자 전용)
# ══════════════════════════════════════════════════════════

class UpdateLLMConfigRequest(BaseModel):
    provider: str
    model: str


class UpdateGeminiLimitRequest(BaseModel):
    daily_limit: int


@app.get("/api/admin/llm-config")
async def get_llm_config(user: dict = Depends(require_admin)):
    """현재 LLM 설정 + Gemini 사용량 조회"""
    import runtime_config
    import gemini_usage

    return {
        "llm": runtime_config.get_all(),
        "gemini_usage": gemini_usage.get_today_status(),
        "gemini_history": gemini_usage.get_history(days=14),
    }


@app.post("/api/admin/llm-config")
async def update_llm_config(
    req: UpdateLLMConfigRequest,
    user: dict = Depends(require_admin),
):
    """LLM provider와 model을 변경 (즉시 반영, 파일 영속)"""
    import runtime_config

    try:
        runtime_config.set_provider_and_model(req.provider, req.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "ok": True,
        "llm": runtime_config.get_all(),
    }


@app.post("/api/admin/gemini-limit")
async def update_gemini_limit(
    req: UpdateGeminiLimitRequest,
    user: dict = Depends(require_admin),
):
    """Gemini 일일 한도 수정"""
    import gemini_usage

    if req.daily_limit < 0:
        raise HTTPException(status_code=400, detail="daily_limit must be >= 0")

    gemini_usage.set_daily_limit(req.daily_limit)
    return {"ok": True, "gemini_usage": gemini_usage.get_today_status()}


@app.post("/api/admin/gemini-reset")
async def reset_gemini_today(user: dict = Depends(require_admin)):
    """오늘 Gemini 사용량 카운터 초기화"""
    import gemini_usage

    gemini_usage.reset_today()
    return {"ok": True, "gemini_usage": gemini_usage.get_today_status()}


# ══════════════════════════════════════════════════════════
# 디버그/모니터링 API (관리자 전용)
# ══════════════════════════════════════════════════════════

@app.get("/api/debug/memory")
async def debug_memory(user: dict = Depends(require_admin)):
    """현재 프로세스 메모리 상세 정보 (관리자 전용)"""
    result = {"pid": os.getpid(), "timestamp": time.time()}

    # psutil 기반 시스템 정보
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        result["process"] = {
            "rss_mb": round(mem.rss / 1024 / 1024, 1),
            "vms_mb": round(mem.vms / 1024 / 1024, 1),
            "threads": proc.num_threads(),
            "cpu_percent": proc.cpu_percent(interval=0.5),
        }
        try:
            result["process"]["handles"] = proc.num_handles()
        except AttributeError:
            pass

        sys_mem = psutil.virtual_memory()
        result["system"] = {
            "total_mb": round(sys_mem.total / 1024 / 1024, 1),
            "available_mb": round(sys_mem.available / 1024 / 1024, 1),
            "used_percent": sys_mem.percent,
        }
    except ImportError:
        result["error_psutil"] = "psutil 미설치 (pip install psutil)"

    # tracemalloc 기반 Python 메모리 할당 Top 15
    try:
        import tracemalloc
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            result["tracemalloc"] = "방금 시작됨 — 다시 호출하면 데이터 확인 가능"
        else:
            snapshot = tracemalloc.take_snapshot()
            top = snapshot.statistics("lineno")[:15]
            result["tracemalloc_top15"] = [
                {
                    "file": str(s.traceback),
                    "size_mb": round(s.size / 1024 / 1024, 2),
                    "count": s.count,
                }
                for s in top
            ]
            current, peak = tracemalloc.get_traced_memory()
            result["tracemalloc_summary"] = {
                "current_mb": round(current / 1024 / 1024, 2),
                "peak_mb": round(peak / 1024 / 1024, 2),
            }
    except Exception as e:
        result["error_tracemalloc"] = str(e)

    # LLM Semaphore 상태
    try:
        from llm import _llm_semaphore, MAX_CONCURRENT_LLM
        if _llm_semaphore is not None:
            result["llm_semaphore"] = {
                "max": MAX_CONCURRENT_LLM,
                "available": _llm_semaphore._value,
                "waiting": MAX_CONCURRENT_LLM - _llm_semaphore._value,
            }
    except Exception:
        pass

    return result


@app.get("/api/debug/health")
async def debug_health():
    """서버 헬스체크 (인증 불필요 — 외부 모니터링용)"""
    result = {"status": "ok", "timestamp": time.time(), "pid": os.getpid()}
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        result["rss_mb"] = round(mem.rss / 1024 / 1024, 1)
        result["uptime_seconds"] = round(time.time() - proc.create_time())
    except ImportError:
        pass
    return result


if __name__ == "__main__":
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=debug)
