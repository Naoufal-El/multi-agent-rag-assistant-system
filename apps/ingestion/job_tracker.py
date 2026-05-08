"""
Job Tracker
Tracks ingestion job state and progress
"""
from datetime import datetime, UTC
from typing import Optional, Dict, List
from apps.models.ingestion.state import IngestionJob, FileStatus
from apps.models.ingestion.enums import JobStatus


class JobTracker:
    """
    Track ingestion job state

    Note: In-memory storage for now
    Future: Store in PostgreSQL for persistence
    """

    def __init__(self):
        self.current_job: Optional[IngestionJob] = None
        self.job_history: List[IngestionJob] = []
        self.max_history = 10

    def create_job(self, files: List[str]) -> IngestionJob:
        """Create new ingestion job"""
        import uuid

        job = IngestionJob(
            job_id=f"job_{uuid.uuid4().hex[:8]}",
            status=JobStatus.PENDING,
            files_total=len(files),
            started_at=datetime.now(UTC),
            file_statuses=[
                FileStatus(filename=f, status="pending")
                for f in files
            ]
        )

        self.current_job = job
        print(f"[JobTracker] Created job {job.job_id} with {len(files)} files")
        return job

    def start_job(self) -> None:
        """Mark job as running"""
        if self.current_job:
            self.current_job.status = JobStatus.RUNNING
            self.current_job.started_at = datetime.now(UTC)
            print(f"[JobTracker] Started job {self.current_job.job_id}")

    def update_file_status(
            self,
            filename: str,
            status: str,
            chunks_created: int = 0,
            error: Optional[str] = None
    ) -> None:
        """Update individual file status"""
        if not self.current_job:
            return

        for file_status in self.current_job.file_statuses:
            if file_status.filename == filename:
                file_status.status = status
                file_status.chunks_created = chunks_created
                file_status.error = error

                if status == "processing":
                    file_status.started_at = datetime.now(UTC)
                elif status in ["completed", "failed"]:
                    file_status.completed_at = datetime.now(UTC)

                if status == "completed":
                    self.current_job.files_processed += 1
                    self.current_job.chunks_total += chunks_created
                else:
                    self.current_job.files_failed += 1

                break

    def complete_job(self, success: bool = True, error: Optional[str] = None) -> None:
        """Mark job as completed or failed"""
        if not self.current_job:
            return

        self.current_job.status = JobStatus.COMPLETED if success else JobStatus.FAILED
        self.current_job.completed_at = datetime.now(UTC)
        self.current_job.error = error

        # Add to history
        self.job_history.append(self.current_job)

        # Keep only last N jobs
        if len(self.job_history) > self.max_history:
            self.job_history = self.job_history[-self.max_history:]

        duration = self.current_job.get_duration_seconds()
        print(f"[JobTracker] Completed job {self.current_job.job_id} in {duration:.2f}s")
        print(f"[JobTracker] Files: {self.current_job.files_processed}/{self.current_job.files_total} processed")
        print(f"[JobTracker] Chunks: {self.current_job.chunks_total} total")

        self.current_job = None

    def cancel_job(self) -> None:
        """Cancel running job"""
        if self.current_job:
            self.current_job.status = JobStatus.CANCELLED
            self.current_job.completed_at = datetime.now(UTC)
            self.job_history.append(self.current_job)
            print(f"[JobTracker] Cancelled job {self.current_job.job_id}")
            self.current_job = None

    def get_status(self) -> Dict:
        """Get current job status"""
        if not self.current_job:
            return {
                'status': JobStatus.IDLE,
                'message': 'No job running'
            }

        return {
            'job_id': self.current_job.job_id,
            'status': self.current_job.status,
            'progress': self.current_job.get_progress_percent(),
            'files_total': self.current_job.files_total,
            'files_processed': self.current_job.files_processed,
            'files_failed': self.current_job.files_failed,
            'chunks_total': self.current_job.chunks_total,
            'duration_seconds': self.current_job.get_duration_seconds(),
            'started_at': self.current_job.started_at.isoformat() if self.current_job.started_at else None
        }

    def get_history(self) -> List[Dict]:
        """Get job history"""
        return [
            {
                'job_id': job.job_id,
                'status': job.status,
                'files_total': job.files_total,
                'files_processed': job.files_processed,
                'files_failed': job.files_failed,
                'chunks_total': job.chunks_total,
                'duration_seconds': job.get_duration_seconds(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'error': job.error
            }
            for job in reversed(self.job_history)
        ]


# Singleton instance
job_tracker = JobTracker()