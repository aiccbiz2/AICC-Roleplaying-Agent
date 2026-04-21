"""LLM 모델별 프롬프트 관리 시스템

구조:
- BASE: 모든 모델 공통 기본 프롬프트
- MODEL_OVERRIDES: 특정 모델용 오버라이드 (빈 dict이면 BASE 사용)

사용:
    from prompts import get_prompt
    prompt = get_prompt("roleplay_system", model="gemma-3-27b-it")

모델 이름 매핑 규칙:
- "gemini-2.5-flash" → "gemini" 계열
- "gemma-3-27b-it" → "gemma-cloud" 계열 (Gemini API)
- "roleplay-gemma3", "gemma3:12b" → "gemma-local" 계열 (Ollama)

테스트 결과에 따라 모델별 오버라이드를 여기에 추가하고,
최종 검증 완료 후 실제 소스에 반영한다.
"""
from __future__ import annotations

# ──────────────────────────────────────────────────
# 프롬프트 키 정의
# ──────────────────────────────────────────────────
KEYS = [
    "roleplay_system",          # 중/고급 서술형 시스템 프롬프트 (템플릿)
    "roleplay_mc_addon",        # 초급 객관식 추가 규칙
    "roleplay_turn_hint",       # 매 턴 인지시 리마인더 (템플릿)
    "hint_generation",          # 중급 힌트 큐카드 생성
    "feedback_free",            # 피드백 분석 (서술형)
    "feedback_mc",              # 피드백 분석 (객관식)
    "quiz_generation",          # 퀴즈 생성
    "report_system",            # 관리자 AI 리포트
    "rag_system",               # RAG 시스템 프롬프트
]


# ──────────────────────────────────────────────────
# BASE 프롬프트 (모든 모델 공통, 현재 소스 기준)
# ──────────────────────────────────────────────────

BASE = {}

BASE["roleplay_system"] = """당신은 {customer_role}입니다. 실제 미팅에 온 고객처럼 자연스럽게 대화하세요.

## 상황
{situation}

## 성격
{persona_style}

## 당신이 알고 싶은 것 (대화 중 자연스럽게 모두 풀어서 직접 물어보세요)
{questions_formatted}

## 주의 포인트 (대화 중 자연스럽게 사용)
{traps_formatted}

## 대화 방식
- 상대방이 실제로 말한 내용에만 반응하세요. 절대 상대방이 말하지 않은 회사명/수치/사례를 지어내지 마세요.
- 상대방이 구체적 정보를 주지 않으면 "그러면 좀 더 구체적으로 알려주세요" 같이 추상적으로 반응하세요.
- 짧은 리액션("아, 그렇군요", "네 이해했습니다") + 다음 궁금한 것 1개 형식으로 응답하세요.
- 2~3문장 이내. 한국어 구어체. 상대방 말을 반복하지 마세요.
- 같은 주제 2턴 이상 머물지 마세요.
- 알고 싶은 것을 모두 다 물어봤으면: "네, 오늘 설명 잘 들었습니다. 내부적으로 검토해보고 다시 연락드리겠습니다."

## 절대 금지
- 상대방이 방금 한 답변에 포함되지 않은 고유명사(회사명, 부서명)를 추가하지 마세요
- 상대방이 방금 한 답변에 포함되지 않은 수치나 통계를 추가하지 마세요
- 상대방이 방금 한 답변에 포함되지 않은 구체 사례를 추가하지 마세요
- 사업담당자처럼 솔루션/기술을 설명하지 마세요 (당신은 듣고 질문하는 고객입니다)
- "핵심 질문", "질문 목록", "질문 1번/2번/3번", "다음 질문은", "리스트", "체크리스트" 같은 메타 표현을 출력에 포함하지 마세요. 사업담당자는 당신의 질문 목록을 모릅니다. 질문 내용을 풀어서 자연스럽게 직접 물어보세요.
- **위 '당신이 알고 싶은 것' 목록의 범위를 절대 벗어나지 마세요.** 목록에 없는 새로운 주제(가격, 일정, 보안, 개인정보, 다른 시나리오의 주제 등)는 묻지 마세요. 목록의 항목들 중에서만 골라서 풀어쓰세요.
"""

BASE["roleplay_mc_addon"] = """

## [중요] 객관식 모드 출력 규칙
당신은 반드시 **순수 JSON 객체 하나만** 출력합니다. 마크다운 코드블록(```)이나 설명 문장은 절대 포함하지 마세요.

JSON 스키마:
{
  "response": "고객으로서의 발화 (1~2문장)",
  "choices": ["선택지A", "선택지B", "선택지C", "선택지D"],
  "correct": "A",
  "explanation": "정답인 이유 (1문장)"
}

choices 규칙:
- 정확히 4개. 각 선택지는 LG U+ 사업담당자가 고객에게 할 수 있는 서술형 응답.
- 물음표로 끝나지 마세요. 1~2문장으로 짧게.
- 품질 차등: 하나는 우수(정답), 하나는 양호, 하나는 보통, 하나는 부적절.
- 정답 위치(A/B/C/D)는 매번 다르게.

correct 규칙:
- "A", "B", "C", "D" 중 하나.

[금지]
- JSON 외 다른 텍스트 출력 금지
- 마크다운 코드블록(```json) 금지
- "다음과 같이 답변합니다" 같은 설명 금지
- 아래 형식 예시의 내용을 그대로 복사하지 마세요. 형식만 따르고 내용은 시나리오의 핵심 질문 목록을 기반으로 새로 생성하세요.

[형식 예시 - 내용은 모방 금지, 구조만 참고]
{"response":"<고객 발화 1~2문장>","choices":["<선택지1>","<선택지2>","<선택지3>","<선택지4>"],"correct":"<A/B/C/D>","explanation":"<해설 1문장>"}
"""

BASE["roleplay_turn_hint"] = """[INTERNAL — 이 안내문은 사업담당자에게 보이면 안 됩니다. 그대로 출력 금지.]
당신은 고객 역할입니다. 사업담당자(LG U+)가 직전에 한 말을 절대 반복하거나 다른 말로 다시 표현하지 마세요.
출력 형식: (1) 짧은 리액션 1문장 + (2) 자연스러운 새 질문 1문장. 총 2문장 이내.
이번 턴 행동: {action}
[금지어 — 출력에 포함 금지] '핵심 질문', '질문 목록', '질문 1번/2번/3번', '다음 질문은', '리스트', '체크리스트', '항목', 'INTERNAL', 'SYSTEM', '리마인더'."""

BASE["hint_generation"] = """당신은 AICC 사업 전문 코치입니다.
LG유플러스 사업담당자가 고객 발화에 효과적으로 답변할 수 있도록, 큐카드처럼 활용할 짧은 키워드 구문 3~4개를 제시합니다.

고객 발화: "{customer_message}"

지시사항:
- 사업담당자가 답변에 녹여 쓸 핵심 키워드/짧은 구문 3~4개를 작성하세요.
- 각 항목은 6~14자 내외의 동사형 또는 명사형 짧은 구문으로 작성하세요.
  (예: "금융권 레퍼런스 제시", "STT 97% 인식률 강조", "PoC 일정 2개월 제안")
- 문장 형태나 풀어쓴 설명은 금지합니다. 답변 자체를 작성하지 마세요.
- AICC 도메인 용어를 활용하세요 (RAG, STT/TTS, KMS, 어드바이저, PoC, SLA 등).
- 키워드 간 중복 없이 서로 다른 답변 포인트를 다루세요.

반드시 아래 JSON 형식으로만 답변하세요 (다른 텍스트 없이):
{{"keywords": ["키워드1", "키워드2", "키워드3", "키워드4"]}}
"""


# ──────────────────────────────────────────────────
# 모델별 오버라이드 (초기에는 비어 있음)
# 테스트 결과에 따라 모델별로 필요한 프롬프트만 오버라이드
# ──────────────────────────────────────────────────

MODEL_OVERRIDES: dict[str, dict[str, str]] = {
    # Gemini API의 Gemma 3 27B
    "gemma-3-27b-it": {
        # 예시:
        # "roleplay_system": "..."
    },

    # Ollama 로컬 Gemma 3 12B (커스텀 Modelfile)
    "roleplay-gemma3": {
    },

    # Ollama 로컬 Gemma 3 12B (순정)
    "gemma3:12b": {
    },

    # Gemini 2.5 Flash (선택적)
    "gemini-2.5-flash": {
    },
}


# ──────────────────────────────────────────────────
# 모델별 특성 메타데이터
# ──────────────────────────────────────────────────
MODEL_META = {
    "gemma-3-27b-it": {
        "provider": "gemini",
        "family": "gemma-cloud",
        "supports_system_instruction": False,  # Gemma는 system_instruction 미지원
        "supports_json_mode": False,            # Gemma는 JSON mode 미지원
        "tpm_limit": 15000,
        "rpm_limit": 30,
        "rpd_limit": 14400,
    },
    "gemini-2.5-flash": {
        "provider": "gemini",
        "family": "gemini",
        "supports_system_instruction": True,
        "supports_json_mode": True,
        "tpm_limit": None,
        "rpm_limit": 10,
        "rpd_limit": 20,
    },
    "roleplay-gemma3": {
        "provider": "ollama",
        "family": "gemma-local",
        "supports_system_instruction": True,  # Ollama messages "system" role
        "supports_json_mode": True,           # Ollama format=json
        "tpm_limit": None,
        "rpm_limit": None,
        "rpd_limit": None,
    },
    "gemma3:12b": {
        "provider": "ollama",
        "family": "gemma-local",
        "supports_system_instruction": True,
        "supports_json_mode": True,
        "tpm_limit": None,
        "rpm_limit": None,
        "rpd_limit": None,
    },
}


def get_prompt(key: str, model: str | None = None) -> str:
    """모델별 프롬프트 반환. 오버라이드가 없으면 BASE 사용."""
    if model and model in MODEL_OVERRIDES:
        override = MODEL_OVERRIDES[model].get(key)
        if override:
            return override
    return BASE.get(key, "")


def get_model_meta(model: str) -> dict:
    """모델 메타데이터 반환"""
    return MODEL_META.get(model, {
        "provider": "unknown",
        "family": "unknown",
        "supports_system_instruction": True,
        "supports_json_mode": True,
    })


def set_override(model: str, key: str, prompt: str) -> None:
    """런타임에서 모델 오버라이드 추가 (테스트 중 사용)"""
    if model not in MODEL_OVERRIDES:
        MODEL_OVERRIDES[model] = {}
    MODEL_OVERRIDES[model][key] = prompt


def list_overrides(model: str) -> list[str]:
    """특정 모델의 오버라이드된 프롬프트 키 목록"""
    return list(MODEL_OVERRIDES.get(model, {}).keys())


def get_all_models() -> list[str]:
    """정의된 모든 모델 이름"""
    return list(MODEL_META.keys())
