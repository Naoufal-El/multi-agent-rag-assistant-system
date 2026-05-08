"""
State management for the conversation graph
Extended with guardrail metadata
"""

from typing import TypedDict, Literal, Optional, List, Dict, Any

# Message type
class Msg(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str

# Route type
Route = Literal["rag", "conversation", "blocked", "greeting"]

# Input Guardrail Result
class InputGuardrailResult(TypedDict):
    passed: bool
    layer1_passed: bool # Format checks
    layer2_passed: Optional[bool] # LLM checks (None if not reached)
    blocked_reason: Optional[str]
    layer1_checks: Dict[str, Any] # Detailed check results
    layer2_score: Optional[float] # LLM appropriateness score
    warnings: List[str]

# Response Metadata (from agents)
class ResponseMetadata(TypedDict):
    agent: str # "cs_rag"
    confidence: float

    # RAG-specific
    retrieved_chunks: Optional[int]
    sources: Optional[List[str]]
    used_context: Optional[bool]

    # Conversational-specific (legacy)
    conversational_mode: Optional[bool]

# Output Guardrail Check Result
class GuardrailCheck(TypedDict):
    score: float
    passed: bool
    details: Optional[str]

# Output Guardrail Result
class OutputGuardrailResult(TypedDict):
    overall_score: float
    passed: bool
    decision: Literal["pass", "conditional", "fail"]
    checks: Dict[str, GuardrailCheck]
    failure_reason: Optional[str]
    suggested_action: Optional[str]
    retry_count: int

# Main State
class State(TypedDict):
    messages: List[Msg]
    thread_id: Optional[str]
    route: Optional[Route]
    route_confidence: Optional[float]
    route_reason: Optional[str]

    # NEW: User context
    user_type: Optional[str]  # "customer" or "employee"
    target_kb: Optional[str]  # "customer_kb" or "process_kb"

    # Guardrail metadata
    input_guardrail: Optional[InputGuardrailResult]
    response_metadata: Optional[ResponseMetadata]
    output_guardrail: Optional[OutputGuardrailResult]

    # Retry tracking
    regeneration_count: int

    # Session info (for rate limiting)
    session_id: Optional[str]