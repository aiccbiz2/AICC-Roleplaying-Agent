"""롤플레이 후 피드백 분석"""
from __future__ import annotations

import json

from llm import call_claude, call_claude_async

# ── 중급/고급 서술형 피드백 프롬프트 ─────────────────────────
FEEDBACK_PROMPT = """당신은 LG U+ AI사업2팀의 수석 세일즈 트레이너입니다.
신규 사업담당자가 AI 고객과 진행한 AICC 영업 롤플레이를 정답지 기반으로 정밀 분석하세요.

## 시나리오 정보
- 시나리오: {scenario_title}
- 고객 난이도: {persona_level}

## 정답지 — 고객이 물어볼 예상 질문 목록
{key_questions_section}

## 정답지 — 이 시나리오에서 반드시 알아야 할 함정/주의사항
{traps_section}

## 실제 대화 내용
{conversation}

---

## 분석 지시사항

반드시 아래 JSON 형식으로만 답변하세요. 코드블록 없이 순수 JSON만:

{{
  "overall_score": "A/B/C/D 중 하나 (A=우수 90점이상, B=양호 70점이상, C=보통 50점이상, D=미흡 50점미만)",

  "question_coverage": {{
    "covered": ["실제로 대화에서 다룬 질문 (예상 질문 목록 기준)"],
    "missed": ["아예 다루지 못한 질문 또는 불충분하게 답한 질문"],
    "coverage_rate": "N/M (다룬 질문 수/전체 예상 질문 수)"
  }},

  "auto_q_analysis": [
    {{
      "question": "예상 질문 원문",
      "status": "충분히 답변 | 부분적 답변 | 미답변",
      "what_was_said": "사업담당자가 실제로 말한 내용 요약 (없으면 '언급 없음')",
      "ideal_answer": "이 질문에 대한 이상적인 답변 핵심 포인트 2-3개",
      "gap": "부족했던 점 또는 보완이 필요한 내용 (충분히 답변한 경우 '없음')"
    }}
  ],

  "trap_handling": [
    {{
      "trap": "함정/주의사항 원문",
      "handled": true/false,
      "how": "어떻게 대응했는지 (처리하지 못했으면 '대응 없음')",
      "ideal": "이상적인 대응 방법"
    }}
  ],

  "strengths": [
    "잘한 점 1 — 구체적인 발화 인용 포함",
    "잘한 점 2 — 구체적인 발화 인용 포함"
  ],

  "improvements": [
    "개선점 1 — 구체적으로 무엇을 어떻게 고쳐야 하는지",
    "개선점 2 — 구체적으로 무엇을 어떻게 고쳐야 하는지",
    "개선점 3 — 구체적으로 무엇을 어떻게 고쳐야 하는지"
  ],

  "terminology_check": {{
    "correctly_used": ["정확히 사용한 AICC 핵심 용어들"],
    "missed_or_wrong": ["놓쳤거나 잘못 사용한 용어들"],
    "tip": "용어 활용 관련 한줄 팁"
  }},

  "best_moment": "대화 중 가장 잘한 순간 — 구체적 발화 인용",
  "worst_moment": "대화 중 가장 아쉬운 순간 — 구체적 발화 인용",
  "expert_answer": "가장 아쉬운 순간에 수석 트레이너라면 이렇게 답변했을 것 (모범 답변 예시 2-3문장)",
  "next_focus": "다음 연습에서 딱 한 가지만 집중한다면 무엇인지 (구체적, 실행 가능하게)"
}}"""


# ── 초급 객관식 피드백 프롬프트 ─────────────────────────────
FEEDBACK_PROMPT_BEGINNER = """당신은 LG U+ AI사업2팀의 수석 세일즈 트레이너입니다.
아래는 신규 담당자가 진행한 AICC 영업 롤플레이 (초급 객관식 모드) 결과입니다.

## 시나리오 정보
- 시나리오: {scenario_title}
- 고객 난이도: {persona_level} (초급 — 객관식)

## 객관식 결과
- 총 문항: {total_questions}
- 정답: {correct_count}
- 정답률: {correct_rate}%

## 오답 상세
{wrong_details}

## 대화 요약
{conversation}

반드시 아래 JSON 형식으로만 답변하세요:

{{
  "overall_score": "A/B/C/D (A=90%이상, B=70%이상, C=50%이상, D=50%미만)",
  "correct_rate": "{correct_count}/{total_questions} ({correct_rate}%)",
  "strengths": ["잘 대응한 부분 1", "잘 대응한 부분 2"],
  "wrong_answers": [
    {{
      "turn": 1,
      "question": "고객 질문 요약",
      "selected": "선택한 답변",
      "correct": "정답",
      "why_wrong": "왜 선택한 답변이 틀렸는지",
      "why_correct": "왜 정답이 맞는지 — AICC 도메인 관점에서"
    }}
  ],
  "weak_areas": ["취약 영역 1 (어떤 유형에서 틀렸는지)", "취약 영역 2"],
  "improvements": ["개선 포인트 1", "개선 포인트 2"],
  "next_focus": "다음에 반드시 공부할 한 가지"
}}

오답이 없으면 wrong_answers를 빈 배열 []로 답변하세요."""


def _build_key_questions_section(scenario_data: dict) -> str:
    questions = scenario_data.get("key_questions", [])
    if not questions:
        return "(시나리오 예상 질문 목록 없음)"
    return "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))


def _build_traps_section(scenario_data: dict) -> str:
    traps = scenario_data.get("traps", [])
    if not traps:
        return "(함정/주의사항 없음)"
    return "\n".join(f"- {t}" for t in traps)


def format_conversation(chat_history: list[dict]) -> str:
    lines = []
    for msg in chat_history:
        role = "🧑 [나(사업담당)]" if msg["role"] == "user" else "👤 [고객(AI)]"
        lines.append(f"{role}: {msg['content']}")
    return "\n\n".join(lines)


def analyze_roleplay(
    chat_history: list[dict],
    scenario_title: str,
    persona_level: str,
    scenario_data: dict | None = None,
) -> dict:
    conversation = format_conversation(chat_history)
    sd = scenario_data or {}
    prompt = FEEDBACK_PROMPT.format(
        scenario_title=scenario_title,
        persona_level=persona_level,
        conversation=conversation,
        key_questions_section=_build_key_questions_section(sd),
        traps_section=_build_traps_section(sd),
    )
    text = call_claude(prompt)
    return _parse_feedback(text)


async def analyze_roleplay_async(
    chat_history: list[dict],
    scenario_title: str,
    persona_level: str,
    mode: str = "free_text",
    answer_history: list[dict] | None = None,
    scenario_data: dict | None = None,
) -> dict:
    conversation = format_conversation(chat_history)

    if mode == "multiple_choice" and answer_history:
        return await _analyze_beginner_async(
            conversation, scenario_title, persona_level, answer_history
        )

    sd = scenario_data or {}
    prompt = FEEDBACK_PROMPT.format(
        scenario_title=scenario_title,
        persona_level=persona_level,
        conversation=conversation,
        key_questions_section=_build_key_questions_section(sd),
        traps_section=_build_traps_section(sd),
    )
    # max_tokens 4096으로 증가 — 상세 분석에 충분한 토큰 확보
    text = await call_claude_async(prompt, max_tokens=4096)
    return _parse_feedback(text)


async def _analyze_beginner_async(
    conversation: str,
    scenario_title: str,
    persona_level: str,
    answer_history: list[dict],
) -> dict:
    total = len(answer_history)
    correct = sum(1 for a in answer_history if a.get("isCorrect"))
    rate = round(100 * correct / total) if total > 0 else 0

    wrong_items = [a for a in answer_history if not a.get("isCorrect")]
    wrong_details = "\n".join(
        f"- 턴 {a['turn']}: 질문 \"{a.get('question', '')[:60]}...\"\n"
        f"  선택: \"{a.get('selected', '')}\"\n"
        f"  정답: \"{a.get('correct', '')}\""
        for a in wrong_items
    ) if wrong_items else "(오답 없음)"

    prompt = FEEDBACK_PROMPT_BEGINNER.format(
        scenario_title=scenario_title,
        persona_level=persona_level,
        total_questions=total,
        correct_count=correct,
        correct_rate=rate,
        wrong_details=wrong_details,
        conversation=conversation[:2000],
    )
    text = await call_claude_async(prompt, max_tokens=3072)
    return _parse_feedback(text)


def _strip_markdown_codeblock(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline > 0:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _parse_feedback(text: str) -> dict:
    text = _strip_markdown_codeblock(text)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        # 잘린 JSON 복구 시도
        try:
            start = text.find("{")
            if start >= 0:
                partial = text[start:]
                open_braces = partial.count("{") - partial.count("}")
                open_brackets = partial.count("[") - partial.count("]")
                repaired = partial + "]" * max(open_brackets, 0) + "}" * max(open_braces, 0)
                return json.loads(repaired)
        except (json.JSONDecodeError, ValueError):
            pass

        import re
        score_match = re.search(r'"overall_score"\s*:\s*"([ABCD])"', text)
        return {
            "overall_score": score_match.group(1) if score_match else "?",
            "strengths": ["(피드백 분석 중 오류가 발생했습니다. 다시 시도해주세요.)"],
            "improvements": ["다시 시도해 주세요."],
            "question_coverage": {"covered": [], "missed": [], "coverage_rate": "0/0"},
            "auto_q_analysis": [],
            "trap_handling": [],
            "error_partial": True,
        }
