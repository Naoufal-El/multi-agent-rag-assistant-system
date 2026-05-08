"""
Ingestion Controller
REST API endpoints for document ingestion management with dual-collection support
"""
from apps.middleware.auth_middleware import require_admin
from fastapi import Depends
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import List
from apps.ingestion.jobs.background_worker import background_worker
from apps.services.ingestionService import ingestion_service
from apps.services.ingestionJobService import ingestion_job_service
from apps.config.settings import settings
from apps.models.ingestion.enums import PipelineMode
from apps.models.dto.schemas import CollectionType
from apps.models.ingestion.response import (
    IngestionStatusResponse,
    UploadFilesResponse
)
from pathlib import Path
import shutil
import json

router = APIRouter(prefix="/ingestion")


# ============================================
# JOB MANAGEMENT (Core Operations)
# ============================================

@router.get("/status", response_model=IngestionStatusResponse, dependencies=[Depends(require_admin)])
async def get_status():
    """
    Get current ingestion job status

    Returns:
    - Job progress and statistics
    - Pending files count
    - Processing state
    """
    try:
        status = await ingestion_service.get_status()
        return IngestionStatusResponse(
            status=status.get('status', 'idle'),
            job_id=status.get('job_id'),
            progress=status.get('progress'),
            files_total=status.get('files_total'),
            files_processed=status.get('files_processed'),
            files_failed=status.get('files_failed'),
            chunks_total=status.get('chunks_total'),
            pending_files_count=status.get('pending_files_count', 0),
            is_running=status.get('is_running', False),
            message=f"{status.get('pending_files_count', 0)} files in pending directory"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start", dependencies=[Depends(require_admin)])
async def start_ingestion():
    """
    Start processing pending files

    Respects current pipeline mode:
    - AUTOMATIC/MANUAL: Processes immediately
    - PAUSED: Blocked (403 error)

    This is the ONLY manual trigger endpoint.
    """
    try:
        # Check permission
        allowed, reason = ingestion_job_service.is_ingestion_allowed()
        if not allowed:
            raise HTTPException(status_code=403, detail=reason)

        # Track manual trigger
        ingestion_job_service.manual_trigger_count += 1

        # Start ingestion
        result = await ingestion_service.start_ingestion(immediate=True)
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['message'])

        return {
            **result,
            'trigger_type': 'manual',
            'mode': ingestion_job_service.get_mode()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel", dependencies=[Depends(require_admin)])
async def cancel_job():
    """
    Cancel currently running job

    Only cancels current job - doesn't affect pipeline mode.
    """
    try:
        result = await ingestion_service.cancel_ingestion()
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['message'])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", dependencies=[Depends(require_admin)])
async def get_history():
    """Get ingestion job history"""
    try:
        history = ingestion_service.get_history()
        return {
            "status": "success",
            "jobs": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# FILE MANAGEMENT (NEW: Dual-Collection Support)
# ============================================

@router.post("/upload", response_model=UploadFilesResponse, dependencies=[Depends(require_admin)])
async def upload_files(
        files: List[UploadFile] = File(...),
        collection: CollectionType = Query(
            default=CollectionType.customer_kb,
            description="Target collection: customer_kb (products) or process_kb (HR/processes)"
        )
):
    """
    Upload files to pending directory with collection targeting

    Args:
        files: List of files to upload
        collection: Target collection (customer_kb or process_kb)

    Files are NOT automatically processed.
    Use /start to trigger processing.

    Metadata file (.meta) is created alongside each file to track target collection.
    """
    uploaded = []
    failed = []

    pending_dir = Path(settings.ingestion.pending_dir)
    pending_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        try:
            file_path = Path(file.filename)

            # Validate format
            if not settings.ingestion.is_supported_file(file.filename):
                failed.append(f"{file.filename} (unsupported format)")
                continue

            # Handle duplicates
            target_path = pending_dir / file.filename
            counter = 1
            while target_path.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                target_path = pending_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            # Save file
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # NEW: Save metadata file with collection info
            metadata_path = target_path.with_suffix(target_path.suffix + ".meta")
            with open(metadata_path, "w") as f:
                json.dump({"collection": collection.value}, f)

            uploaded.append(file.filename)
            print(f"[IngestionController] Uploaded {file.filename} → {collection.value}")

        except Exception as e:
            failed.append(f"{file.filename} ({str(e)})")

    return UploadFilesResponse(
        status="completed" if uploaded else "failed",
        message=f"Uploaded {len(uploaded)} files to {collection.value}, {len(failed)} failed",
        uploaded_files=uploaded,
        failed_files=failed,
        target_collection=collection.value
    )


@router.get("/files", dependencies=[Depends(require_admin)])
async def list_files():
    """List files in pending directory with collection info"""
    try:
        from apps.utils.directory_manager import directory_manager

        pending_files = directory_manager.get_pending_files()

        files_info = []
        for f in pending_files:
            # Read metadata to get collection
            meta_path = f.with_suffix(f.suffix + ".meta")
            collection = "customer_kb"  # default

            if meta_path.exists():
                try:
                    with open(meta_path, "r") as mf:
                        meta = json.load(mf)
                        collection = meta.get("collection", "customer_kb")
                except:
                    pass

            files_info.append({
                "filename": f.name,
                "size_mb": round(directory_manager.get_file_size_mb(f), 2),
                "extension": f.suffix,
                "target_collection": collection  # NEW
            })

        return {
            "status": "success",
            "count": len(files_info),
            "files": files_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# PIPELINE CONTROL (Simplified)
# ============================================

@router.get("/mode", dependencies=[Depends(require_admin)])
async def get_mode():
    """
    Get current pipeline mode and worker status

    Returns:
    - Current mode (AUTOMATIC/MANUAL/PAUSED)
    - Worker state
    - Permission status
    """
    try:
        return {
            'status': 'success',
            'mode': ingestion_job_service.get_mode(),
            'control': ingestion_job_service.get_status(),
            'worker': background_worker.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mode/{mode}", dependencies=[Depends(require_admin)])
async def set_mode(mode: str):
    """
    Set pipeline mode

    Modes:
    - automatic: Worker processes files every 30min
    - manual: Only /start triggers work
    - pause: Emergency stop - blocks ALL ingestion

    Examples:
    - POST /ingestion/mode/automatic
    - POST /ingestion/mode/manual
    - POST /ingestion/mode/pause
    """
    try:
        mode_map = {
            'automatic': PipelineMode.AUTOMATIC,
            'manual': PipelineMode.MANUAL,
            'pause': PipelineMode.PAUSED
        }

        if mode not in mode_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode. Use: {', '.join(mode_map.keys())}"
            )

        result = await ingestion_job_service.set_mode(mode_map[mode])

        messages = {
            'automatic': 'Automatic mode enabled - worker scans every 30min',
            'manual': 'Manual mode enabled - use /start to trigger',
            'pause': 'Pipeline paused - all ingestion blocked'
        }

        return {
            'status': 'success',
            'message': messages[mode],
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume", dependencies=[Depends(require_admin)])
async def resume():
    """
    Resume from PAUSED state

    Returns to AUTOMATIC mode.
    """
    try:
        result = await ingestion_job_service.resume()
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['message'])

        return {
            'status': 'success',
            'message': 'Pipeline resumed - automatic mode active',
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# WORKER CONTROL
# ============================================

@router.post("/worker/start", dependencies=[Depends(require_admin)])
async def start_worker():
    """
    Start background worker

    Starts the scheduler loop.
    Worker respects current pipeline mode and .env settings.
    """
    try:
        await background_worker.start()
        return {
            'status': 'success',
            'message': 'Background worker started',
            'worker': background_worker.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/worker/stop", dependencies=[Depends(require_admin)])
async def stop_worker():
    """
    Stop background worker

    Stops the scheduler loop.
    Manual ingestion via /start will still work.
    """
    try:
        await background_worker.stop()
        return {
            'status': 'success',
            'message': 'Background worker stopped',
            'worker': background_worker.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/worker/status", dependencies=[Depends(require_admin)])
async def get_worker_status():
    """Get background worker status"""
    try:
        return {
            'status': 'success',
            'worker': background_worker.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))