"""
Ingestion State Models
Pydantic models for tracking ingestion jobs
"""
from datetime import datetime, UTC
from typing import Optional, List
from pydantic import BaseModel
from apps.models.ingestion.enums import JobStatus


class FileStatus(BaseModel):
    """Individual file processing status"""
    filename: str
    status: str  # "processing", "completed", "failed"
    chunks_created: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class IngestionJob(BaseModel):
    """Ingestion job state"""
    job_id: str
    status: JobStatus
    files_total: int = 0
    files_processed: int = 0
    files_failed: int = 0
    chunks_total: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    file_statuses: List[FileStatus] = []

    def get_progress_percent(self) -> float:
        """Calculate progress percentage"""
        if self.files_total == 0:
            return 0.0
        return (self.files_processed / self.files_total) * 100

    def get_duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds"""
        if not self.started_at:
            return None

        end_time = self.completed_at or datetime.now(UTC)
        duration = end_time - self.started_at
        return duration.total_seconds()