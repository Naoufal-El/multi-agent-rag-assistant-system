from pydantic import BaseModel
from typing import List, Optional


class IngestionStatusResponse(BaseModel):
    status: str
    job_id: Optional[str] = None
    progress: Optional[float] = None
    files_total: Optional[int] = None
    files_processed: Optional[int] = None
    files_failed: Optional[int] = None
    chunks_total: Optional[int] = None
    pending_files_count: int
    is_running: bool
    message: str


class CollectionInfoResponse(BaseModel):
    name: Optional[str] = None
    vectors_count: Optional[int] = None
    indexed_vectors_count: Optional[int] = None
    points_count: Optional[int] = None
    status: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class UploadFilesResponse(BaseModel):
    status: str
    message: str
    uploaded_files: List[str]
    failed_files: List[str]
    target_collection: str = "customer_kb"  # NEW: Track which collection