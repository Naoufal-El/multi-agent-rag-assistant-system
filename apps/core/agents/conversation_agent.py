"""
Conversation Agent - Employee General Chat (No RAG)
Handles casual conversation for EMPLOYEES ONLY without knowledge base retrieval
WITH MULTILINGUAL SUPPORT
"""

from apps.core.workflow.state import State, Msg
from apps.core.llm.ollama_client import ollama_client
from apps.config.settings import settings
from apps.prompts.conversation_prompts import SYSTEM_CONTEXT_PROMPT

def answer_conversationally(state: State) -> State:
    """Generate conversational response for EMPLOYEES (no RAG)"""

    messages = state.get("messages", [])
    user_type = state.get("user_type", "customer")

    print(f"[CONVERSATION_AGENT] Processing with {len(messages)} messages")
    print(f"[CONVERSATION_AGENT] User type: {user_type}")

    # Add system context if not present
    has_system_context = any(msg.get("role") == "system" for msg in messages)

    # Get last user message to detect language
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    if not has_system_context:
        # Employee-specific conversational context WITH MULTILINGUAL SUPPORT
        system_context: Msg = {
            "role": "system",
            "content": SYSTEM_CONTEXT_PROMPT.format(last_user_msg=last_user_msg)
        }
        messages.insert(0, system_context)

    if len(messages) == 1:  # Only system message
        greeting: Msg = {
            "role": "assistant",
            "content": "Hello! I'm here to chat. How's your day going?"
        }
        messages.append(greeting)
        state["messages"] = messages
        state["response_metadata"] = {
            "confidence": 0.5,
            "agent": "conversation",
            "retrieved_chunks": 0,
            "used_context": False
        }
        return state

    try:
        # Generate response with conversation temperature
        reply = ollama_client.generate_response(
            messages,
            temperature=settings.llm.conversation_temperature  # 0.7 for creative chat
        )

        assistant_msg: Msg = {
            "role": "assistant",
            "content": reply
        }
        messages.append(assistant_msg)

        state["response_metadata"] = {
            "confidence": 0.75,
            "agent": "conversation",
            "retrieved_chunks": 0,
            "used_context": False
        }

        print(f"[CONVERSATION_AGENT] Generated response ({len(reply)} chars)")

    except Exception as e:
        print(f"[CONVERSATION_AGENT] Error: {e}")

        error_msg: Msg = {
            "role": "assistant",
            "content": "I apologize, I'm having trouble right now. Please try again."
        }
        messages.append(error_msg)

        state["response_metadata"] = {
            "confidence": 0.2,
            "agent": "conversation",
            "retrieved_chunks": 0,
            "used_context": False,
            "error": str(e)
        }

    state["messages"] = messages
    return state