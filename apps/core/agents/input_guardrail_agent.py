"""
Input Guardrail Agent - Validates user input before processing
WITH EMPLOYEE SUPPORT - Relaxed validation for employees
"""

from apps.core.guardrails.input_guardrail import input_guardrail
from apps.core.workflow.state import State, Msg, InputGuardrailResult


# Greeting keywords (simple, fast check)
GREETING_KEYWORDS = [
    "hi", "hello", "hey", "greetings", "good morning", "good afternoon",
    "good evening", "howdy", "hiya", "sup", "what's up", "whats up", "ciao"
]


def validate_input(state: State) -> State:
    """Input guardrail node with employee-aware validation"""

    messages = state.get("messages", [])
    session_id = state.get("thread_id")
    user_type = state.get("user_type", "customer")

    # Get last user message
    last_user_msg = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    if last_user_msg is None:
        empty_result: InputGuardrailResult = {
            "passed": True,
            "layer1_passed": True,
            "layer2_passed": None,
            "blocked_reason": None,
            "layer1_checks": {},
            "layer2_score": None,
            "warnings": []
        }
        state["input_guardrail"] = empty_result
        return state

    print(f"[INPUT_GUARDRAIL] Validating query: '{last_user_msg[:60]}...'")
    print(f"[INPUT_GUARDRAIL] User type: {user_type}")

    # Check for greeting FIRST (bypass all guardrails)
    if _is_greeting(last_user_msg):
        print(f"[INPUT_GUARDRAIL] Detected GREETING - bypassing all checks")

        greeting_response = _get_greeting_response(user_type)
        greeting_msg: Msg = {
            "role": "assistant",
            "content": greeting_response
        }
        messages.append(greeting_msg)
        state["messages"] = messages
        state["route"] = "greeting"

        greeting_result: InputGuardrailResult = {
            "passed": True,
            "layer1_passed": True,
            "layer2_passed": True,
            "blocked_reason": None,
            "layer1_checks": {"greeting_detected": True},
            "layer2_score": None,
            "warnings": []
        }
        state["input_guardrail"] = greeting_result
        print(f"[INPUT_GUARDRAIL] GREETING handled - route set to 'greeting'")
        return state

    # Run validation (Layer 1 + Layer 2)
    # For employees: skip domain checks
    context = {}
    if user_type == "employee":
        context["skip_domain_check"] = True
        print("[INPUT_GUARDRAIL] Employee detected - skipping domain validation")

    result = input_guardrail.validate(last_user_msg, session_id, context=context)

    # Store in state
    state["input_guardrail"] = result

    # Handle result
    if not result["passed"]:
        reason = result["blocked_reason"]

        rejection_msg_content = _get_rejection_message(reason, user_type)
        rejection_msg: Msg = {
            "role": "assistant",
            "content": rejection_msg_content
        }
        messages.append(rejection_msg)
        state["messages"] = messages
        state["route"] = "blocked"

        print(f"[INPUT_GUARDRAIL] BLOCKED: {reason}")
    else:
        print(f"[INPUT_GUARDRAIL] PASSED")
        if result.get("warnings"):
            print(f"[INPUT_GUARDRAIL] Warnings: {result['warnings']}")

    return state


def _is_greeting(text: str) -> bool:
    """
    Check if text is EXACTLY a greeting (no additional content)

    Args:
        text: User input

    Returns:
        True if greeting detected (exact match only)
    """
    # Normalize text
    normalized = text.lower().strip()

    # Remove punctuation for matching
    normalized = normalized.strip(".,!?")

    # ONLY exact match - no partial matching
    return normalized in GREETING_KEYWORDS


def _get_greeting_response(user_type: str) -> str:
    """Generate appropriate greeting response based on user type"""
    if user_type == "employee":
        return (
            "Hello! 👋 I'm here to help you with internal processes support. What can I help you with today?\n"
            "• Internal HR policies and procedures\n"
            "• Company IT support and admin processes\n"
            "• Product information\n"
            "• Customer service best practices\n"
        )
    else:
        return (
            "Hello! 👋 Welcome to our electronics store support. What can I help you with today?\n"
            "• Product information and specifications\n"
            "• Pricing and availability\n"
            "• Orders, shipping, and tracking\n"
            "• Returns and exchanges\n"
            "• Technical support"
        )


def _get_rejection_message(reason: str, user_type: str) -> str:
    """Get appropriate rejection message"""

    exact_matches = {
        "Empty message not allowed": "Your message is empty. Please provide a question.",
        "Text too short": "Your message is too short. Please provide more details.",
        "Text too long": "Your message is too long. Please shorten it and try again.",
        "No meaningful text content": "Please provide a text-based question.",
        "rate_limit_exceeded_minute": "You're sending too many requests. Please wait a moment.",
        "rate_limit_exceeded_hour": "You've reached the hourly limit. Please try again later.",
        "repeated_query_spam": "You've asked this multiple times. Please wait for a response.",
    }

    if reason in exact_matches:
        return exact_matches[reason]

    # Safety-related
    if any(kw in reason.lower() for kw in ["toxic", "profanity", "inappropriate", "unsafe"]):
        return "I can't process that request. Please avoid anything inappropriate."

    # Default fallback
    return "I can only help with support questions, in what I can assist you today?"