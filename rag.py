"""RAG 파이프라인: 질문 → 벡터 검색 → Claude CLI 답변"""
from __future__ import annotations

from langchain_community.vectorstores import Chroma
from langchain.schema import Document

from config import CHROMA_DIR, COLLECTION_NAME, TOP_K
from ingest import get_embeddings
from llm import call_claude

SYSTEM_PROMPT = """당신은 LG U+ AI사업2팀의 IPCC/AICC 도메인 전문가입니다.
아래 참고 자료를 기반으로 질문에 정확하게 답변하세요.

규칙:
1. 참고 자료에 있는 내용을 기반으로 답변하세요.
2. 참고 자료에 없는 내용은 "해당 내용은 현재 지식베이스에 없습니다"라고 솔직히 말하세요.
3. 컨택센터/IPCC/AICC 용어는 정식 명칭과 현장 표현을 함께 설명하세요.
4. 실제 고객 미팅에서 나온 사례가 있다면 함께 언급하세요.
5. 답변은 구조화하여 읽기 쉽게 작성하세요."""


def get_vectorstore() -> Chroma:
    """기존 ChromaDB 벡터 저장소 로드"""
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_DIR),
        embedding_function=get_embeddings(),
    )


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


def ask(query: str, chat_history: list[dict] | None = None) -> tuple[str, list[Document]]:
    """RAG 기반 질문 응답"""
    docs = retrieve(query)
    context = format_context(docs)

    # 이전 대화 포함
    history_text = ""
    if chat_history:
        for msg in chat_history[-6:]:
            role = "사용자" if msg["role"] == "user" else "AI"
            history_text += f"{role}: {msg['content']}\n"
        history_text += "\n"

    prompt = f"{history_text}참고 자료:\n{context}\n\n질문: {query}"

    answer = call_claude(prompt, system_prompt=SYSTEM_PROMPT)
    return answer, docs
