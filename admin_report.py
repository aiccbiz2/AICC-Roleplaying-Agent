"""관리자 AI 종합 리포트 생성"""
from __future__ import annotations

from llm import call_claude_async

REPORT_SYSTEM_PROMPT = """당신은 AICC 사업팀의 학습 성과를 분석하는 전문 분석가입니다.
팀원들의 롤플레이 시뮬레이션 및 퀴즈 학습 데이터를 분석하여 종합 리포트를 생성합니다.

다음 형식의 마크다운 리포트를 작성하세요:

## 팀 종합 평가 리포트

### 1. 전체 요약
- 활성 학습 인원, 평균 등급, 가장 많이 연습한 시나리오 등

### 2. 팀원별 평가
| 이름 | 롤플레이 횟수 | 평균 등급 | 등급 추이 | 퀴즈 정답률 | 강점 | 개선점 |
(각 팀원의 피드백 데이터를 바탕으로 구체적으로 평가)

### 3. 시나리오별 분석
- 가장 어려워하는/잘하는 시나리오

### 4. 공통 개선점
- 팀 전체적으로 반복되는 약점

### 5. 추천 액션
- 구체적인 학습 방향 제안

데이터를 기반으로 객관적이고 건설적인 피드백을 제공하세요. 한국어로 작성합니다."""


async def generate_team_report(members_summary: list[dict], members_detail: list[dict]) -> str:
    lines = ["## 팀원별 학습 데이터\n"]

    for summary, detail in zip(members_summary, members_detail):
        name = summary.get("name", "?")
        lines.append(f"### {name} ({summary.get('position', '')}, {summary.get('department', '')})")
        lines.append(f"- 롤플레이: {summary.get('roleplay_count', 0)}회, 평균 등급: {summary.get('avg_grade', '-')}")
        lines.append(f"- 퀴즈: {summary.get('quiz_count', 0)}문제, 정답률: {summary.get('accuracy', 0)}%")
        lines.append(f"- 최근 활동: {summary.get('last_active', '-')}")

        # 롤플레이 등급 추이
        sessions = detail.get("roleplay_sessions", [])
        if sessions:
            grades = [s.get("overall_grade", "?") for s in reversed(sessions)]
            lines.append(f"- 등급 추이: {' → '.join(grades)}")

            # 피드백에서 강점/개선점 수집
            strengths = []
            improvements = []
            for s in sessions:
                fb = s.get("feedback")
                if fb:
                    strengths.extend(fb.get("strengths", []))
                    improvements.extend(fb.get("improvements", []))
            if strengths:
                lines.append(f"- 강점 키워드: {', '.join(strengths[:5])}")
            if improvements:
                lines.append(f"- 개선점 키워드: {', '.join(improvements[:5])}")

        # 퀴즈 카테고리별 정답률
        quiz_records = detail.get("quiz_records", [])
        if quiz_records:
            cat_stats: dict[str, dict] = {}
            for qr in quiz_records:
                cat = qr.get("category", "기타")
                if cat not in cat_stats:
                    cat_stats[cat] = {"correct": 0, "total": 0}
                cat_stats[cat]["total"] += 1
                if qr.get("is_correct"):
                    cat_stats[cat]["correct"] += 1
            cat_lines = [f"  - {c}: {s['correct']}/{s['total']} ({100*s['correct']//s['total'] if s['total'] else 0}%)" for c, s in cat_stats.items()]
            lines.append("- 퀴즈 카테고리별:\n" + "\n".join(cat_lines))

        lines.append("")

    prompt = "\n".join(lines)
    report = await call_claude_async(prompt, system_prompt=REPORT_SYSTEM_PROMPT, max_tokens=2048)
    return report
