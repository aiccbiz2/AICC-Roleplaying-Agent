"""Gemini API 일일 사용량 추적 (파일 영속)

Gemini 무료 티어는 하루에 요청 수 제한이 있다.
이 모듈은 매 Gemini API 호출을 기록하고, 일자별 카운트를 `data/gemini_usage.json`에 저장한다.
서버가 재기동되어도 이력이 유지된다.

구조:
{
  "daily_limit": 250,
  "history": {
    "2026-04-07": {"requests": 42, "prompt_chars": 12345, "response_chars": 5678},
    "2026-04-06": {"requests": 120, "prompt_chars": ...}
  }
}

사용:
    import gemini_usage
    gemini_usage.record(prompt_len=500, response_len=200)
    status = gemini_usage.get_today_status()
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger("gemini_usage")

USAGE_PATH = config.PROJECT_DIR / "data" / "gemini_usage.json"
# Gemma 3 무료 한도 14,400을 기본값으로 설정. gemini-2.5-flash는 20으로, admin UI에서 조정 가능
DEFAULT_DAILY_LIMIT = 14400

_lock = threading.Lock()
_cache: dict | None = None


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    if USAGE_PATH.exists():
        try:
            _cache = json.loads(USAGE_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("gemini_usage.json 로드 실패: %s — 새로 시작", e)
            _cache = {"daily_limit": DEFAULT_DAILY_LIMIT, "history": {}}
    else:
        _cache = {"daily_limit": DEFAULT_DAILY_LIMIT, "history": {}}

    if "daily_limit" not in _cache:
        _cache["daily_limit"] = DEFAULT_DAILY_LIMIT
    if "history" not in _cache:
        _cache["history"] = {}
    return _cache


def _save() -> None:
    if _cache is None:
        return
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    USAGE_PATH.write_text(
        json.dumps(_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record(prompt_len: int = 0, response_len: int = 0, success: bool = True) -> None:
    """Gemini API 호출 1회 기록."""
    with _lock:
        cfg = _load()
        today = _today()
        if today not in cfg["history"]:
            cfg["history"][today] = {
                "requests": 0,
                "errors": 0,
                "prompt_chars": 0,
                "response_chars": 0,
            }
        entry = cfg["history"][today]
        entry["requests"] = entry.get("requests", 0) + 1
        entry["prompt_chars"] = entry.get("prompt_chars", 0) + prompt_len
        entry["response_chars"] = entry.get("response_chars", 0) + response_len
        if not success:
            entry["errors"] = entry.get("errors", 0) + 1
        _save()


def get_today_status() -> dict:
    """오늘 사용량 + 한도 + 남은 요청 수 반환."""
    with _lock:
        cfg = _load()
        today = _today()
        entry = cfg["history"].get(today, {})
        requests_today = entry.get("requests", 0)
        limit = cfg.get("daily_limit", DEFAULT_DAILY_LIMIT)
        remaining = max(0, limit - requests_today)
        return {
            "date": today,
            "requests_today": requests_today,
            "errors_today": entry.get("errors", 0),
            "prompt_chars_today": entry.get("prompt_chars", 0),
            "response_chars_today": entry.get("response_chars", 0),
            "daily_limit": limit,
            "remaining": remaining,
            "percentage": round(requests_today / limit * 100, 1) if limit > 0 else 0,
        }


def get_history(days: int = 14) -> list[dict]:
    """최근 N일 사용 이력 (최신순)"""
    with _lock:
        cfg = _load()
        history = cfg.get("history", {})
        # 날짜순 내림차순 정렬
        sorted_dates = sorted(history.keys(), reverse=True)[:days]
        return [
            {
                "date": d,
                "requests": history[d].get("requests", 0),
                "errors": history[d].get("errors", 0),
                "prompt_chars": history[d].get("prompt_chars", 0),
                "response_chars": history[d].get("response_chars", 0),
            }
            for d in sorted_dates
        ]


def set_daily_limit(limit: int) -> None:
    """일일 한도 수동 설정 (admin UI용)"""
    with _lock:
        cfg = _load()
        cfg["daily_limit"] = max(0, int(limit))
        _save()


def reset_today() -> None:
    """오늘 카운터 초기화 (테스트/긴급용)"""
    with _lock:
        cfg = _load()
        today = _today()
        if today in cfg["history"]:
            cfg["history"][today] = {
                "requests": 0,
                "errors": 0,
                "prompt_chars": 0,
                "response_chars": 0,
            }
            _save()
