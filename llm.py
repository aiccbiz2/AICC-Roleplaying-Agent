"""Claude CLI 래퍼 — Pro/Max 구독 인증 활용 (API Key 불필요)"""
from __future__ import annotations

import os
import subprocess

from config import LLM_MODEL


def call_claude(
    prompt: str,
    system_prompt: str = "",
) -> str:
    """Claude CLI를 호출하여 응답을 받아옴.

    ANTHROPIC_API_KEY가 설정되어 있으면 unset하여
    구독 인증(OAuth)을 사용하도록 함.
    """
    cmd = [
        "claude",
        "-p",
        "--output-format", "text",
        "--model", LLM_MODEL,
        "--tools", "",
    ]

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    # ANTHROPIC_API_KEY가 있으면 CLI가 API 크레딧 모드로 전환됨
    # → unset하여 Pro/Max 구독 인증 사용
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI 오류: {result.stderr}")

    return result.stdout.strip()
