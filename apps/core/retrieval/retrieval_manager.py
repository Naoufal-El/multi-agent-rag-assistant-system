"""
Retrieval manager - combines embedding generation with vector search
Now supports dual collections
"""

from typing import List, Dict, Any
from apps.core.embeddings.embedding_client import embedding_client
from apps.core.vector_store.qdrant_client import qdrant_store
from apps.config.settings import settings

class RetrievalManager:
    """Manages document retrieval for RAG with dual collection support"""

    def __init__(self):
        self.top_k = settings.qdrant.retrieval_top_k
        self.enabled = settings.qdrant.retrieval_enabled

        print(f"[RetrievalManager] Initialized")
        print(f"[RetrievalManager] Top-K: {self.top_k}")
        print(f"[RetrievalManager] Enabled: {self.enabled}")

    def retrieve(self, query: str, collection_name: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Retrieve relevant documents for a query from a specific collection"""
        if not self.enabled:
            print("[RetrievalManager] Retrieval is disabled")
            return []

        k = top_k or self.top_k

        try:
            # Step 1: Generate query embedding
            print(f"[RetrievalManager] Retrieving from '{collection_name}' for: '{query[:50]}...'")
            query_embedding = embedding_client.generate_embedding(query)

            # Step 2: Search Qdrant
            results = qdrant_store.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                top_k=k,
                score_threshold=0.3  # Only return docs with >30% similarity
            )

            print(f"[RetrievalManager] Retrieved {len(results)} documents")
            return results

        except Exception as e:
            print(f"[RetrievalManager] ERROR during retrieval: {e}")
            return []

    @staticmethod
    def format_context(documents: List[Dict[str, Any]]) -> str:
        """Format retrieved documents into context string for LLM"""
        if not documents:
            return ""

        context_parts = []
        for i, doc in enumerate(documents, 1):
            # Format: [Document N] (score: X.XX)
            # Text content
            header = f"[Document {i}] (relevance: {doc['score']:.2f})"
            text = doc['text']
            context_parts.append(f"{header}\n{text}")

        context = "\n\n".join(context_parts)
        print(f"[RetrievalManager] Formatted {len(documents)} docs into context ({len(context)} chars)")
        return context

    def retrieve_and_format(self, query: str, collection_name: str, top_k: int = None) -> str:
        """Retrieve documents and format them into context"""
        documents = self.retrieve(query, collection_name, top_k)
        return self.format_context(documents)

# Global instance
retrieval_manager = RetrievalManager()