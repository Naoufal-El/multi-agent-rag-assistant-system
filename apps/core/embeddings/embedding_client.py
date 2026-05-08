"""
Embedding client using Ollama's nomic-embed-text model
Converts text into vector representations for semantic search
"""
from typing import List
from ollama import Client
from apps.config.settings import settings

class EmbeddingClient:
    """Generate embeddings using Ollama's nomic-embed-text model"""

    def __init__(self):
        self.ollama_url = settings.llm.url
        self.model = settings.llm.embedding_model
        self.client = Client(host=self.ollama_url)
        print(f"[EmbeddingClient] Initialized with model: {self.model}")

    def generate_embedding(self, text:str) -> List[float]:
        """Generate embedding for a single text string"""
        try:
            response = self.client.embeddings(
                model=self.model,
                prompt=text
            )
            # Extract embedding vector
            embedding = response['embedding']
            print(f"[EmbeddingClient] Generated embedding: {len(embedding)} dimensions")
            return embedding

        except Exception as e:
            print(f"[EmbeddingClient] Error generating embedding: {e}")
            raise

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of text strings"""
        embeddings = []
        print(f"[EmbeddingClient] Generating embeddings for {len(texts)} texts...")
        for i, text in enumerate(texts):
            try:
                embedding = self.generate_embedding(text)
                embeddings.append(embedding)

                if (i + 1) % 10 == 0:  # Progress logging
                    print(f"[EmbeddingClient] Progress: {i + 1}/{len(texts)}")

            except Exception as e:
                print(f"[EmbeddingClient] Failed on text {i}: {e}")
                # Return zero vector as fallback
                embeddings.append([0.0] * 768)
        print(f"[EmbeddingClient] Batch complete: {len(embeddings)} embeddings")
        return embeddings

# Global instance
embedding_client = EmbeddingClient()