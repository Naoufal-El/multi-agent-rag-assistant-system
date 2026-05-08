"""
Background Worker
Handles scheduled document ingestion jobs
"""
import asyncio
from datetime import datetime, UTC
from typing import Optional
from apps.services.ingestionJobService import ingestion_job_service
from apps.config.settings import settings
from apps.services.ingestionService import ingestion_service
from apps.utils.directory_manager import directory_manager


class BackgroundWorker:
    """
    Background worker for automatic document ingestion

    Startup behavior:
    - If auto_scan_enabled=true: Starts automatically with app
    - If auto_scan_enabled=false: Doesn't start, but can be started via API

    Runtime behavior:
    - Controlled ONLY by pipeline mode (AUTOMATIC/MANUAL/PAUSED)
    - .env setting is ignored during runtime
    """

    def __init__(self):
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.last_scan_time: Optional[datetime] = None
        self.scan_count = 0

    async def start(self) -> None:
        """Start background worker - always starts regardless of settings"""
        if self.is_running:
            print("[BackgroundWorker] Already running")
            return

        self.is_running = True
        self.task = asyncio.create_task(self._run_scheduler())

        print(f"[BackgroundWorker] Started with {settings.ingestion.scan_interval_minutes}min interval")

    async def stop(self) -> None:
        """Stop background worker"""
        if not self.is_running:
            print("[BackgroundWorker] Not running")
            return

        self.is_running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        print("[BackgroundWorker] Stopped")

    async def _run_scheduler(self) -> None:
        """Main scheduler loop"""
        interval_seconds = settings.ingestion.scan_interval_minutes * 60

        print(f"[BackgroundWorker] Scheduler loop started (interval: {interval_seconds}s)")

        while self.is_running:
            try:
                await self._scan_and_process()
                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                print("[BackgroundWorker] Scheduler cancelled")
                break

            except Exception as e:
                print(f"[BackgroundWorker] Error in scheduler: {e}")
                await asyncio.sleep(60)

    async def _scan_and_process(self) -> None:
        """
        Scan pending directory and start ingestion if needed

        Processing is controlled ONLY by pipeline mode (runtime).
        .env setting is ignored during runtime.
        """
        self.last_scan_time = datetime.now(UTC)
        self.scan_count += 1

        print(f"[BackgroundWorker] Scan #{self.scan_count} at {self.last_scan_time.strftime('%H:%M:%S')}")

        # Check pipeline mode
        mode = ingestion_job_service.get_mode()
        if not ingestion_job_service.is_worker_allowed():
            print(f"[BackgroundWorker] Skipping - pipeline mode: {mode}")
            return

        print(f"[BackgroundWorker] Active - pipeline mode: {mode}")

        # Check if files exist
        pending_files = directory_manager.get_pending_files()

        if not pending_files:
            print("[BackgroundWorker] No pending files found")
            return

        print(f"[BackgroundWorker] Found {len(pending_files)} pending files, triggering ingestion")

        # Check if ingestion already running
        if ingestion_service.is_running:
            print("[BackgroundWorker] Ingestion already running, skipping")
            return

        # Start ingestion
        try:
            result = await ingestion_service.start_ingestion(immediate=True)

            if result['status'] == 'success':
                print(f"[BackgroundWorker] Ingestion started: {result.get('job_id')}")
            else:
                print(f"[BackgroundWorker] Ingestion failed: {result.get('message')}")

        except Exception as e:
            print(f"[BackgroundWorker] Failed to start ingestion: {e}")

    def get_status(self) -> dict:
        """Get worker status"""

        return {
            'is_running': self.is_running,
            'scan_count': self.scan_count,
            'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'scan_interval_minutes': settings.ingestion.scan_interval_minutes,
            'pipeline_mode': ingestion_job_service.get_mode(),
            'worker_allowed': ingestion_job_service.is_worker_allowed()
        }


# Singleton instance
background_worker = BackgroundWorker()