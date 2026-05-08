"""Test the complete RAG agent"""
from apps.core.embeddings.embedding_client import embedding_client
from apps.core.vector_store.qdrant_client import qdrant_store
from apps.core.agents.rag_agent import answer_with_rag

def setup_test_knowledge_base():
    """Create test knowledge base"""
    print("\n=== Setting up test knowledge base ===")

    # Create collection
    qdrant_store.create_collection(recreate=True)

    # Sample knowledge base documents
    docs = [
        "Our refund policy: We offer a full 30-day money-back guarantee on all products. No questions asked.",
        "Shipping information: Standard shipping takes 3-5 business days. Express shipping is available for $15 extra.",
        "Customer support: Our support team is available 24/7 via email at support@example.com or live chat.",
        "Product warranty: All products come with a 1-year manufacturer warranty covering defects.",
        "Return process: To return an item, contact support within 30 days and we'll send you a prepaid shipping label."
    ]

    # Generate embeddings and index
    print(f"Indexing {len(docs)} documents...")
    embeddings = embedding_client.generate_embeddings_batch(docs)
    qdrant_store.add_documents(docs, embeddings)

    print("Knowledge base ready\n")

def test_rag_agent():
    """Test RAG agent with different questions"""
    print("=== Testing RAG Agent ===\n")

    test_questions = [
        "What's your refund policy?",
        "How long does shipping take?",
        "Do you offer a warranty?"
    ]

    for question in test_questions:
        print(f"Question: {question}")
        print("-" * 60)

        # Create state
        state = {
            "messages": [
                {"role": "user", "content": question}
            ],
            "route": "cs_rag"
        }

        # Run RAG agent
        result = answer_with_rag(state)

        # Extract answer
        answer = result["messages"][-1]["content"]
        print(f"Answer: {answer}\n")
        print("=" * 60)
        print()

if __name__ == "__main__":
    setup_test_knowledge_base()
    test_rag_agent()
    print("🎉 RAG Agent test complete!")