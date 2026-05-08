"""
Ingestion Enums
Shared enums for ingestion system
"""
from enum import Enum


class JobStatus(str, Enum):
    """Job execution status"""
    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileStatusEnum(str, Enum):
    """File processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class PipelineMode(str, Enum):
    """Pipeline operation modes"""
    AUTOMATIC = "automatic"  # Worker processes files automatically
    MANUAL = "manual"        # Only manual triggers allowed
    PAUSED = "paused"        # All ingestion blocked