"""
Ingestion Control Service
Manages ingestion pipeline modes and permissions
"""
from apps.models.ingestion.enums import PipelineMode
from datetime import datetime, UTC
from typing import Tuple, Optional
from apps.config.settings import settings

class IngestionJobService:
    """
    Controls ingestion pipeline behavior

    Initial mode is set based on .env:
    - auto_scan_enabled=true → AUTOMATIC mode
    - auto_scan_enabled=false → MANUAL mode

    Mode can be changed at runtime via API.
    """

    def __init__(self):
        # Initialize mode based on .env setting
        if settings.ingestion.auto_scan_enabled:
            self.current_mode = PipelineMode.AUTOMATIC
            print("[IngestionControl] Initial mode: AUTOMATIC (from .env)")
        else:
            self.current_mode = PipelineMode.MANUAL
            print("[IngestionControl] Initial mode: MANUAL (from .env)")

        self.pause_reason: Optional[str] = None
        self.manual_trigger_count = 0
        self.mode_changed_at = datetime.now(UTC)

    def get_mode(self) -> PipelineMode:
        """Get current pipeline mode"""
        return self.current_mode

    async def set_mode(self, mode: PipelineMode) -> dict:
        """
        Set pipeline mode

        Args:
            mode: New pipeline mode

        Returns:
            Status dict with mode change info
        """
        old_mode = self.current_mode
        self.current_mode = mode
        self.mode_changed_at = datetime.now(UTC)

        if mode != PipelineMode.PAUSED:
            self.pause_reason = None

        print(f"[IngestionControl] Mode changed: {old_mode} → {mode}")

        return {
            'previous_mode': old_mode,
            'current_mode': mode,
            'changed_at': self.mode_changed_at.isoformat()
        }

    async def pause(self, reason: str = "Manual pause") -> dict:
        """
        Pause entire pipeline (emergency stop)

        Args:
            reason: Why the pipeline was paused
        """
        old_mode = self.current_mode
        self.current_mode = PipelineMode.PAUSED
        self.pause_reason = reason
        self.mode_changed_at = datetime.now(UTC)

        print(f"[IngestionControl] Pipeline PAUSED: {reason}")

        return {
            'status': 'success',
            'previous_mode': old_mode,
            'reason': reason,
            'paused_at': self.mode_changed_at.isoformat()
        }

    async def resume(self) -> dict:
        """Resume from PAUSED state (returns to AUTOMATIC)"""
        if self.current_mode != PipelineMode.PAUSED:
            return {
                'status': 'error',
                'message': f'Cannot resume - not paused (current mode: {self.current_mode})'
            }

        old_reason = self.pause_reason
        await self.set_mode(PipelineMode.AUTOMATIC)

        print(f"[IngestionControl] Pipeline RESUMED (was paused: {old_reason})")

        return {
            'status': 'success',
            'previous_reason': old_reason,
            'current_mode': PipelineMode.AUTOMATIC
        }

    def is_ingestion_allowed(self) -> Tuple[bool, str]:
        """
        Check if ingestion is allowed right now

        Returns:
            (allowed, reason)
        """
        if self.current_mode == PipelineMode.PAUSED:
            return False, f"Pipeline paused: {self.pause_reason}"

        return True, "Ingestion allowed"

    def is_worker_allowed(self) -> bool:
        """
        Check if background worker should process files

        Returns:
            True if worker should process, False otherwise
        """
        # Worker only processes in AUTOMATIC mode
        return self.current_mode == PipelineMode.AUTOMATIC

    def get_status(self) -> dict:
        """Get control service status"""
        allowed, reason = self.is_ingestion_allowed()

        return {
            'mode': self.current_mode,
            'ingestion_allowed': allowed,
            'worker_allowed': self.is_worker_allowed(),
            'pause_reason': self.pause_reason,
            'manual_trigger_count': self.manual_trigger_count,
            'mode_changed_at': self.mode_changed_at.isoformat(),
            'reason': reason
        }


# Singleton instance
ingestion_job_service = IngestionJobService()