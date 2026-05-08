"""
Orchestrator Agent - Routes user queries AND selects KB collection
IMPROVED: Deterministic routing with keyword detection + LLM fallback + MEMORY AWARENESS
"""
from apps.config import settings
from apps.core.workflow.state import State
from apps.core.llm.ollama_client import ollama_client
from apps.prompts.orchestration_prompts import ROUTING_PROMPT

# ========================================
# Added memory/conversation keywords
# ========================================
CONVERSATION_KEYWORDS = [
    "hello", "hi", "hey", "thanks", "thank you", "bye", "goodbye",
    "how are you", "what's up", "whats up", "good morning", "good afternoon",
    "tell me a joke", "joke", "story", "chat", "talk",
    # Memory/conversation history keywords
    "my name", "what's my name", "whats my name", "who am i", "who i am",
    "remember", "you said", "earlier", "before", "previous", "last time",
    "our conversation", "we talked", "you mentioned", "i told you",
    "do you remember", "recall", "what did i say"
]

PROCESS_KB_KEYWORDS = [
    "vacation", "leave", "time off", "pto", "holiday",
    "expense", "reimbursement", "receipt", "claim",
    "it ticket", "support ticket", "helpdesk", "password", "reset",
    "hr", "human resources", "policy", "benefit", "insurance",
    "payroll", "salary", "onboarding", "offboarding"
]

CUSTOMER_KB_KEYWORDS = [
    "product", "feature", "specification", "spec", "price", "pricing",
    "warranty", "return", "refund", "customer", "client",
    "electronics", "laptop", "phone", "tablet", "tv", "camera"
]


def decide_route(state: State) -> State:
    """
    Route query to appropriate agent + select KB collection

    THREE-STEP ROUTING:
    1. Keyword-based detection (fast, deterministic)
    2. LLM classification (fallback)
    3. Confidence adjustment
    """

    messages = state.get("messages", [])
    user_type = state.get("user_type", "customer")

    print(f"[ORCHESTRATOR] Starting routing logic")
    print(f"[ORCHESTRATOR] User type: {user_type}")

    # Get last user message
    last_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_message = msg.get("content", "")
            break

    if not last_message:
        # Fallback if no user message
        state["route"] = "rag"
        state["target_kb"] = "customer_kb" if user_type == "customer" else "process_kb"
        state["routing_confidence"] = 0.5
        return state

    print(f"[ORCHESTRATOR] {user_type.capitalize()} query: '{last_message[:50]}...'")

    # ========================================
    # CUSTOMER ROUTING (Simple: always rag → customer_kb)
    # ========================================
    if user_type == "customer":
        print(f"[ORCHESTRATOR] Customer detected → route=rag, target_kb=customer_kb")
        state["route"] = "rag"
        state["target_kb"] = "customer_kb"
        state["routing_confidence"] = 0.9
        return state

    # ========================================
    # EMPLOYEE ROUTING (Complex: conversation vs rag)
    # ========================================

    # Step 1: Keyword-based detection (FAST - 0ms)
    normalized_query = last_message.lower().strip()

    # Check CONVERSATION keywords (including MEMORY)
    if any(keyword in normalized_query for keyword in CONVERSATION_KEYWORDS):
        print(f"[ORCHESTRATOR] Keyword match → conversation (memory/chat)")
        state["route"] = "conversation"
        state["target_kb"] = None  # No KB needed
        state["routing_confidence"] = 0.95
        return state

    # Check PROCESS_KB keywords
    if any(keyword in normalized_query for keyword in PROCESS_KB_KEYWORDS):
        print(f"[ORCHESTRATOR] Keyword match → rag with process_kb")
        state["route"] = "rag"
        state["target_kb"] = "process_kb"
        state["routing_confidence"] = 0.9
        return state

    # Check CUSTOMER_KB keywords
    if any(keyword in normalized_query for keyword in CUSTOMER_KB_KEYWORDS):
        print(f"[ORCHESTRATOR] Keyword match → rag with customer_kb")
        state["route"] = "rag"
        state["target_kb"] = "customer_kb"
        state["routing_confidence"] = 0.9
        return state

    # ========================================
    # Step 2: LLM-based classification (FALLBACK)
    # ========================================
    print(f"[ORCHESTRATOR] No keyword match - using LLM classification")

    # Clearer prompt with memory awareness
    prompt = ROUTING_PROMPT(query= last_message)

    try:
        llm_response = ollama_client.generate_response(
            [{"role": "user", "content": prompt}],
            temperature=settings.llm.routing_temperature  # Low temp for consistent routing
        ).strip().lower()

        print(f"[ORCHESTRATOR] LLM response: '{llm_response}'")

        # Parse LLM response
        if "conversation" in llm_response:
            route = "conversation"
            target_kb = None
            confidence = 0.75
        elif "rag" in llm_response:
            route = "rag"
            if "process" in llm_response:
                target_kb = "process_kb"
            elif "customer" in llm_response:
                target_kb = "customer_kb"
            else:
                # Default to process_kb for employees
                target_kb = "process_kb"
            confidence = 0.75
        else:
            # Fallback if LLM gives unexpected response
            print(f"[ORCHESTRATOR] Unexpected LLM response, defaulting to conversation")
            route = "conversation"
            target_kb = None
            confidence = 0.5

        print(f"[ORCHESTRATOR] LLM → route={route}, target_kb={target_kb}")

    except Exception as e:
        print(f"[ORCHESTRATOR] LLM routing error: {e}, defaulting to rag+process_kb")
        route = "rag"
        target_kb = "process_kb"
        confidence = 0.5

    # ========================================
    # Step 3: Set state and return
    # ========================================
    state["route"] = route
    state["target_kb"] = target_kb
    state["routing_confidence"] = confidence

    print(f"[ORCHESTRATOR] Final decision:")
    print(f"[ORCHESTRATOR]   route = {route}")
    print(f"[ORCHESTRATOR]   target_kb = {target_kb}")
    print(f"[ORCHESTRATOR]   confidence = {confidence}")

    return state