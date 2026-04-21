"""Stage 1 MVP 설정"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# 프로젝트 경로
PROJECT_DIR = Path(__file__).parent
DOCS_DIR = PROJECT_DIR / "docs"
CHROMA_DIR = PROJECT_DIR / "chroma_db"
DB_PATH = PROJECT_DIR / "data" / "app.db"

# JWT 설정
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# 문서 경로
EDUCATION_DIR = DOCS_DIR / "교육자료"
MEETING_DIR = DOCS_DIR / "고객미팅"
GLOSSARY_PATH = DOCS_DIR / "도메인_용어사전.md"
QUESTION_DB_PATH = DOCS_DIR / "고객질문_패턴DB.md"
SCENARIO_PATH = DOCS_DIR / "롤플레이_시나리오.md"

# LLM Provider 설정
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")  # "gemini" | "claude-cli" | "ollama"
LLM_MODEL = os.environ.get("LLM_MODEL", "")  # 비어있으면 프로바이더별 기본값 사용
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# 프로바이더별 기본 모델
if not LLM_MODEL:
    LLM_MODEL = {
        "gemini": "gemini-2.5-flash",
        "claude-cli": "sonnet",
        "ollama": "roleplay-gemma3",
    }.get(LLM_PROVIDER, "gemini-2.5-flash")

# 로컬 임베딩 (API 불필요)
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"

# RAG 설정
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 5

# 컬렉션 이름
COLLECTION_NAME = "ipcc_aicc_knowledge"
