"""
Document Ingestion Configuration Settings
Manages document loading, processing, and indexing configuration
"""
from envyaml import EnvYAML
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal
from pathlib import Path


# Load configuration from YAML with .env variable substitution
envIngestion = EnvYAML("apps/config/ingestion_conf.yaml")
params = envIngestion.get("params", {})


class IngestionSettings(BaseModel):
    """Document ingestion configuration"""

    # Directory Paths
    pending_dir: str
    processing_dir: str
    completed_dir: str
    failed_dir: str

    # Supported Formats
    supported_extensions: str  # Comma-separated string

    # Job Scheduling
    auto_scan_enabled: bool
    scan_interval_minutes: int

    # Document Processing
    chunk_size: int = Field(ge=100, le=5000)
    chunk_overlap: int = Field(ge=0, le=500)
    min_chunk_size: int = Field(ge=50, le=500)

    # File Validation
    max_file_size_mb: int = Field(ge=1, le=100)
    max_concurrent_files: int = Field(ge=1, le=20)

    # Batch Processing
    batch_size: int = Field(ge=1, le=100)
    retry_failed_files: bool
    max_retries: int = Field(ge=1, le=10)

    # Qdrant
    create_collection_if_not_exists: bool

    @field_validator('supported_extensions')
    @classmethod
    def validate_extensions(cls, v: str) -> str:
        """Ensure extensions start with dot"""
        extensions = [ext.strip() for ext in v.split(',')]
        for ext in extensions:
            if not ext.startswith('.'):
                raise ValueError(f"Extension must start with dot: {ext}")
        return v

    @field_validator('chunk_overlap')
    @classmethod
    def validate_overlap(cls, v: int, info) -> int:
        """Ensure overlap is less than chunk size"""
        chunk_size = info.data.get('chunk_size', 1000)
        if v >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v

    def get_extensions_list(self) -> List[str]:
        """Parse comma-separated extensions into list"""
        return [ext.strip() for ext in self.supported_extensions.split(',')]

    def get_all_dirs(self) -> List[Path]:
        """Get all directory paths as Path objects"""
        return [
            Path(self.pending_dir),
            Path(self.processing_dir),
            Path(self.completed_dir),
            Path(self.failed_dir)
        ]

    def is_supported_file(self, filename: str) -> bool:
        """Check if file extension is supported"""
        extensions = self.get_extensions_list()
        return any(filename.lower().endswith(ext) for ext in extensions)


# Singleton instance
ingestion_settings = IngestionSettings(**params)