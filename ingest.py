"""문서 인제스트 파이프라인: docs/ → ChromaDB 벡터 저장소"""
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from config import (
    DOCS_DIR, CHROMA_DIR, COLLECTION_NAME,
    EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP,
)


def load_documents() -> list:
    """docs/ 하위의 모든 .md, .txt 파일을 로드"""
    docs = []
    for ext in ("*.md", "*.txt"):
        for path in DOCS_DIR.rglob(ext):
            try:
                loader = TextLoader(str(path), encoding="utf-8")
                loaded = loader.load()
                for doc in loaded:
                    doc.metadata["source"] = str(path.relative_to(DOCS_DIR))
                    doc.metadata["category"] = _categorize(path)
                docs.extend(loaded)
            except Exception as e:
                print(f"[WARN] {path.name} 로드 실패: {e}")
    return docs


def _categorize(path: Path) -> str:
    """파일 경로 기반 카테고리 분류"""
    rel = str(path.relative_to(DOCS_DIR))
    if "교육자료" in rel:
        return "교육자료"
    elif "고객미팅" in rel:
        return "고객미팅"
    elif "용어사전" in rel:
        return "용어사전"
    elif "패턴DB" in rel or "질문" in rel:
        return "고객질문"
    elif "시나리오" in rel:
        return "시나리오"
    return "기타"


def split_documents(docs: list) -> list:
    """청크 분할"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n---\n", "\n## ", "\n### ", "\n\n", "\n", " "],
    )
    return splitter.split_documents(docs)


def get_embeddings():
    """로컬 임베딩 모델 (API 불필요)"""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
    )


def create_vectorstore(chunks: list) -> Chroma:
    """ChromaDB 벡터 저장소 생성"""
    embeddings = get_embeddings()
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_DIR),
    )
    return vectorstore


def ingest():
    """전체 인제스트 파이프라인 실행"""
    print("📄 문서 로드 중...")
    docs = load_documents()
    print(f"  → {len(docs)}개 문서 로드 완료")

    print("✂️  청크 분할 중...")
    chunks = split_documents(docs)
    print(f"  → {len(chunks)}개 청크 생성")

    print("🔢 임베딩 및 벡터 저장소 생성 중 (로컬 모델)...")
    vectorstore = create_vectorstore(chunks)
    print(f"  → ChromaDB 저장 완료: {CHROMA_DIR}")

    return vectorstore


if __name__ == "__main__":
    ingest()
