"""
Test script for Phase 2 document loaders
Place test documents in data/pending/ directory
"""
import asyncio
from pathlib import Path
from apps.ingestion.document_loader import document_loader
from apps.ingestion.text_chunker import text_chunker
from apps.utils.directory_manager import directory_manager


async def test_loaders():
    """Test all document loaders"""

    print("=" * 60)
    print("PHASE 2 TESTING: Document Loaders and Text Chunker")
    print("=" * 60)

    # Create directories
    print("\n1. Creating directories...")
    directory_manager.create_directories()

    # Get pending files
    print("\n2. Scanning pending directory...")
    pending_files = directory_manager.get_pending_files()

    if not pending_files:
        print(" No files found in data/pending/")
        print(" Please add test files to data/pending/ directory")
        return

    print(f"   ✓ Found {len(pending_files)} files")
    for file in pending_files:
        print(f"     - {file.name}")

    # Test each file
    print("\n3. Testing document loaders...")

    for file_path in pending_files:
        print(f"\n   Testing: {file_path.name}")
        print(f"   {'─' * 50}")

        try:
            # Validate file
            is_valid, msg = directory_manager.validate_file(file_path)
            print(f"   Validation: {'Ok' if is_valid else 'Failed'} {msg}")

            if not is_valid:
                continue

            # Load document
            result = document_loader.load(file_path)

            print(f"   Format: {result['format']}")
            print(f"   Size: {result['size_bytes']:,} bytes")
            print(f"   Content length: {len(result['content']):,} characters")
            print(f"   Metadata: {result['metadata']}")

            # Show content preview
            preview = result['content'][:200].replace('\n', ' ')
            print(f"   Preview: {preview}...")

            # Test chunking
            print(f"\n   Testing text chunker...")
            chunks = text_chunker.chunk(
                result['content'],
                metadata={'filename': result['filename'], 'format': result['format']}
            )

            print(f"   Chunks created: {len(chunks)}")

            if chunks:
                stats = text_chunker.get_chunk_stats(chunks)
                print(f"   Avg chunk size: {stats['avg_chunk_size']:.0f} chars")
                print(f"   Min chunk size: {stats['min_chunk_size']} chars")
                print(f"   Max chunk size: {stats['max_chunk_size']} chars")

                # Show first chunk
                print(f"\n   First chunk preview:")
                first_chunk = chunks[0]['text'][:150].replace('\n', ' ')
                print(f"   {first_chunk}...")

            print(f" Successfully processed {file_path.name}")

        except Exception as e:
            print(f" Error: {str(e)}")

    async def test_file_movement():
        """Test directory manager file movement functionality"""

    print("\n" + "=" * 60)
    print("TESTING FILE MOVEMENT FUNCTIONALITY")
    print("=" * 60)

    from apps.config.settings import settings

    # Get pending files
    pending_files = directory_manager.get_pending_files()

    if not pending_files:
        print("\n No files in pending directory to test movement")
        return

    # Take first file for testing
    test_file = pending_files[0]
    print(f"\n1. Testing with file: {test_file.name}")

    # Test 1: Move to processing
    print(f"\n2. Moving to processing directory...")
    try:
        processing_path = directory_manager.move_file(
            test_file,
            settings.ingestion.processing_dir
        )
        print(f" Moved to: {processing_path}")
        print(f" File exists: {processing_path.exists()}")
    except Exception as e:
        print(f" Error: {e}")
        return

    # Test 2: Move to completed
    print(f"\n3. Moving to completed directory...")
    try:
        completed_path = directory_manager.move_file(
            processing_path,
            settings.ingestion.completed_dir
        )
        print(f" Moved to: {completed_path}")
        print(f" File exists: {completed_path.exists()}")
    except Exception as e:
        print(f" Error: {e}")
        return

    # Test 3: Test duplicate handling (move back to pending)
    # print(f"\n4. Testing duplicate name handling...")

    # # Create another file with same name in pending
    # import shutil
    # duplicate_source = completed_path
    # duplicate_target = Path(settings.ingestion.pending_dir) / completed_path.name
    #
    # # Copy file back to create duplicate scenario
    # shutil.copy(duplicate_source, duplicate_target)
    # print(f"   Created duplicate: {duplicate_target.name}")
    #
    # try:
    #     # Try to move again (should handle duplicate)
    #     final_path = directory_manager.move_file(
    #         duplicate_source,
    #         settings.ingestion.pending_dir
    #     )
    #     print(f" Handled duplicate, renamed to: {final_path.name}")
    #     print(f" Original file intact: {duplicate_target.exists()}")
    #     print(f" New file created: {final_path.exists()}")
    # except Exception as e:
    #     print(f" Error: {e}")

    # Test 4: Check all directories
    print(f"\n5. Directory status:")
    for dir_path in settings.ingestion.get_all_dirs():
        files_in_dir = list(Path(dir_path).glob("*")) if Path(dir_path).exists() else []
        print(f"   {dir_path}: {len(files_in_dir)} files")
        for f in files_in_dir[:3]:  # Show first 3
            print(f"     - {f.name}")

    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_loaders())