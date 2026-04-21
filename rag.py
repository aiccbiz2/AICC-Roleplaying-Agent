"""RAG 파이프라인: 질문 → 벡터 검색 → Claude CLI 답변"""
from __future__ import annotations

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from config import CHROMA_DIR, COLLECTION_NAME, TOP_K
from ingest import get_embeddings
from llm import call_claude_async

SYSTEM_PROMPT = """당신은 LG U+ AI사업2팀의 IPCC/AICC 도메인 전문가입니다.
아래 참고 자료를 기반으로 질문에 정확하게 답변하세요.

규칙:
1. 참고 자료에 있는 내용을 기반으로 답변하세요.
2. 참고 자료에 없는 내용은 "해당 내용은 현재 지식베이스에 없습니다"라고 솔직히 말하세요.
3. 컨택센터/IPCC/AICC 용어는 정식 명칭과 현장 표현을 함께 설명하세요.
4. 실제 고객 미팅에서 나온 사례가 있다면 함께 언급하세요.
5. 답변은 구조화하여 읽기 쉽게 작성하세요."""


_vectorstore_instance = None


def get_vectorstore() -> Chroma:
    """기존 ChromaDB 벡터 저장소 로드 — 싱글톤으로 재사용"""
    global _vectorstore_instance
    if _vectorstore_instance is None:
        _vectorstore_instance = Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=str(CHROMA_DIR),
            embedding_function=get_embeddings(),
        )
    return _vectorstore_instance


def retrieve(query: str, top_k: int = TOP_K) -> list[Document]:
    """쿼리와 유사한 문서 검색"""
    vectorstore = get_vectorstore()
    return vectorstore.similarity_search(query, k=top_k)


def format_context(docs: list[Document]) -> str:
    """검색 결과를 컨텍스트 문자열로 포맷"""
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "알 수 없음")
        category = doc.metadata.get("category", "")
        parts.append(f"[{i}] ({category}) {source}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


async def ask(query: str, chat_history: list[dict] | None = None) -> tuple[str, list[Document]]:
    """RAG 기반 질문 응답"""
    # 컨텍스트 크기 제한 (Ollama 같은 로컬 모델 속도 개선)
    docs = retrieve(query, top_k=3)  # 5 → 3
    context = format_context(docs)
    if len(context) > 2000:
        context = context[:2000] + "\n..."

    # 이전 대화 포함 (최근 4턴만)
    history_text = ""
    if chat_history:
        for msg in chat_history[-4:]:
            role = "사용자" if msg["role"] == "user" else "AI"
            history_text += f"{role}: {msg['content']}\n"
        history_text += "\n"

    prompt = f"{history_text}참고 자료:\n{context}\n\n질문: {query}"

    # max_tokens 제한으로 응답 시간 단축 (RAG 답변은 보통 500자 내외면 충분)
    answer = await call_claude_async(prompt, system_prompt=SYSTEM_PROMPT, max_tokens=512)
    return answer, docs
