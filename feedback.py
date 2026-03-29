"""롤플레이 후 피드백 분석"""
from __future__ import annotations

import json

from llm import call_claude

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

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {"error": "피드백 생성에 실패했습니다.", "raw": text}
