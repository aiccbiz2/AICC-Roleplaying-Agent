"""LLM 호출 래퍼 — 멀티 백엔드 (Gemini API / Claude CLI)"""
from __future__ import annotations

import asyncio
import logging
import os
import time

from config import GEMINI_API_KEY, OLLAMA_BASE_URL
import runtime_config
import gemini_usage


def _get_provider() -> str:
    """현재 LLM provider (runtime_config에서 매 호출마다 읽음)"""
    return runtime_config.get_provider()


def _get_model() -> str:
    """현재 LLM model (runtime_config에서 매 호출마다 읽음)"""
    return runtime_config.get_model()

logger = logging.getLogger("llm")

# ── 동시 LLM 호출 제한 (Ollama OOM 방지) ──
MAX_CONCURRENT_LLM = int(os.environ.get("MAX_CONCURRENT_LLM", "5"))
_llm_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """asyncio.Semaphore 지연 초기화 (이벤트 루프 바운드)"""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)
    return _llm_semaphore


# ══════════════════════════════════════════════════════════
# Gemini API 백엔드
# ══════════════════════════════════════════════════════════

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


async def _call_gemini_async(prompt: str, system_prompt: str = "", max_tokens: int | None = None) -> str:
    """Gemini API 네이티브 async 호출.

    Gemma 모델은 system_instruction과 response_mime_type=JSON을 지원하지 않으므로
    system_prompt를 user 메시지에 inline으로 합치고 JSON mode를 비활성화한다.
    """
    from google.genai import types

    model_name = _get_model()
    is_gemma = "gemma" in model_name.lower()

    client = _get_gemini_client()
    gen_config = None
    final_prompt = prompt

    config_kwargs = {}
    if max_tokens:
        config_kwargs["max_output_tokens"] = max_tokens

    if is_gemma:
        # Gemma: system_instruction 미지원 → user 메시지 앞에 합친다
        if system_prompt:
            final_prompt = f"{system_prompt}\n\n---\n\n{prompt}"
        if config_kwargs:
            gen_config = types.GenerateContentConfig(**config_kwargs)
    else:
        # Gemini: system_instruction + JSON mode 사용
        if system_prompt:
            needs_json = "JSON" in system_prompt or "json" in system_prompt
            config_kwargs["system_instruction"] = system_prompt
            if needs_json:
                config_kwargs["response_mime_type"] = "application/json"
        if config_kwargs:
            gen_config = types.GenerateContentConfig(**config_kwargs)

    logger.info("[Gemini 요청] prompt=%d chars, system=%d chars, model=%s, gemma=%s",
                len(final_prompt), len(system_prompt), model_name, is_gemma)
    start = time.time()

    success = True
    output = ""
    try:
        response = await client.aio.models.generate_content(
            model=model_name,
            config=gen_config,
            contents=final_prompt,
        )
        output = response.text.strip() if response.text else ""
    except Exception as e:
        success = False
        logger.error("[Gemini 에러] %s", e)
        raise
    finally:
        # 사용량 기록 (성공/실패 모두)
        gemini_usage.record(
            prompt_len=len(final_prompt),
            response_len=len(output),
            success=success,
        )

    elapsed = time.time() - start
    logger.info("[Gemini 응답] %d chars (%.1fs)", len(output), elapsed)
    return output


def _call_gemini(prompt: str, system_prompt: str = "") -> str:
    """Gemini API 동기 호출 (하위 호환용)."""
    return asyncio.run(_call_gemini_async(prompt, system_prompt))


async def _call_gemini_multiturn_async(
    system_prompt: str,
    chat_history: list[dict],
    final_user_prompt: str = "",
) -> str:
    """Gemini/Gemma API 네이티브 멀티턴 호출.

    chat_history는 [{"role": "user|assistant", "content": "..."}] 형식.
    Gemini contents는 role="user"/"model", parts=[{"text": "..."}] 형식이 필요.

    Gemini: system_instruction 파라미터 사용 + contents 배열
    Gemma: 첫 user 메시지에 system_prompt를 inline + contents 배열 (system_instruction 미지원)
    """
    from google.genai import types

    model_name = _get_model()
    is_gemma = "gemma" in model_name.lower()
    client = _get_gemini_client()

    # chat_history → Gemini contents 형식 변환
    contents = []
    for i, msg in enumerate(chat_history):
        role = "user" if msg["role"] == "user" else "model"
        text = msg["content"]
        # Gemma: 첫 user 메시지에 system_prompt 합치기
        if is_gemma and i == 0 and role == "user" and system_prompt:
            text = f"{system_prompt}\n\n---\n\n{text}"
        contents.append({"role": role, "parts": [{"text": text}]})

    # final_user_prompt가 있으면 마지막에 user 메시지로 추가
    if final_user_prompt:
        contents.append({"role": "user", "parts": [{"text": final_user_prompt}]})

    # Gemini는 system_instruction 사용, Gemma는 None
    gen_config = None
    if not is_gemma and system_prompt:
        gen_config = types.GenerateContentConfig(system_instruction=system_prompt)

    total_chars = sum(len(c["parts"][0]["text"]) for c in contents)
    logger.info(
        "[Gemini 멀티턴] turns=%d, total=%d chars, system=%d chars, model=%s, gemma=%s",
        len(contents), total_chars, len(system_prompt), model_name, is_gemma,
    )
    start = time.time()

    success = True
    output = ""
    try:
        response = await client.aio.models.generate_content(
            model=model_name,
            config=gen_config,
            contents=contents,
        )
        output = response.text.strip() if response.text else ""
    except Exception as e:
        success = False
        logger.error("[Gemini 멀티턴 에러] %s", e)
        raise
    finally:
        gemini_usage.record(
            prompt_len=total_chars + len(system_prompt),
            response_len=len(output),
            success=success,
        )

    elapsed = time.time() - start
    logger.info("[Gemini 멀티턴 응답] %d chars (%.1fs)", len(output), elapsed)
    return output


# ══════════════════════════════════════════════════════════
# Claude CLI 백엔드 (기존 subprocess 방식 보존)
# ══════════════════════════════════════════════════════════

def _build_cli_cmd(system_prompt: str = "") -> list[str]:
    cmd = [
        "claude",
        "-p",
        "--output-format", "text",
        "--model", _get_model(),
        "--max-turns", "1",
    ]
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])
    return cmd


def _build_cli_env() -> dict:
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    return env


async def _call_claude_cli_async(prompt: str, system_prompt: str = "") -> str:
    """Claude CLI 비동기 호출 — 스레드풀에서 동기 subprocess 실행."""
    return await asyncio.get_event_loop().run_in_executor(
        None, _call_claude_cli, prompt, system_prompt
    )


def _call_claude_cli(prompt: str, system_prompt: str = "") -> str:
    """Claude CLI 동기 호출."""
    import subprocess

    cmd = _build_cli_cmd(system_prompt)
    env = _build_cli_env()

    logger.info("[CLI 요청] prompt=%d chars, system=%d chars, model=%s",
                len(prompt), len(system_prompt), _get_model())
    start = time.time()

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        encoding="utf-8",
    )

    elapsed = time.time() - start

    if result.stderr:
        logger.warning("[CLI stderr] %s", result.stderr.strip())

    if result.returncode != 0:
        logger.error("[CLI 실패] returncode=%d, stderr=%s (%.1fs)",
                     result.returncode, result.stderr, elapsed)
        raise RuntimeError(f"Claude CLI 오류: {result.stderr}")

    output = result.stdout.strip()
    logger.info("[CLI 응답] %d chars (%.1fs)", len(output), elapsed)
    return output


# ══════════════════════════════════════════════════════════
# Ollama 백엔드 (로컬 LLM)
# ══════════════════════════════════════════════════════════

_ollama_async_client = None
_ollama_sync_client = None


def _get_ollama_async_client():
    """Ollama용 httpx AsyncClient 싱글톤"""
    global _ollama_async_client
    import httpx
    if _ollama_async_client is None or _ollama_async_client.is_closed:
        _ollama_async_client = httpx.AsyncClient(timeout=180)
    return _ollama_async_client


def _get_ollama_sync_client():
    """Ollama용 httpx Client 싱글톤"""
    global _ollama_sync_client
    import httpx
    if _ollama_sync_client is None or _ollama_sync_client.is_closed:
        _ollama_sync_client = httpx.Client(timeout=180)
    return _ollama_sync_client


async def _call_ollama_async(prompt: str, system_prompt: str = "", max_tokens: int | None = None) -> str:
    """Ollama API 네이티브 async 호출."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    return await _call_ollama_messages_async(messages, max_tokens=max_tokens)


async def _call_ollama_multiturn_async(
    system_prompt: str,
    chat_history: list[dict],
    final_user_prompt: str = "",
    max_tokens: int | None = None,
) -> str:
    """Ollama API 멀티턴 async 호출 — user/assistant 역할을 정확히 구분하여 전송."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    for msg in chat_history:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})

    if final_user_prompt:
        messages.append({"role": "user", "content": final_user_prompt})

    return await _call_ollama_messages_async(messages, max_tokens=max_tokens)


async def _call_ollama_messages_async(messages: list[dict], max_tokens: int | None = None) -> str:
    """Ollama API 공통 메시지 전송 (단일턴/멀티턴 공용)."""
    all_text = " ".join(m["content"] for m in messages)
    needs_json = "JSON" in all_text or "json" in all_text

    total_prompt_len = sum(len(m["content"]) for m in messages)
    model_name = _get_model()
    logger.info("[Ollama 요청] messages=%d개, total=%d chars, model=%s, json_mode=%s",
                len(messages), total_prompt_len, model_name, needs_json)
    start = time.time()

    if max_tokens:
        num_predict = max_tokens
    else:
        num_predict = 2048 if total_prompt_len > 2000 else 1024

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "num_ctx": 4096,
        },
    }
    if needs_json:
        payload["format"] = "json"

    client = _get_ollama_async_client()
    res = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)

    elapsed = time.time() - start
    output = res.json()["message"]["content"].strip()
    logger.info("[Ollama 응답] %d chars (%.1fs)", len(output), elapsed)
    return output


def _call_ollama(prompt: str, system_prompt: str = "") -> str:
    """Ollama API 동기 호출."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    return _call_ollama_messages_sync(messages)


def _call_ollama_multiturn(
    system_prompt: str,
    chat_history: list[dict],
    final_user_prompt: str = "",
    max_tokens: int | None = None,
) -> str:
    """Ollama API 멀티턴 동기 호출 — user/assistant 역할을 정확히 구분하여 전송."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    for msg in chat_history:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})

    if final_user_prompt:
        messages.append({"role": "user", "content": final_user_prompt})

    return _call_ollama_messages_sync(messages, max_tokens=max_tokens)


def _call_ollama_messages_sync(messages: list[dict], max_tokens: int | None = None) -> str:
    """Ollama API 공통 메시지 전송 동기 버전."""
    all_text = " ".join(m["content"] for m in messages)
    needs_json = "JSON" in all_text or "json" in all_text

    total_prompt_len = sum(len(m["content"]) for m in messages)
    model_name = _get_model()
    logger.info("[Ollama 요청] messages=%d개, total=%d chars, model=%s, json_mode=%s",
                len(messages), total_prompt_len, model_name, needs_json)
    start = time.time()

    if max_tokens:
        num_predict = max_tokens
    else:
        num_predict = 2048 if total_prompt_len > 2000 else 1024

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "num_ctx": 4096,
        },
    }
    if needs_json:
        payload["format"] = "json"

    client = _get_ollama_sync_client()
    res = client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)

    elapsed = time.time() - start
    output = res.json()["message"]["content"].strip()
    logger.info("[Ollama 응답] %d chars (%.1fs)", len(output), elapsed)
    return output


# ══════════════════════════════════════════════════════════
# 공통 인터페이스 (프로바이더 분기)
# ══════════════════════════════════════════════════════════

async def call_claude_async(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int | None = None,
) -> str:
    """비동기 LLM 호출 — Semaphore로 동시 호출 제한, 프로바이더 자동 분기.

    max_tokens: 응답 생성 토큰 상한 (None이면 기본값 사용).
    Ollama/Gemini/Gemma 모두 지원.
    """
    sem = _get_semaphore()
    provider = _get_provider()
    async with sem:
        if provider == "gemini":
            return await _call_gemini_async(prompt, system_prompt, max_tokens=max_tokens)
        elif provider == "ollama":
            return await _call_ollama_async(prompt, system_prompt, max_tokens=max_tokens)
        else:
            return await _call_claude_cli_async(prompt, system_prompt)


async def call_multiturn_async(
    system_prompt: str,
    chat_history: list[dict],
    final_user_prompt: str = "",
    max_tokens: int | None = None,
) -> str:
    """비동기 멀티턴 LLM 호출 — 모든 프로바이더가 네이티브 멀티턴을 사용.

    - Gemini/Gemma: contents 배열로 네이티브 호출 (Gemma는 system_prompt를 첫 user에 inline)
    - Ollama: messages 배열로 네이티브 호출
    - Claude CLI: 평탄화 폴백 (CLI는 멀티턴 미지원)
    """
    sem = _get_semaphore()
    provider = _get_provider()
    async with sem:
        if provider == "ollama":
            return await _call_ollama_multiturn_async(
                system_prompt, chat_history, final_user_prompt,
                max_tokens=max_tokens,
            )
        elif provider == "gemini":
            # Gemini/Gemma 네이티브 멀티턴 (max_tokens는 미적용 — Gemini SDK는 자동 관리)
            return await _call_gemini_multiturn_async(
                system_prompt, chat_history, final_user_prompt,
            )
        else:
            # Claude CLI는 멀티턴 미지원 → 평탄화 폴백
            conversation = ""
            for msg in chat_history:
                role = "사업담당" if msg["role"] == "user" else "고객(나)"
                conversation += f"{role}: {msg['content']}\n\n"
            prompt = f"지금까지의 대화:\n{conversation}\n고객(나)으로서 다음 응답을 하세요."
            if final_user_prompt:
                prompt += f"\n{final_user_prompt}"
            return await _call_claude_cli_async(prompt, system_prompt)


def call_claude(
    prompt: str,
    system_prompt: str = "",
) -> str:
    """동기 LLM 호출 — 설정된 프로바이더로 자동 분기."""
    provider = _get_provider()
    if provider == "gemini":
        return _call_gemini(prompt, system_prompt)
    elif provider == "ollama":
        return _call_ollama(prompt, system_prompt)
    else:
        return _call_claude_cli(prompt, system_prompt)


def call_multiturn(
    system_prompt: str,
    chat_history: list[dict],
    final_user_prompt: str = "",
    max_tokens: int | None = None,
) -> str:
    """동기 멀티턴 LLM 호출."""
    provider = _get_provider()
    if provider == "ollama":
        return _call_ollama_multiturn(
            system_prompt, chat_history, final_user_prompt,
            max_tokens=max_tokens,
        )
    elif provider == "gemini":
        # Gemini/Gemma 네이티브 멀티턴 (sync 래퍼)
        return asyncio.run(_call_gemini_multiturn_async(
            system_prompt, chat_history, final_user_prompt,
        ))
    else:
        # Claude CLI는 평탄화 폴백
        conversation = ""
        for msg in chat_history:
            role = "사업담당" if msg["role"] == "user" else "고객(나)"
            conversation += f"{role}: {msg['content']}\n\n"
        prompt = f"지금까지의 대화:\n{conversation}\n고객(나)으로서 다음 응답을 하세요."
        if final_user_prompt:
            prompt += f"\n{final_user_prompt}"
        return call_claude(prompt, system_prompt)
