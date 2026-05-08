from pydantic_settings import BaseSettings
from typing import Literal
from apps.config.redis_settings import redis_settings, RedisSettings
from apps.config.db_settings import db_settings, DBSettings
from apps.config.llm_settings import llm_settings, LLMSettings
from apps.config.qdrant_settings import qdrant_settings, QdrantSettings
from apps.config.memory_settings import memory_settings, MemorySettings
from apps.config.ingestion_settings import ingestion_settings, IngestionSettings
from apps.config.validation_settings import validation_settings, ValidationSettings
from apps.config.auth_settings import auth_settings, AuthenticationSettings

class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    redis: RedisSettings = redis_settings
    db: DBSettings = db_settings
    llm: LLMSettings = llm_settings
    qdrant: QdrantSettings = qdrant_settings
    memory: MemorySettings = memory_settings
    ingestion: IngestionSettings = ingestion_settings
    validation: ValidationSettings = validation_settings
    auth: AuthenticationSettings = auth_settings

    # Feature Flags
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    controller_timeout: int = 120

    # class Config:
    #     env_file = ".env"
    #     case_sensitive = False
    #     extra = "ignore"

settings = Settings()

"""
class Settings(BaseSettings):
    ###Global application settings

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    max_history_msgs: int = 8

    # Database Configuration
    # database_url: str = "postgresql://user:pass@localhost:5432/agentic_db"
    database_url: str = "postgresql://myuser:mypassword@localhost:5433/agentic_db"

    # Ollama Configuration
    ollama_base: str = "http://localhost:11434"
    llm_local_model: str = "gemma3:4b"
    embedding_model: str = "nomic-embed-text"

    # Qdrant Configuration
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "knowledge_base"
    qdrant_vector_size: int = 768  # nomic-embed-text dimensions

    # RAG Configuration
    retrieval_enabled: bool = True
    retrieval_top_k: int = 5  # Number of documents to retrieve
    chunk_size: int = 500  # Characters per chunk
    chunk_overlap: int = 50  # Overlap between chunks

    # Feature Flags
    cloud_llm_enabled: bool = False

    # Monitoring
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    controller_timeout: int = 120  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

settings = Settings()

# Debug logging
print(f"[SETTINGS] Loaded controller_timeout={settings.controller_timeout}")
print(f"[SETTINGS] Loaded ollama_base={settings.ollama_base}")
print(f"[SETTINGS] Loaded qdrant_url={settings.qdrant_url}")
print(f"[SETTINGS] Loaded retrieval_enabled={settings.retrieval_enabled}")
"""