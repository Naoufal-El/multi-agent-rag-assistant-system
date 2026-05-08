"""
Output Guardrail Agent - LangGraph Integration
Validates responses before sending to users (Step 3 - Guardrails Phase)
"""
from apps.config import settings
from apps.core.workflow.state import State
from apps.core.guardrails.output_guardrail import output_guardrail


def validate_output(state: State) -> State:
    """
    LangGraph node for output validation

    Validates the generated response and decides:
    - pass: Send to user
    - conditional: Add disclaimer and send
    - regenerate: Try again (up to max attempts)
    - fail: Send fallback message
    """
    messages = state.get("messages", [])
    response_metadata = state.get("response_metadata", {})
    retrieved_docs = state.get("retrieved_docs", [])

    # Get the last assistant message (the response to validate)
    last_response = None
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            last_response = msg.get("content", "")
            break

    if not last_response:
        print("[OUTPUT_GUARDRAIL] No response found to validate")
        state["output_guardrail"] = {
            "overall_score": 0.0,
            "passed": False,
            "decision": "fail",
            "checks": {},
            "issues": ["No response generated"]
        }
        return state

    print(f"[OUTPUT_GUARDRAIL] Validating response: '{last_response[:60]}...'")

    # Run validation
    validation_result = output_guardrail.validate(
        response=last_response,
        response_metadata=response_metadata,
        retrieved_context=retrieved_docs if retrieved_docs else None
    )

    # Store validation result in state
    state["output_guardrail"] = validation_result

    decision = validation_result.get("decision", "pass")
    score = validation_result.get("overall_score", 0.0)

    print(f"[OUTPUT_GUARDRAIL] Decision: {decision} | Score: {score:.2f}")

    # Handle decision
    if decision == "pass":
        print("[OUTPUT_GUARDRAIL] Response PASSED validation")

    elif decision == "conditional":
        # Add disclaimer to response
        disclaimer = "\n\n(Note: This information may be incomplete. Please verify important details.)"
        messages[-1]["content"] = last_response + disclaimer
        state["messages"] = messages
        print("[OUTPUT_GUARDRAIL] Response PASSED with disclaimer")

    elif decision == "regenerate":
        # Check retry count
        retry_count = state.get("retry_count", 0)
        max_retries = settings.llm.max_regeneration_attempts

        if retry_count < max_retries:
            # Increment retry counter
            state["retry_count"] = retry_count + 1

            # Remove the bad response
            messages.pop()
            state["messages"] = messages

            print(f"[OUTPUT_GUARDRAIL] Triggering regeneration (attempt {retry_count + 1}/{max_retries})")

            # Add retry instructions to state for orchestrator
            state["retry_reason"] = validation_result.get("issues", ["Quality too low"])[0]
        else:
            # Max retries reached - use fallback
            print(f"[OUTPUT_GUARDRAIL] Max retries ({max_retries}) reached - using fallback")

            fallback_msg = "I apologize, but I'm having difficulty providing a quality response. Could you rephrase your question or ask something else?"
            messages[-1]["content"] = fallback_msg
            state["messages"] = messages
            state["output_guardrail"]["decision"] = "fail"

    elif decision == "fail":
        # Replace with fallback message
        fallback_msg = "I apologize, but I'm unable to provide a proper response right now. Please try rephrasing your question."
        messages[-1]["content"] = fallback_msg
        state["messages"] = messages
        print("[OUTPUT_GUARDRAIL] Response FAILED - using fallback")

    return state