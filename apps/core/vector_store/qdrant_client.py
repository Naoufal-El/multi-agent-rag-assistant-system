from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from apps.config.settings import settings

class QdrantStore:
    """Qdrant vector database operations with dual collection support"""

    def __init__(self):
        self.url = settings.qdrant.url

        # NEW: Dual collections
        self.customer_collection = settings.qdrant.customer_collection
        self.process_collection = settings.qdrant.process_collection

        self.vector_size = settings.qdrant.vector_size

        print(f"[QdrantClient] Qdrant URL: {self.url}")
        print(f"[QdrantClient] Customer Collection: {self.customer_collection}")
        print(f"[QdrantClient] Employee Collection: {self.process_collection}")

        # Initialize Qdrant client
        self.client = QdrantClient(url=self.url)

    def create_collection(self, collection_name: str, recreate: bool = False) -> bool:
        """Create or recreate a Qdrant collection"""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]

            if collection_name in collection_names:
                if recreate:
                    print(f"[QdrantStore] Deleting existing collection: {collection_name}")
                    self.client.delete_collection(collection_name=collection_name)
                else:
                    print(f"[QdrantStore] Collection already exists: {collection_name}")
                    return True

            # Create new collection
            print(f"[QdrantStore] Creating collection: {collection_name}")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )

            print(f"[QdrantStore] Collection created successfully")
            return True

        except Exception as e:
            print(f"[QdrantStore] Error creating collection: {e}")
            return False

    def add_documents(self,
                      collection_name: str,
                      texts: List[str],
                      embeddings: List[List[float]],
                      metadata: Optional[List[Dict[str, Any]]] = None
                      ) -> bool:
        """Add documents to a specific collection"""
        try:
            if len(texts) != len(embeddings):
                raise ValueError("texts and embeddings must have same length")
            if metadata and len(metadata) != len(texts):
                raise ValueError("metadata must have same length as texts")

            # Create points for Qdrant
            points = []
            for i, (text, embedding) in enumerate(zip(texts, embeddings)):
                payload = {
                    "text": text,
                    "index": i
                }

                # Add metadata if provided
                if metadata:
                    payload.update(metadata[i])

                point = PointStruct(
                    id=i,
                    vector=embedding,
                    payload=payload
                )

                points.append(point)

            # Upload to Qdrant
            print(f"[QdrantStore] Uploading {len(points)} documents to {collection_name}...")
            self.client.upsert(
                collection_name=collection_name,
                points=points
            )

            print(f"[QdrantStore] {len(points)} documents added to {collection_name}")
            return True

        except Exception as e:
            print(f"[QdrantStore] ERROR adding documents: {e}")
            return False

    def search(
            self,
            collection_name: str,
            query_vector: List[float],
            top_k: int = 5,
            score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Search for similar documents in a specific collection"""
        try:
            # Use query_points instead of deprecated search
            search_result = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True  # Include document text and metadata
            )

            # Format results
            results = []
            for point in search_result.points:
                result = {
                    "text": point.payload.get("text", ""),
                    "score": point.score,
                    "metadata": {
                        k: v for k, v in point.payload.items()
                        if k not in ["text", "index"]
                    }
                }
                results.append(result)

            print(f"[QdrantStore] Found {len(results)} results in {collection_name}")
            return results

        except Exception as e:
            print(f"[QdrantStore] ERROR searching: {e}")
            return []

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a specific Qdrant collection

        Args:
            collection_name: Name of collection to query

        Returns:
            Dict with collection statistics or error info
        """
        try:
            info = self.client.get_collection(collection_name)

            return {
                'name': collection_name,
                'vectors_count': info.vectors_count,
                'indexed_vectors_count': info.indexed_vectors_count if hasattr(info, 'indexed_vectors_count') else None,
                'points_count': info.points_count,
                'status': str(info.status),
                'error': None
            }

        except Exception as e:
            print(f"[QdrantStore] ERROR getting collection info for {collection_name}: {e}")
            return {
                'name': collection_name,
                'error': str(e),
                'message': f'Collection {collection_name} may not exist or Qdrant unavailable',
                'vectors_count': None,
                'points_count': None,
                'status': 'error'
            }
# Global instance
qdrant_store = QdrantStore()