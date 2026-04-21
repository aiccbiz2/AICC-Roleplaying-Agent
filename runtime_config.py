"""런타임 LLM 설정 관리 (파일 영속, 핫 리로드)

서버 재시작 없이 관리자 UI에서 LLM provider/model을 변경할 수 있다.
설정은 data/runtime_config.json에 저장되며, 매 LLM 호출 시 읽는다.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import config

logger = logging.getLogger("runtime_config")

CONFIG_PATH = config.PROJECT_DIR / "data" / "runtime_config.json"

VALID_PROVIDERS = {"gemini", "claude-cli", "ollama"}

_lock = threading.Lock()
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    if CONFIG_PATH.exists():
        try:
            _cache = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("runtime_config.json 로드 실패: %s — 기본값 사용", e)
            _cache = {}
    else:
        _cache = {}

    # config.py의 환경변수/기본값을 폴백으로 사용
    _cache.setdefault("provider", config.LLM_PROVIDER)
    _cache.setdefault("model", config.LLM_MODEL)
    return _cache


def _save() -> None:
    if _cache is None:
        return
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_provider() -> str:
    with _lock:
        return _load()["provider"]


def get_model() -> str:
    with _lock:
        return _load()["model"]


def get_all() -> dict:
    with _lock:
        cfg = _load()
        return {
            "provider": cfg["provider"],
            "model": cfg["model"],
        }


def set_provider_and_model(provider: str, model: str) -> None:
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"Invalid provider: {provider}. Must be one of {VALID_PROVIDERS}")
    with _lock:
        cfg = _load()
        cfg["provider"] = provider
        cfg["model"] = model
        _save()
    logger.info("LLM 설정 변경: provider=%s, model=%s", provider, model)
