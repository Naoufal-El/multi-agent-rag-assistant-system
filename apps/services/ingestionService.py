"""
Ingestion Service
Orchestrates document ingestion pipeline with strict metadata validation
"""

from typing import List, Dict, Optional
from pathlib import Path
import asyncio
import json

from apps.config.settings import settings
from apps.utils.directory_manager import directory_manager
from apps.ingestion.document_loader import document_loader
from apps.ingestion.text_chunker import text_chunker
from apps.ingestion.job_tracker import job_tracker
from apps.services.documentProcessorService import document_processor_service


class IngestionService:
    """
    Main ingestion service orchestrator

    STRICT METADATA REQUIREMENT:
    - All files MUST have a .meta file with valid collection name
    - Files without metadata are REJECTED before processing starts
    """

    def __init__(self):
        self.is_running = False
        self.current_task: Optional[asyncio.Task] = None

    async def get_status(self) -> Dict:
        """Get current ingestion status"""
        job_status = job_tracker.get_status()
        pending_files = directory_manager.get_pending_files()

        return {
            **job_status,
            'pending_files_count': len(pending_files),
            'pending_files': [f.name for f in pending_files[:10]],
            'is_running': self.is_running
        }

    def _validate_metadata_file(self, file_path: Path) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Validate metadata file exists and has valid collection

        Args:
            file_path: Path to the main file

        Returns:
            Tuple of (is_valid, collection_name, error_message)
        """
        # Check for .meta file
        meta_path = file_path.with_suffix(file_path.suffix + ".meta")

        if not meta_path.exists():
            return (False, None, f"Missing metadata file: {meta_path.name}")

        try:
            with open(meta_path, "r") as f:
                metadata = json.load(f)

            collection = metadata.get("collection")

            if not collection:
                return (False, None, "Metadata file missing 'collection' field")

            # Validate collection name is one of the valid options
            valid_collections = [
                settings.qdrant.customer_collection,
                settings.qdrant.process_collection
            ]

            if collection not in valid_collections:
                return (False, None, f"Invalid collection '{collection}'. Must be one of: {valid_collections}")

            return (True, collection, None)

        except json.JSONDecodeError:
            return (False, None, "Metadata file is not valid JSON")
        except Exception as e:
            return (False, None, f"Error reading metadata: {str(e)}")

    def _validate_all_files_have_metadata(self, files: List[Path]) -> Dict:
        """
        Validate ALL files have valid metadata before starting job

        Returns:
            Dict with validation results
        """
        invalid_files = []

        for file_path in files:
            is_valid, collection, error = self._validate_metadata_file(file_path)

            if not is_valid:
                invalid_files.append({
                    'filename': file_path.name,
                    'error': error
                })

        if invalid_files:
            return {
                'status': 'invalid',
                'message': f'{len(invalid_files)} files missing or have invalid metadata',
                'invalid_files': invalid_files
            }

        return {'status': 'valid'}

    async def start_ingestion(self, immediate: bool = True) -> Dict:
        """
        Start document ingestion job

        STRICT VALIDATION: All files must have valid metadata before processing starts
        """
        # Check if job already running
        if self.is_running:
            return {
                'status': 'error',
                'message': 'Ingestion job already running',
                'current_job': job_tracker.get_status()
            }

        # Get pending files
        pending_files = directory_manager.get_pending_files()
        if not pending_files:
            return {
                'status': 'error',
                'message': 'No files in pending directory',
                'pending_dir': settings.ingestion.pending_dir
            }

        # STRICT VALIDATION: Check ALL files have valid metadata
        validation = self._validate_all_files_have_metadata(pending_files)

        if validation['status'] == 'invalid':
            return {
                'status': 'error',
                'message': validation['message'],
                'invalid_files': validation['invalid_files'],
                'action_required': 'Add valid .meta files to all files before ingestion'
            }

        # Create job
        job = job_tracker.create_job([f.name for f in pending_files])

        if immediate:
            # Start immediately
            self.current_task = asyncio.create_task(self._run_ingestion_job(pending_files))
            return {
                'status': 'started',
                'message': f'Ingestion job started with {len(pending_files)} files (all have valid metadata)',
                'job_id': job.job_id,
                'files_count': len(pending_files)
            }
        else:
            return {
                'status': 'scheduled',
                'message': f'Ingestion job scheduled with {len(pending_files)} files',
                'job_id': job.job_id,
                'files_count': len(pending_files)
            }

    async def cancel_ingestion(self) -> Dict:
        """Cancel running ingestion job"""
        if not self.is_running:
            return {
                'status': 'error',
                'message': 'No job running'
            }

        if self.current_task:
            self.current_task.cancel()

        job_tracker.cancel_job()
        self.is_running = False

        return {
            'status': 'cancelled',
            'message': 'Ingestion job cancelled'
        }

    async def _run_ingestion_job(self, files: List[Path]) -> None:
        """Run ingestion job for list of files"""
        self.is_running = True
        job_tracker.start_job()
        print(f"[IngestionService] Starting job with {len(files)} files")

        successful = 0
        failed = 0

        try:
            batch_size = settings.ingestion.batch_size
            for i in range(0, len(files), batch_size):
                batch = files[i:i + batch_size]

                tasks = [self._process_file(file_path) for file_path in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        failed += 1
                    elif result:
                        successful += 1
                    else:
                        failed += 1

            job_tracker.complete_job(success=True)
            print(f"[IngestionService] Job completed: {successful} successful, {failed} failed")

        except Exception as e:
            print(f"[IngestionService] Job failed: {e}")
            job_tracker.complete_job(success=False, error=str(e))
        finally:
            self.is_running = False

    async def _process_file(self, file_path: Path) -> bool:
        """Process single file through ingestion pipeline"""
        filename = file_path.name
        meta_filename = filename + ".meta"

        try:
            print(f"[IngestionService] Processing: {filename}")
            job_tracker.update_file_status(filename, "processing")

            # Step 1: Validate and read metadata (REQUIRED)
            is_valid, target_collection, error = self._validate_metadata_file(file_path)

            if not is_valid:
                raise ValueError(f"Metadata validation failed: {error}")

            print(f"[IngestionService] Target collection: {target_collection}")

            # Step 2: Validate file
            is_valid_file, error_msg = directory_manager.validate_file(file_path)
            if not is_valid_file:
                raise ValueError(f"File validation failed: {error_msg}")

            # Step 3: Move to processing directory
            processing_path = directory_manager.move_file(
                file_path,
                settings.ingestion.processing_dir
            )

            # Also move metadata file
            meta_path = file_path.with_suffix(file_path.suffix + ".meta")
            meta_processing_path = Path(settings.ingestion.processing_dir) / meta_filename
            meta_path.rename(meta_processing_path)

            # Step 4: Load document
            document = document_loader.load(processing_path)
            if not document['content'].strip():
                raise ValueError("Document has no content")

            # Step 5: Chunk text
            chunks = text_chunker.chunk(
                document['content'],
                metadata={
                    'filename': filename,
                    'format': document['format'],
                    'source_metadata': document['metadata']
                }
            )

            if not chunks:
                raise ValueError("No chunks created from document")

            # Step 6: Process chunks (embed and index) with target collection
            await document_processor_service.process_chunks(
                chunks,
                filename,
                target_collection=target_collection
            )

            # Step 7: Move to completed directory
            directory_manager.move_file(
                processing_path,
                settings.ingestion.completed_dir
            )

            # Also move metadata file
            meta_processing_path = Path(settings.ingestion.processing_dir) / meta_filename
            if meta_processing_path.exists():
                meta_completed_path = Path(settings.ingestion.completed_dir) / meta_filename
                meta_processing_path.rename(meta_completed_path)

            job_tracker.update_file_status(filename, "completed", chunks_created=len(chunks))
            print(f"[IngestionService] ✓ Completed: {filename} → {target_collection} ({len(chunks)} chunks)")
            return True

        except Exception as e:
            print(f"[IngestionService] ✗ Failed: {filename} - {str(e)}")

            # Move to failed directory
            try:
                failed_path = Path(settings.ingestion.processing_dir) / filename
                if failed_path.exists():
                    directory_manager.move_file(
                        failed_path,
                        settings.ingestion.failed_dir
                    )

                # Also move metadata file if exists
                meta_processing_path = Path(settings.ingestion.processing_dir) / meta_filename
                if meta_processing_path.exists():
                    meta_failed_path = Path(settings.ingestion.failed_dir) / meta_filename
                    meta_processing_path.rename(meta_failed_path)

            except Exception as move_error:
                print(f"[IngestionService] Could not move failed file: {move_error}")

            job_tracker.update_file_status(filename, "failed", error=str(e))
            return False

    def get_history(self) -> List[Dict]:
        """Get ingestion job history"""
        return job_tracker.get_history()


# Singleton instance
ingestion_service = IngestionService()