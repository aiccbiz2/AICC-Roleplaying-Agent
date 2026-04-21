"""롤플레이 후 피드백 분석"""
from __future__ import annotations

import json

from llm import call_claude, call_claude_async

FEEDBACK_PROMPT = """당신은 LG U+ AI사업2팀의 시니어 도메인 전문가입니다.
아래는 신규 담당자가 AI 고객과 진행한 AICC 사업 롤플레이 대화입니다.

## 시나리오 정보
- 시나리오: {scenario_title}
- 고객 난이도: {persona_level}

## 대화 내용
{conversation}

## 분석 기준

아래 항목을 분석하고 JSON으로 답변하세요:

1. **도메인 용어 사용**: IPCC/AICC 핵심 용어(PBX, CTI, IVR, ACD, STT, TTS, RAG 등)를 정확하게 사용했는가
2. **질문 대응력**: 고객의 질문에 충분하고 정확하게 답변했는가
3. **핵심 메시지 전달**: 제품/서비스의 가치를 효과적으로 설명했는가
4. **함정 대응**: 고객의 반박이나 어려운 질문에 적절히 대처했는가
5. **대화 태도**: 전문적이면서 고객 친화적인 태도를 유지했는가

반드시 아래 JSON 형식으로만 답변하세요:
{{
  "overall_score": "A/B/C/D 중 하나 (A=우수, B=양호, C=보통, D=미흡)",
  "strengths": ["잘한 점 1", "잘한 점 2"],
  "improvements": ["개선할 점 1", "개선할 점 2", "개선할 점 3"],
  "terminology_check": {{
    "correctly_used": ["정확히 사용한 용어들"],
    "missed_or_wrong": ["놓쳤거나 잘못 사용한 용어들"],
    "tip": "용어 관련 한줄 팁"
  }},
  "best_moment": "대화 중 가장 잘한 순간 (구체적 인용)",
  "worst_moment": "대화 중 가장 아쉬운 순간 (구체적 인용)",
  "expert_answer": "가장 아쉬운 순간에 전문가라면 이렇게 대응했을 것: (모범 답변 예시)",
  "next_focus": "다음 연습에서 집중할 포인트 한 가지"
}}"""


FEEDBACK_PROMPT_BEGINNER = """당신은 LG U+ AI사업2팀의 시니어 도메인 전문가입니다.
아래는 신규 담당자가 AI 고객과 진행한 AICC 사업 롤플레이 (초급 객관식 모드) 결과입니다.

## 시나리오 정보
- 시나리오: {scenario_title}
- 고객 난이도: {persona_level} (초급 — 객관식)

## 객관식 답안 결과
- 총 문항 수: {total_questions}
- 정답 수: {correct_count}
- 정답률: {correct_rate}%

## 오답 문항 상세
{wrong_details}

## 대화 내용 요약
{conversation}

## 분석 기준
초급 객관식 모드이므로, 자유롭게 작성한 답변이 아닌 **선택한 답변의 정답 여부**를 기반으로 피드백하세요.
"~~을 언급했어야 했다" 같은 주관식 피드백은 하지 마세요. 대신:
1. 정답률 기반 전체 수준 평가
2. 오답 문항별로 왜 틀렸는지, 정답이 왜 맞는지 해설
3. 취약한 영역 (어떤 유형의 질문에서 주로 틀렸는지)
4. 다음에 공부할 포인트

반드시 아래 JSON 형식으로만 답변하세요:
{{
  "overall_score": "A/B/C/D 중 하나 (A=90%이상, B=70%이상, C=50%이상, D=50%미만)",
  "correct_rate": "{correct_count}/{total_questions} ({correct_rate}%)",
  "strengths": ["잘 대응한 부분 1", "잘 대응한 부분 2"],
  "wrong_answers": [설명은 아래 참조],
  "improvements": ["개선 포인트 1", "개선 포인트 2"],
  "next_focus": "다음 연습에서 집중할 포인트"
}}

wrong_answers 배열 예시:
[
  {{
    "turn": 1,
    "question": "고객의 질문 요약",
    "selected": "사용자가 선택한 답변",
    "correct": "정답 답변",
    "explanation": "왜 정답이 맞고 선택한 답변이 틀린지 해설"
  }}
]
오답이 없으면 빈 배열 []로 답변하세요."""


def format_conversation(chat_history: list[dict]) -> str:
    """대화 히스토리를 분석용 텍스트로 변환"""
    lines = []
    for msg in chat_history:
        role = "🧑 [나(사업담당)]" if msg["role"] == "user" else "👤 [고객]"
        lines.append(f"{role}: {msg['content']}")
    return "\n\n".join(lines)


def analyze_roleplay(
    chat_history: list[dict],
    scenario_title: str,
    persona_level: str,
) -> dict:
    """롤플레이 대화 분석 및 피드백 생성"""
    conversation = format_conversation(chat_history)

    prompt = FEEDBACK_PROMPT.format(
        scenario_title=scenario_title,
        persona_level=persona_level,
        conversation=conversation,
    )

    text = call_claude(prompt)
    return _parse_feedback(text)


async def analyze_roleplay_async(
    chat_history: list[dict],
    scenario_title: str,
    persona_level: str,
    mode: str = "free_text",
    answer_history: list[dict] | None = None,
) -> dict:
    """비동기 롤플레이 대화 분석 및 피드백 생성"""
    conversation = format_conversation(chat_history)

    if mode == "multiple_choice" and answer_history:
        return await _analyze_beginner_async(
            conversation, scenario_title, persona_level, answer_history
        )

    prompt = FEEDBACK_PROMPT.format(
        scenario_title=scenario_title,
        persona_level=persona_level,
        conversation=conversation,
    )
    text = await call_claude_async(prompt, max_tokens=2048)
    return _parse_feedback(text)


async def _analyze_beginner_async(
    conversation: str,
    scenario_title: str,
    persona_level: str,
    answer_history: list[dict],
) -> dict:
    """초급 객관식 모드 전용 피드백 생성"""
    total = len(answer_history)
    correct = sum(1 for a in answer_history if a.get("isCorrect"))
    rate = round(100 * correct / total) if total > 0 else 0

    wrong_items = [a for a in answer_history if not a.get("isCorrect")]
    wrong_details = "\n".join(
        f"- 턴 {a['turn']}: 고객 질문 \"{a.get('question', '')[:60]}...\"\n"
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
    text = await call_claude_async(prompt, max_tokens=1536)
    return _parse_feedback(text)


def _strip_markdown_codeblock(text: str) -> str:
    """Gemini 등이 ```json ... ``` 으로 감싸는 경우 제거"""
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
        # 텍스트에서 JSON 추출 시도
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        # 불완전 JSON 복구 시도: 잘린 JSON에 "}" 추가
        try:
            start = text.find("{")
            if start >= 0:
                partial = text[start:]
                # 열린 괄호 수만큼 닫기
                open_braces = partial.count("{") - partial.count("}")
                open_brackets = partial.count("[") - partial.count("]")
                repaired = partial + "]" * max(open_brackets, 0) + "}" * max(open_braces, 0)
                return json.loads(repaired)
        except (json.JSONDecodeError, ValueError):
            pass

        # 최소한의 정보라도 추출
        import re
        score_match = re.search(r'"overall_score"\s*:\s*"([ABCD])"', text)
        return {
            "overall_score": score_match.group(1) if score_match else "?",
            "strengths": ["(피드백 JSON이 불완전하여 전체 분석을 표시할 수 없습니다.)"],
            "improvements": ["다시 시도해 주세요."],
            "error_partial": True,
        }
