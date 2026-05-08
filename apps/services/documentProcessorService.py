"""
Document Processor Service
Handles embedding generation and vector indexing with DUAL-COLLECTION support
"""

from typing import List, Dict
import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor

from apps.config.settings import settings
from apps.core.embeddings.embedding_client import embedding_client
from apps.core.vector_store.qdrant_client import qdrant_store


class DocumentProcessorService:
    """
    Process document chunks for RAG with dual-collection routing

    Responsibilities:
    - Generate embeddings for text chunks
    - Route chunks to correct Qdrant collection (customer_kb or process_kb)
    - Index chunks in Qdrant vector database with duplicate prevention
    - Ensure collections exist
    - Handle batch processing
    """

    def __init__(self):
        self.collections_initialized = {}  # Track initialization per collection
        self.executor = ThreadPoolExecutor(max_workers=3)

    @staticmethod
    def generate_chunk_id(text: str, filename: str, chunk_index: int) -> str:
        """
        Generate deterministic UUID from chunk content

        Uses SHA256 hash converted to UUID format.
        Ensures same content produces same UUID for duplicate prevention.

        Args:
            text: Chunk text content
            filename: Source filename
            chunk_index: Index of chunk in document

        Returns:
            UUID string in standard format
        """
        import uuid

        # Create deterministic content string
        content = f"{filename}::{chunk_index}::{text}"

        # Generate SHA256 hash and convert to UUID
        hash_object = hashlib.sha256(content.encode('utf-8'))
        hash_bytes = hash_object.digest()

        # Convert first 16 bytes of hash to UUID
        chunk_uuid = str(uuid.UUID(bytes=hash_bytes[:16]))

        return chunk_uuid

    async def initialize_collection(self, collection_name: str) -> None:
        """
        Ensure Qdrant collection exists

        Args:
            collection_name: Name of collection to initialize (customer_kb or process_kb)

        Creates collection if it doesn't exist and settings allow it
        """
        if self.collections_initialized.get(collection_name):
            return

        if not settings.ingestion.create_collection_if_not_exists:
            print(f"[DocumentProcessor] Collection auto-creation disabled for {collection_name}")
            return

        try:
            # Check if collection exists
            collections = qdrant_store.client.get_collections()
            collection_exists = any(
                c.name == collection_name
                for c in collections.collections
            )

            if not collection_exists:
                print(f"[DocumentProcessor] Creating collection: {collection_name}")
                from qdrant_client.models import Distance, VectorParams

                qdrant_store.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=settings.qdrant.vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"[DocumentProcessor] Collection '{collection_name}' created successfully")
            else:
                print(f"[DocumentProcessor] Collection '{collection_name}' already exists")

            self.collections_initialized[collection_name] = True

        except Exception as e:
            print(f"[DocumentProcessor] Collection initialization failed for '{collection_name}': {e}")
            raise

    async def process_chunks(
            self,
            chunks: List[Dict],
            source_filename: str,
            target_collection: str  # ← NEW PARAMETER
    ) -> None:
        """
        Process chunks: generate embeddings and index in target Qdrant collection

        Uses content-based hash IDs to prevent duplicates.
        If the same file is processed again, chunks will be updated (upserted)
        instead of creating duplicates.

        Args:
            chunks: List of text chunks with metadata
            source_filename: Original filename for tracking
            target_collection: Collection to index into (customer_kb or process_kb)

        Raises:
            Exception if processing fails
        """
        # Ensure target collection exists
        await self.initialize_collection(target_collection)

        print(f"[DocumentProcessor] Processing {len(chunks)} chunks from {source_filename}")
        print(f"[DocumentProcessor] Target collection: {target_collection}")
        print(f"[DocumentProcessor] Using content-based IDs (duplicates will be replaced)")

        # Process chunks in batches to avoid overwhelming services
        batch_size = min(settings.ingestion.max_concurrent_files, 10)

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            # Process batch with target collection
            await self._process_batch(batch, source_filename, target_collection)

            print(f"[DocumentProcessor] Processed batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1}")

    async def _process_batch(
            self,
            batch: List[Dict],
            source_filename: str,
            target_collection: str  # ← NEW PARAMETER
    ) -> None:
        """
        Process a batch of chunks with duplicate prevention

        Uses deterministic IDs based on content hash.
        Qdrant's upsert operation will replace existing chunks with same ID.

        Args:
            batch: List of chunks to process
            source_filename: Original filename
            target_collection: Collection to index into
        """
        # Generate embeddings for all chunks in batch
        texts = [chunk['text'] for chunk in batch]

        try:
            # Generate embeddings using executor (since embedding_client is synchronous)
            loop = asyncio.get_event_loop()
            embedding_tasks = [
                loop.run_in_executor(self.executor, embedding_client.generate_embedding, text)
                for text in texts
            ]

            embeddings = await asyncio.gather(*embedding_tasks)

            # Prepare points for Qdrant
            from qdrant_client.models import PointStruct

            points = []
            for chunk, embedding in zip(batch, embeddings):
                # Generate deterministic ID from chunk content
                chunk_id = self.generate_chunk_id(
                    text=chunk['text'],
                    filename=source_filename,
                    chunk_index=chunk['index']
                )

                # Create serializable metadata (no nested lists/dicts)
                metadata = {
                    'filename': source_filename,
                    'chunk_index': chunk['index'],
                    'total_chunks': chunk['metadata'].get('total_chunks'),
                    'format': chunk['metadata'].get('format'),
                    'start_char': chunk.get('start_char'),
                    'end_char': chunk.get('end_char'),
                    'collection': target_collection,  # Add collection info to metadata
                }

                # Add source metadata if it's simple types
                source_meta = chunk['metadata'].get('source_metadata', {})
                if source_meta:
                    for key, value in source_meta.items():
                        # Only add simple serializable types
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            metadata[f'source_{key}'] = value

                point = PointStruct(
                    id=chunk_id,  # Deterministic hash ID (prevents duplicates)
                    vector=embedding,
                    payload={
                        'text': chunk['text'],
                        **metadata
                    }
                )
                points.append(point)

            # Upsert to TARGET COLLECTION
            qdrant_store.client.upsert(
                collection_name=target_collection,  # ← ROUTE TO CORRECT COLLECTION
                points=points
            )

            print(f"[DocumentProcessor] Indexed {len(points)} chunks to '{target_collection}' (duplicates auto-replaced)")

        except Exception as e:
            print(f"[DocumentProcessor] Batch processing failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def get_collection_info(self, collection_name: str) -> Dict:
        """
        Get information about specific Qdrant collection

        Args:
            collection_name: Name of collection to query

        Returns:
            Dict with collection statistics
        """
        return qdrant_store.get_collection_info(collection_name)


# Singleton instance
document_processor_service = DocumentProcessorService()