"""IPCC/AICC 도메인 퀴즈 모드"""
from __future__ import annotations

import json
import logging
import random
import time

from config import PROJECT_DIR
from rag import retrieve, format_context
from llm import call_claude_async

logger = logging.getLogger("quiz")

POOL_PATH = PROJECT_DIR / "quiz_pool.json"

# ── 퀴즈 풀 캐시 (파일 mtime 기반 자동 갱신) ──
_quiz_pool_cache: list[dict] | None = None
_quiz_pool_mtime: float = 0.0

QUIZ_CATEGORIES = [
    "IPCC 아키텍처 (PBX, CTI, IVR, 녹취)",
    "음성기술 (STT, TTS, 화자분리)",
    "AI/LLM (RAG, 콜봇, 챗봇)",
    "상담운영 (ACD, WFM, QA)",
    "도입/구축 (PoC, 레퍼런스, 연동)",
    "비용/라이센스",
    "AICC 기능 (상담 어드바이저, 보이스봇)",
    "사업 전략 (영업 대응)",
]

QUIZ_PROMPT = """당신은 IPCC/AICC 도메인 교육 퀴즈 출제자입니다.

아래 참고 자료를 기반으로 **{category}** 카테고리에서 4지선다형 퀴즈 1문제를 생성하세요.

규칙:
1. 실무에서 실제로 알아야 하는 핵심 지식을 묻는 문제를 출제하세요.
2. 난이도: {difficulty}
3. 고객 미팅에서 실제 나올 수 있는 상황 기반 문제를 선호하세요.
4. 정답 해설에서 관련 배경 지식도 함께 설명하세요.

참고 자료:
{context}

반드시 아래 JSON 형식으로만 답변하세요 (다른 텍스트 없이):
{{
  "question": "문제 텍스트",
  "options": ["A. 선택지1", "B. 선택지2", "C. 선택지3", "D. 선택지4"],
  "answer": "A",
  "explanation": "정답 해설 (2-3문장)"
}}"""


def _get_quiz_pool() -> list[dict]:
    """퀴즈 풀을 캐시에서 로딩 (파일 변경 시에만 다시 읽음)"""
    global _quiz_pool_cache, _quiz_pool_mtime

    if not POOL_PATH.exists():
        return []

    current_mtime = POOL_PATH.stat().st_mtime
    if _quiz_pool_cache is None or current_mtime != _quiz_pool_mtime:
        logger.info("퀴즈 풀 로딩: %s", POOL_PATH)
        _quiz_pool_cache = json.loads(POOL_PATH.read_text(encoding="utf-8"))
        _quiz_pool_mtime = current_mtime

    return _quiz_pool_cache or []


def load_quiz_from_pool(
    category: str | None = None,
    difficulty: str = "중급",
) -> dict | None:
    """사전 생성된 퀴즈 풀에서 즉시 로딩 (캐시 사용)"""
    pool = _get_quiz_pool()
    if not pool:
        return None

    # 필터링
    filtered = pool
    if category:
        filtered = [q for q in filtered if q.get("category") == category]
    if difficulty:
        with_diff = [q for q in filtered if q.get("difficulty") == difficulty]
        if with_diff:
            filtered = with_diff

    if not filtered:
        return None

    return random.choice(filtered)


def load_quiz_set_from_pool(
    category: str | None = None,
    difficulty: str = "중급",
    count: int = 10,
) -> list[dict]:
    """퀴즈 풀에서 count개 세트를 중복 없이 로딩 (캐시 사용)"""
    pool = _get_quiz_pool()
    if not pool:
        return []

    filtered = pool
    if category:
        filtered = [q for q in filtered if q.get("category") == category]
    if difficulty:
        with_diff = [q for q in filtered if q.get("difficulty") == difficulty]
        if with_diff:
            filtered = with_diff

    if not filtered:
        return []

    # 중복 없이 count개 선택 (부족하면 있는 만큼)
    return random.sample(filtered, min(count, len(filtered)))


async def generate_quiz(
    category: str | None = None,
    difficulty: str = "중급",
) -> dict:
    """퀴즈 1문제 생성"""
    if category is None:
        category = random.choice(QUIZ_CATEGORIES)

    docs = retrieve(category, top_k=4)
    context = format_context(docs)

    prompt = QUIZ_PROMPT.format(
        category=category,
        difficulty=difficulty,
        context=context,
    )

    text = await call_claude_async(prompt, max_tokens=1024)

    # Gemini 등이 ```json ... ``` 으로 감싸는 경우 제거
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline > 0:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        quiz = json.loads(text)
        quiz["category"] = category
        quiz["difficulty"] = difficulty
        return quiz
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            quiz = json.loads(text[start:end])
            quiz["category"] = category
            quiz["difficulty"] = difficulty
            return quiz
        raise ValueError(f"퀴즈 생성 실패: {text}")
