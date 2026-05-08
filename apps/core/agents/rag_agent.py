"""
Customer Service RAG Agent - Universal (Customer + Employee Support)
Handles questions requiring knowledge base retrieval with dynamic collection selection
WITH MULTILINGUAL SUPPORT + MEMORY-AWARE FALLBACK
"""

from apps.core.workflow.state import State, Msg
from apps.core.llm.ollama_client import ollama_client
from apps.core.retrieval.retrieval_manager import retrieval_manager
from apps.config.settings import settings
from apps.prompts.rag_prompts import (
    CUSTOMER_RAG_PROMPT,
    EMPLOYEE_RAG_PROMPT,
    EMPLOYEE_FALLBACK_RAG_PROMPT,
    CUSTOMER_FALLBACK_RAG_PROMPT
)

def answer_with_rag(state: State) -> State:
    """Generate response using RAG with dynamic KB selection"""

    messages = state.get("messages", [])
    user_type = state.get("user_type", "customer")
    target_kb = state.get("target_kb")

    print(f"[RAG_AGENT] Processing with {len(messages)} messages")
    print(f"[RAG_AGENT] User type: {user_type}")
    print(f"[RAG_AGENT] Target KB: {target_kb}")

    if not messages:
        greeting: Msg = {
            "role": "assistant",
            "content": "Hello! How can I help you today?"
        }
        messages.append(greeting)
        state["messages"] = messages
        state["response_metadata"] = {
            "confidence": 0.5,
            "agent": "rag_agent",
            "retrieved_chunks": 0,
            "used_context": False
        }
        return state

    # Validate target_kb
    if not target_kb:
        print("[RAG_AGENT] ERROR: target_kb not set in state")
        error_msg: Msg = {
            "role": "assistant",
            "content": "I apologize, I'm having trouble processing your request. Please try again."
        }
        messages.append(error_msg)
        state["messages"] = messages
        state["response_metadata"] = {
            "confidence": 0.2,
            "agent": "rag_agent",
            "retrieved_chunks": 0,
            "used_context": False,
            "error": "target_kb not set"
        }
        return state

    try:
        # Get the latest user question
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break

        if not last_user_msg:
            raise ValueError("No user message found")

        print(f"[RAG_AGENT] User question: '{last_user_msg[:50]}...'")

        # Retrieve from specific collection
        retrieved_docs = retrieval_manager.retrieve(
            query=last_user_msg,
            collection_name=target_kb,
            top_k=5
        )

        # Save for output guardrail
        state["retrieved_docs"] = retrieved_docs

        #  Memory-aware fallback when no docs found
        if not retrieved_docs:
            print("[RAG_AGENT] No relevant docs found, using conversational response WITH HISTORY")

            # ADD SYSTEM PROMPT WITH MEMORY INSTRUCTION
            conversational_messages = messages.copy()
            memory_system_prompt = _build_memory_fallback_prompt(user_type)
            conversational_messages.insert(0, {
                "role": "system",
                "content": memory_system_prompt
            })

            reply = ollama_client.generate_response(
                conversational_messages,
                temperature=settings.llm.conversation_temperature
            )

            state["response_metadata"] = {
                "confidence": 0.6,
                "agent": "rag_agent",
                "retrieved_chunks": 0,
                "used_context": False,
                "used_history": True
            }

        else:
            # Format context
            context = retrieval_manager.format_context(retrieved_docs)
            print(f"[RAG_AGENT] Using {len(retrieved_docs)} documents as context")

            # Build RAG prompt with MULTILINGUAL instruction
            rag_messages = messages.copy()
            system_prompt = _build_system_prompt(user_type, context)
            rag_messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })

            # Generate answer with LOWER temperature for factual accuracy
            reply = ollama_client.generate_response(
                rag_messages,
                temperature=settings.llm.rag_temperature  # ← USE RAG TEMPERATURE (0.3)
            )

            state["response_metadata"] = {
                "confidence": 0.85,
                "agent": "rag_agent",
                "retrieved_chunks": len(retrieved_docs),
                "used_context": True,
                "used_history": False
            }

        # Add response
        assistant_msg: Msg = {
            "role": "assistant",
            "content": reply
        }
        messages.append(assistant_msg)

        print(f"[RAG_AGENT] Generated response ({len(reply)} chars)")
        print(f"[RAG_AGENT] Success | Confidence: {state['response_metadata']['confidence']}")

    except Exception as e:
        print(f"[RAG_AGENT] Error: {e}")

        # User-type-specific error message
        if user_type == "employee":
            error_content = "I apologize, I'm having trouble accessing our internal documentation. Could you rephrase your question?"
        else:
            error_content = "I apologize, I'm having trouble accessing our product information. Could you rephrase your question about our electronics?"

        error_msg: Msg = {
            "role": "assistant",
            "content": error_content
        }
        messages.append(error_msg)

        state["response_metadata"] = {
            "confidence": 0.2,
            "agent": "rag_agent",
            "retrieved_chunks": 0,
            "used_context": False,
            "error": str(e)
        }

    state["messages"] = messages
    return state


# ========================================
# Memory-aware fallback prompt
# ========================================
def _build_memory_fallback_prompt(user_type: str) -> str:
    """
    Build system prompt for when NO documents are retrieved
    This prompt emphasizes using conversation history

    Args:
        user_type: "customer" or "employee"

    Returns:
        System prompt for memory-based responses
    """
    if user_type == "employee":
        return EMPLOYEE_FALLBACK_RAG_PROMPT

    else:  # customer
        return CUSTOMER_FALLBACK_RAG_PROMPT


def _build_system_prompt(user_type: str, context: str) -> str:
    """
    Build appropriate system prompt based on user type WITH MULTILINGUAL SUPPORT

    Args:
        user_type: "customer" or "employee"
        context: Retrieved knowledge base context

    Returns:
        Formatted system prompt
    """

    if user_type == "employee":
        return EMPLOYEE_RAG_PROMPT(context=context)

    else:  # customer
        return CUSTOMER_RAG_PROMPT(context=context)