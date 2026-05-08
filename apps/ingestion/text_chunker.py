"""
Text Chunker
Splits text into overlapping chunks for embedding
"""
from typing import List, Dict
from apps.config.settings import settings


class TextChunker:
    """
    Split text into chunks with overlap for better context preservation

    Strategy:
    - Split by sentences (period + space)
    - Combine sentences until chunk_size reached
    - Add overlap from previous chunk
    - Preserve paragraph boundaries when possible
    """

    def __init__(
            self,
            chunk_size: int = None,
            chunk_overlap: int = None,
            min_chunk_size: int = None
    ):
        self.chunk_size = chunk_size or settings.ingestion.chunk_size
        self.chunk_overlap = chunk_overlap or settings.ingestion.chunk_overlap
        self.min_chunk_size = min_chunk_size or settings.ingestion.min_chunk_size

        print(f"[TextChunker] Initialized: size={self.chunk_size}, overlap={self.chunk_overlap}")

    def chunk(self, text: str, metadata: Dict = None) -> List[Dict]:
        """
        Split text into overlapping chunks

        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to each chunk

        Returns:
            List of chunk dicts:
            [
                {
                    'text': str,           # Chunk text
                    'index': int,          # Chunk index (0-based)
                    'start_char': int,     # Start position in original text
                    'end_char': int,       # End position in original text
                    'metadata': Dict,      # Original metadata + chunk info
                },
                ...
            ]
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            return []

        # Split into sentences
        sentences = self._split_sentences(text)

        chunks = []
        current_chunk = []
        current_length = 0
        char_position = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            # If adding this sentence exceeds chunk_size, save current chunk
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)

                chunks.append({
                    'text': chunk_text,
                    'index': len(chunks),
                    'start_char': char_position - current_length,
                    'end_char': char_position,
                    'metadata': {
                        **(metadata or {}),
                        'chunk_index': len(chunks),
                        'total_chunks': None,  # Will be updated later
                    }
                })

                # Keep overlap from previous chunk
                overlap_text = chunk_text[-self.chunk_overlap:] if len(chunk_text) > self.chunk_overlap else chunk_text
                overlap_sentences = overlap_text.split('. ')

                current_chunk = overlap_sentences
                current_length = len(overlap_text)

            current_chunk.append(sentence)
            current_length += sentence_length + 1  # +1 for space
            char_position += sentence_length + 1

        # Add remaining chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)

            if len(chunk_text) >= self.min_chunk_size:
                chunks.append({
                    'text': chunk_text,
                    'index': len(chunks),
                    'start_char': char_position - current_length,
                    'end_char': char_position,
                    'metadata': {
                        **(metadata or {}),
                        'chunk_index': len(chunks),
                        'total_chunks': None,
                    }
                })

        # Update total_chunks in metadata
        for chunk in chunks:
            chunk['metadata']['total_chunks'] = len(chunks)

        print(f"[TextChunker] Created {len(chunks)} chunks from {len(text)} chars")

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences

        Simple strategy: Split on ". " but keep the period with sentence
        More sophisticated: Could use nltk.sent_tokenize
        """
        # Replace common abbreviations to avoid splitting
        text = text.replace('Mr.', 'Mr').replace('Mrs.', 'Mrs').replace('Dr.', 'Dr')
        text = text.replace('etc.', 'etc').replace('e.g.', 'eg').replace('i.e.', 'ie')

        # Split on period followed by space and capital letter
        import re
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

        # Clean up sentences
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    def get_chunk_stats(self, chunks: List[Dict]) -> Dict:
        """Get statistics about chunks"""
        if not chunks:
            return {
                'total_chunks': 0,
                'avg_chunk_size': 0,
                'min_chunk_size': 0,
                'max_chunk_size': 0
            }

        chunk_sizes = [len(chunk['text']) for chunk in chunks]

        return {
            'total_chunks': len(chunks),
            'avg_chunk_size': sum(chunk_sizes) / len(chunk_sizes),
            'min_chunk_size': min(chunk_sizes),
            'max_chunk_size': max(chunk_sizes)
        }


# Singleton instance
text_chunker = TextChunker()