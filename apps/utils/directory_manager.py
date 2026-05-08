"""
Directory Manager
Creates and manages ingestion directory structure
"""
from pathlib import Path
from typing import List
from apps.config.settings import settings


class DirectoryManager:
    """Manages ingestion directory structure"""

    @staticmethod
    def create_directories() -> None:
        """Create all required ingestion directories"""
        directories = settings.ingestion.get_all_dirs()

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"[DirectoryManager] Created/verified: {directory}")

    @staticmethod
    def get_pending_files() -> List[Path]:
        """Get all files in pending directory"""
        pending_dir = Path(settings.ingestion.pending_dir)

        if not pending_dir.exists():
            return []

        files = []
        for file_path in pending_dir.iterdir():
            if file_path.is_file() and settings.ingestion.is_supported_file(file_path.name):
                files.append(file_path)

        return files

    @staticmethod
    def move_file(source: Path, target_dir: str) -> Path:
        """Move file to target directory"""
        target_path = Path(target_dir) / source.name

        # Handle name conflicts
        counter = 1
        while target_path.exists():
            stem = source.stem
            suffix = source.suffix
            target_path = Path(target_dir) / f"{stem}_{counter}{suffix}"
            counter += 1

        source.rename(target_path)
        print(f"[DirectoryManager] Moved: {source.name} -> {target_path}")

        return target_path

    @staticmethod
    def get_file_size_mb(file_path: Path) -> float:
        """Get file size in megabytes"""
        return file_path.stat().st_size / (1024 * 1024)

    @staticmethod
    def validate_file(file_path: Path) -> tuple[bool, str]:
        """Validate file before processing"""

        # Check if file exists
        if not file_path.exists():
            return False, "File does not exist"

        # Check if it's a file (not directory)
        if not file_path.is_file():
            return False, "Path is not a file"

        # Check file extension
        if not settings.ingestion.is_supported_file(file_path.name):
            supported = settings.ingestion.get_extensions_list()
            return False, f"Unsupported format. Supported: {', '.join(supported)}"

        # Check file size
        size_mb = DirectoryManager.get_file_size_mb(file_path)
        max_size = settings.ingestion.max_file_size_mb

        if size_mb > max_size:
            return False, f"File too large: {size_mb:.2f}MB (max: {max_size}MB)"

        # Check if file is readable
        try:
            with open(file_path, 'rb') as f:
                f.read(1)
        except Exception as e:
            return False, f"Cannot read file: {str(e)}"

        return True, "Valid"


# Singleton instance
directory_manager = DirectoryManager()