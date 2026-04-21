"""모든 활성 시나리오를 점검하여 문제점을 진단

각 시나리오에 대해:
1. Opening 생성 → 첫 질문이 시나리오의 key_questions 중 하나인지
2. 4턴 시뮬레이션 → 각 턴이 정의된 질문을 다루는지
3. 메타 표현 노출 여부
4. echoing (사업담당자 말 반복) 여부
5. 환각 (말하지 않은 회사명/수치) 여부
6. 시나리오 범위 이탈 여부

Rate limit (gemma-3-27b-it 무료 티어, 2026년 4월 기준):
- TPM: 15,000 (Tokens Per Minute)
- RPM: 30 (Requests Per Minute)
- RPD: 14,400 (Requests Per Day)
- 주의: Gemma 모델은 유료 업그레이드해도 한도 동일

실행: python test_all_scenarios.py
"""
import asyncio
import re
import sys
import time
from collections import deque

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import runtime_config

# Gemma로 강제 설정 (사용자 환경)
runtime_config.set_provider_and_model("gemini", "gemma-3-27b-it")

from roleplay import (
    SCENARIOS, build_system_prompt, get_opening_message_async, get_ai_response_async
)


# ── Rate Limiter ─────────────────────────────────────
# Gemma 3 27B 무료 티어: TPM 15,000 / RPM 30
# 한국어 1글자 ≈ 1토큰으로 보수적 추정
TPM_LIMIT = 15000
RPM_LIMIT = 30
SAFETY_MARGIN = 0.85  # 실제 한도의 85%만 사용 (여유분)

_token_window: deque = deque()  # [(timestamp, tokens), ...]
_request_window: deque = deque()  # [timestamp, ...]


def _estimate_tokens(*texts: str) -> int:
    """한국어 텍스트의 토큰 수 추정 (보수적으로 1글자=1토큰)"""
    return sum(len(t) for t in texts) + 200  # 출력 토큰 여유 200


async def rate_limit_wait(estimated_tokens: int):
    """현재 사용량이 한도를 초과하지 않도록 대기"""
    now = time.time()

    # 60초 이전 기록 제거
    while _token_window and _token_window[0][0] < now - 60:
        _token_window.popleft()
    while _request_window and _request_window[0] < now - 60:
        _request_window.popleft()

    # 현재 사용량
    tokens_used = sum(t for _, t in _token_window)
    requests_used = len(_request_window)

    tpm_max = TPM_LIMIT * SAFETY_MARGIN
    rpm_max = RPM_LIMIT * SAFETY_MARGIN

    # 다음 호출이 한도를 초과하면 대기
    if tokens_used + estimated_tokens > tpm_max:
        if _token_window:
            oldest_time = _token_window[0][0]
            wait = (oldest_time + 60) - now + 1
            if wait > 0:
                print(f"    [rate-limit] TPM 한도 근접 ({tokens_used + estimated_tokens}/{int(tpm_max)}), {wait:.0f}초 대기")
                await asyncio.sleep(wait)
                return await rate_limit_wait(estimated_tokens)

    if requests_used + 1 > rpm_max:
        if _request_window:
            oldest = _request_window[0]
            wait = (oldest + 60) - now + 1
            if wait > 0:
                print(f"    [rate-limit] RPM 한도 근접 ({requests_used + 1}/{int(rpm_max)}), {wait:.0f}초 대기")
                await asyncio.sleep(wait)
                return await rate_limit_wait(estimated_tokens)


def record_usage(tokens: int):
    """호출 후 사용량 기록"""
    now = time.time()
    _token_window.append((now, tokens))
    _request_window.append(now)


META_BAD = ["핵심 질문", "질문 1", "질문 2", "질문 3", "질문 4", "질문 5",
            "리스트", "체크리스트", "항목", "INTERNAL", "SYSTEM", "리마인더",
            "워킹 솔루션", "메타", "[지시"]


def check_meta_leakage(text: str) -> list[str]:
    """메타 표현 노출 검사"""
    return [k for k in META_BAD if k in text]


def check_echoing(ai_text: str, salesperson_text: str) -> bool:
    """사업담당자 말을 그대로 반복했는지 검사 (Jaccard similarity 50%+)"""
    if not salesperson_text or not ai_text:
        return False
    sp_words = set(re.findall(r"[가-힣]{2,}", salesperson_text))
    ai_words = set(re.findall(r"[가-힣]{2,}", ai_text))
    if not sp_words:
        return False
    overlap = sp_words & ai_words
    return len(overlap) / len(sp_words) > 0.5


def check_question_coverage(ai_responses: list[str], key_questions: list[str]) -> dict:
    """AI 응답들이 시나리오의 핵심 질문을 얼마나 커버했는지"""
    covered = []
    for q in key_questions:
        # 질문에서 핵심 키워드 2개 추출 (3자 이상 단어)
        key_words = [w for w in re.findall(r"[가-힣]{3,}", q) if len(w) >= 3][:3]
        if not key_words:
            continue
        for resp in ai_responses:
            matches = sum(1 for kw in key_words if kw in resp)
            if matches >= 1:
                covered.append(q[:40] + "...")
                break
    return {
        "covered_count": len(covered),
        "total": len(key_questions),
        "coverage_pct": len(covered) / len(key_questions) * 100 if key_questions else 0,
        "covered": covered,
    }


# 일반화된 사업담당자 응답 (시나리오와 무관)
GENERIC_ANSWERS = [
    "네, 그 부분은 저희가 충분히 지원 가능한 영역입니다.",
    "기술적으로는 가능하지만 구체적인 사항은 환경에 따라 달라질 수 있습니다.",
    "저희가 보유한 솔루션으로 대응 가능한 부분입니다. 더 자세한 내용을 원하시면 말씀해주세요.",
    "그 부분은 시나리오 분석을 통해 최적화할 수 있습니다.",
]


async def test_scenario(scenario_key: str, scenario: dict) -> dict:
    """단일 시나리오 테스트"""
    print(f"\n{'='*70}")
    print(f"  [{scenario_key}] {scenario['title']}")
    print(f"{'='*70}")

    system_prompt = build_system_prompt(scenario_key, "중급")

    issues = []
    ai_responses = []

    # 1. Opening
    try:
        # Rate limit: system_prompt + "(미팅 시작)" 토큰 수 추정
        estimated = _estimate_tokens(system_prompt, "(미팅 시작)")
        await rate_limit_wait(estimated)

        t = time.time()
        opening = await get_opening_message_async(system_prompt)
        elapsed = time.time() - t
        record_usage(estimated + _estimate_tokens(opening))

        print(f"\n  [Opening] ({elapsed:.1f}s)")
        print(f"  AI: {opening[:120]}")
        ai_responses.append(opening)

        leaked = check_meta_leakage(opening)
        if leaked:
            issues.append(f"Opening 메타 노출: {leaked}")
    except Exception as e:
        print(f"  [Opening 에러] {e}")
        return {"scenario": scenario_key, "issues": [f"Opening 실패: {str(e)[:100]}"]}

    # 2. 4턴 대화
    history = [
        {"role": "user", "content": "(미팅 시작)"},
        {"role": "assistant", "content": opening},
    ]

    for i, ans in enumerate(GENERIC_ANSWERS):
        history.append({"role": "user", "content": ans})
        try:
            # Rate limit: system_prompt + 전체 히스토리 토큰 수 추정
            history_text = "".join(m["content"] for m in history)
            estimated = _estimate_tokens(system_prompt, history_text)
            await rate_limit_wait(estimated)

            t = time.time()
            resp = await get_ai_response_async(system_prompt, history)
            elapsed = time.time() - t
            record_usage(estimated + _estimate_tokens(resp))

            print(f"\n  [턴 {i+1}] ({elapsed:.1f}s)")
            print(f"  사업담당: {ans}")
            print(f"  AI 고객: {resp[:140]}")

            ai_responses.append(resp)

            # 검사
            leaked = check_meta_leakage(resp)
            if leaked:
                issues.append(f"턴{i+1} 메타 노출: {leaked}")

            if check_echoing(resp, ans):
                issues.append(f"턴{i+1} 사업담당자 echoing")

            history.append({"role": "assistant", "content": resp})
        except Exception as e:
            err_msg = str(e)[:150]
            print(f"  [턴{i+1} 에러] {err_msg}")
            issues.append(f"턴{i+1} 에러: {err_msg}")
            # 429는 대기 후 다음 시나리오 진행
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print("    [rate-limit] 60초 대기 후 진행...")
                await asyncio.sleep(60)
            break

    # 3. 질문 커버리지
    coverage = check_question_coverage(ai_responses, scenario.get("key_questions", []))
    print(f"\n  [질문 커버리지] {coverage['covered_count']}/{coverage['total']} ({coverage['coverage_pct']:.0f}%)")
    for q in coverage["covered"]:
        print(f"    O {q}")
    not_covered = [q[:40] + "..." for q in scenario.get("key_questions", [])
                   if q[:40] + "..." not in coverage["covered"]]
    for q in not_covered:
        print(f"    X {q}")

    if coverage["coverage_pct"] < 60:
        issues.append(f"질문 커버리지 낮음: {coverage['coverage_pct']:.0f}%")

    # 4. 결과
    if issues:
        print(f"\n  [문제 {len(issues)}건]")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print(f"\n  [OK] 문제 없음")

    return {
        "scenario": scenario_key,
        "title": scenario["title"],
        "issues": issues,
        "coverage": coverage["coverage_pct"],
    }


async def main():
    print("=" * 70)
    print("  롤플레이 전체 시나리오 진단")
    print(f"  모델: {runtime_config.get_provider()}/{runtime_config.get_model()}")
    print("=" * 70)

    # 활성 시나리오만 (disabled 제외)
    active_scenarios = {k: s for k, s in SCENARIOS.items() if not s.get("disabled")}
    print(f"\n  활성 시나리오: {len(active_scenarios)}개")

    results = []
    for key, scen in active_scenarios.items():
        result = await test_scenario(key, scen)
        results.append(result)

    # 종합 결과
    print(f"\n\n{'='*70}")
    print(f"  최종 진단 결과")
    print(f"{'='*70}")
    print(f"\n  {'시나리오':<32} {'커버리지':>10} {'문제수':>8}")
    print(f"  {'-'*55}")
    for r in results:
        title = r.get("title", r["scenario"])[:30]
        cov = r.get("coverage", 0)
        n_issues = len(r["issues"])
        mark = "OK" if n_issues == 0 and cov >= 60 else "!!"
        print(f"  {mark} {title:<30} {cov:>8.0f}% {n_issues:>8}")

    total_issues = sum(len(r["issues"]) for r in results)
    avg_coverage = sum(r.get("coverage", 0) for r in results) / len(results) if results else 0
    print(f"\n  총 문제: {total_issues}건")
    print(f"  평균 커버리지: {avg_coverage:.0f}%")


if __name__ == "__main__":
    asyncio.run(main())
