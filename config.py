"""Stage 1 MVP 설정"""
from pathlib import Path

# 프로젝트 경로
PROJECT_DIR = Path(__file__).parent
DOCS_DIR = PROJECT_DIR / "docs"
CHROMA_DIR = PROJECT_DIR / "chroma_db"

# 문서 경로
EDUCATION_DIR = DOCS_DIR / "교육자료"
MEETING_DIR = DOCS_DIR / "고객미팅"
GLOSSARY_PATH = DOCS_DIR / "도메인_용어사전.md"
QUESTION_DB_PATH = DOCS_DIR / "고객질문_패턴DB.md"
SCENARIO_PATH = DOCS_DIR / "롤플레이_시나리오.md"

# Claude CLI 설정 (Pro/Max 구독 — 무료)
LLM_MODEL = "sonnet"  # CLI 모델 alias

# 로컬 임베딩 (API 불필요)
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"

# RAG 설정
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 5

# 컬렉션 이름
COLLECTION_NAME = "ipcc_aicc_knowledge"
