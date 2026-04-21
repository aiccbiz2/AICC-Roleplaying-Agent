"""pytest 공유 설정 — 서버 자동 기동/재사용, 실패 아티팩트 수집, 콘솔 에러 캡처

핵심 동작:
1. 세션 시작 시 /api/debug/health 로 서버 생존 확인
   - 살아있으면 → 그 서버 재사용 (종료 시 건드리지 않음)
   - 죽어있으면 → python main.py 를 띄우고 폴링, atexit 으로 정리
   - 8000 포트는 점유됐는데 health 가 실패면 → 명확한 에러로 거부 (포트 충돌 보호)
2. page 픽스처를 사용하는 모든 테스트에 콘솔 에러/페이지 에러 리스너 자동 부착
3. 테스트 실패 시 (test name, 첫 실패 메시지, 콘솔 에러, 스크린샷 경로) 를 모아
   세션 종료 시 test-results/issues.md 자동 생성
"""
from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Windows 콘솔 cp949 → UTF-8 강제 (한글 print 깨짐 방지)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import httpx
import pytest

ROOT = Path(__file__).parent
HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"
HEALTH_URL = f"{BASE_URL}/api/debug/health"
RESULTS_DIR = ROOT / "test-results"

# 우리가 띄운 서버 핸들 (None 이면 우리는 안 띄운 것 = 재사용 모드)
_owned_server: Optional[subprocess.Popen] = None

# 실패 아티팩트 누적: dict[nodeid] -> entry  (중복 방지)
_failures: dict[str, dict] = {}
# page 별 콘솔 에러 누적 (테스트 종료 시 비움)
_page_console_errors: dict[int, list[str]] = {}


# ── 서버 라이프사이클 ─────────────────────────────────────────

def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


def _health_ok(timeout: float = 2.0) -> bool:
    try:
        r = httpx.get(HEALTH_URL, timeout=timeout)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


def _wait_for_health(max_seconds: int = 60) -> bool:
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        if _health_ok(timeout=2):
            return True
        time.sleep(1)
    return False


def _start_server() -> subprocess.Popen:
    """python main.py 를 백그라운드 프로세스로 기동."""
    log_path = RESULTS_DIR / "server.log"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log_fp = open(log_path, "w", encoding="utf-8")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    creationflags = 0
    if sys.platform == "win32":
        # Ctrl+C 가 부모로부터 전파되지 않도록 새 프로세스 그룹
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(ROOT),
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=creationflags,
    )
    return proc


def _stop_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            proc.send_signal(subprocess.signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


@pytest.fixture(scope="session", autouse=True)
def ensure_server():
    """세션 동안 BASE_URL 서버가 살아있도록 보장.

    - 이미 떠 있으면 reuse, 아니면 우리가 띄움.
    - 우리가 띄운 경우에만 종료 시 정리.
    """
    global _owned_server

    if _health_ok():
        print(f"\n[conftest] 서버 재사용: {BASE_URL} (이미 기동중)")
        yield BASE_URL
        return

    # health 실패인데 포트는 점유됐으면 다른 프로세스 충돌
    if _port_in_use(HOST, PORT):
        pytest.exit(
            f"[conftest] 포트 {PORT} 가 점유되어 있지만 {HEALTH_URL} 응답이 없습니다.\n"
            f"           다른 프로세스가 8000 을 쓰고 있는지 확인해주세요.",
            returncode=2,
        )

    print(f"\n[conftest] 서버 기동중... ({BASE_URL})")
    _owned_server = _start_server()
    atexit.register(lambda: _owned_server and _stop_server(_owned_server))

    if not _wait_for_health(max_seconds=60):
        _stop_server(_owned_server)
        log_path = RESULTS_DIR / "server.log"
        pytest.exit(
            f"[conftest] 서버가 60초 내에 health 응답을 주지 않았습니다.\n"
            f"           로그: {log_path}",
            returncode=3,
        )

    print(f"[conftest] 서버 준비 완료 ({BASE_URL})")
    yield BASE_URL

    # 우리가 띄운 경우에만 정리
    if _owned_server is not None:
        print(f"\n[conftest] 서버 종료중...")
        _stop_server(_owned_server)
        _owned_server = None


# ── pytest-playwright 통합 ────────────────────────────────────

@pytest.fixture(scope="session")
def base_url() -> str:
    """pytest-base-url 호환 — 모든 페이지 테스트는 page.goto('/login') 식으로 사용."""
    return BASE_URL


@pytest.fixture
def browser_context_args(browser_context_args):
    """기본 컨텍스트 인자 오버라이드 — 한국 로케일/뷰포트/타임존."""
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        "locale": "ko-KR",
        "timezone_id": "Asia/Seoul",
        "ignore_https_errors": True,
    }


@pytest.fixture(autouse=True)
def _capture_page_console(request):
    """page 픽스처를 쓰는 테스트라면 console error / pageerror 를 수집."""
    if "page" not in request.fixturenames:
        yield
        return

    page = request.getfixturevalue("page")
    errors: list[str] = []
    _page_console_errors[id(page)] = errors

    def _on_console(msg):
        if msg.type == "error":
            errors.append(f"[console.error] {msg.text}")

    def _on_pageerror(exc):
        errors.append(f"[pageerror] {exc}")

    page.on("console", _on_console)
    page.on("pageerror", _on_pageerror)

    yield

    _page_console_errors.pop(id(page), None)


# ── 실패 후크 — 아티팩트 + issues.md 누적 ────────────────────

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    # call/setup/teardown 모두에서 실패·에러 캡처
    if not report.failed:
        return
    if report.when not in ("call", "setup"):
        return

    # 이미 동일 nodeid 가 기록됐으면 longrepr 만 갱신 (중복 방지)
    existing = _failures.get(item.nodeid)
    longrepr = str(report.longrepr).splitlines()[-1] if report.longrepr else ""
    phase = "ERROR" if report.when == "setup" else "FAILED"

    if existing is None:
        entry = {
            "nodeid": item.nodeid,
            "name": item.name,
            "phase": phase,
            "longrepr": longrepr,
            "console_errors": [],
            "screenshot": "",
        }
        _failures[item.nodeid] = entry
    else:
        entry = existing
        # 더 자세한 에러 메시지로 갱신
        if longrepr and not entry["longrepr"]:
            entry["longrepr"] = longrepr

    # 콘솔 에러 + 스크린샷 (page 픽스처 사용한 경우만)
    page = item.funcargs.get("page") if hasattr(item, "funcargs") else None
    if page is not None and not entry["screenshot"]:
        entry["console_errors"] = list(_page_console_errors.get(id(page), []))
        try:
            shot_dir = RESULTS_DIR / "manual-shots"
            shot_dir.mkdir(parents=True, exist_ok=True)
            safe_name = item.nodeid.replace("/", "_").replace("::", "__")[:120]
            shot_path = shot_dir / f"{safe_name}.png"
            page.screenshot(path=str(shot_path), full_page=True)
            entry["screenshot"] = str(shot_path.relative_to(ROOT))
        except Exception:
            pass


def pytest_sessionfinish(session, exitstatus):
    """세션 끝나고 issues.md 작성."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    md = RESULTS_DIR / "issues.md"
    total = session.testscollected
    failures = list(_failures.values())
    failed_count = sum(1 for f in failures if f["phase"] == "FAILED")
    error_count = sum(1 for f in failures if f["phase"] == "ERROR")

    lines: list[str] = []
    lines.append("# 자동 테스트 결과 리포트\n")
    lines.append(f"- 수집 테스트: **{total}**")
    lines.append(f"- 실패: **{failed_count}**")
    lines.append(f"- 에러 (setup/teardown): **{error_count}**")
    lines.append(f"- 종료 코드: `{exitstatus}`")
    lines.append(f"- HTML 리포트: `test-results/report.html`")
    lines.append(f"- 서버 로그: `test-results/server.log`")
    lines.append("")

    if not failures:
        lines.append("## 문제 없음\n")
        lines.append("모든 테스트가 통과했습니다.")
    else:
        lines.append("## 실패/에러 목록\n")
        for i, f in enumerate(failures, 1):
            lines.append(f"### {i}. [{f['phase']}] `{f['nodeid']}`\n")
            if f["longrepr"]:
                lines.append(f"- **요약**: {f['longrepr']}")
            if f["console_errors"]:
                lines.append("- **브라우저 콘솔 에러**:")
                for e in f["console_errors"]:
                    lines.append(f"  - `{e}`")
            if f["screenshot"]:
                lines.append(f"- **스크린샷**: `{f['screenshot']}`")
            # pytest-playwright 가 만든 trace.zip 안내
            safe = f["nodeid"].replace("::", "-").replace("/", "-")
            lines.append(f"- **trace 보기**: `playwright show-trace test-results/{safe}/trace.zip` (있는 경우)")
            lines.append("")

    md.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[conftest] 리포트 저장: {md} (실패 {failed_count}, 에러 {error_count})")
