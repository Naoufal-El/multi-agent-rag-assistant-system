"""
LangGraph Workflow - Main conversation flow WITH REGENERATION SUPPORT
"""

from langgraph.graph import StateGraph, START, END
from apps.core.workflow.state import State
from apps.core.agents.input_guardrail_agent import validate_input
from apps.core.agents.orchestrator_agent import decide_route
from apps.core.agents.rag_agent import answer_with_rag
from apps.core.agents.conversation_agent import answer_conversationally
from apps.core.agents.output_guardrail_agent import validate_output
from apps.config.settings import settings

def build_graph():
    """Build the LangGraph workflow with guardrails AND regeneration support"""

    g = StateGraph(State)

    # Add nodes
    g.add_node("input_guardrail", validate_input)
    g.add_node("orchestrator", decide_route)
    g.add_node("rag", answer_with_rag)
    g.add_node("conversation", answer_conversationally)
    g.add_node("output_guardrail", validate_output)

    # Entry point
    g.add_edge(START, "input_guardrail")

    # ========================================
    # INPUT GUARDRAIL ROUTING
    # ========================================
    def route_after_input_guardrail(state: State) -> str:
        """Route based on input guardrail result"""
        route = state.get("route")
        if route == "greeting":
            print(f"[GRAPH] Greeting detected - skipping workflow")
            return "end"
        elif route == "blocked":
            print(f"[GRAPH] Input blocked - ending workflow")
            return "end"
        else:
            print(f"[GRAPH] Input passed - routing to orchestrator")
            return "orchestrator"

    g.add_conditional_edges(
        "input_guardrail",
        route_after_input_guardrail,
        {
            "orchestrator": "orchestrator",
            "end": END
        }
    )

    # ========================================
    # ORCHESTRATOR ROUTING (rag vs conversation)
    # ========================================
    def route_after_orchestrator(state: State) -> str:
        """Route to appropriate agent based on orchestrator decision"""
        route = state.get("route", "rag")
        print(f"[GRAPH] Orchestrator routing to: {route}")
        return route

    g.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "rag": "rag",
            "conversation": "conversation",
        }
    )

    # ========================================
    # AGENTS → OUTPUT GUARDRAIL
    # ========================================
    g.add_edge("rag", "output_guardrail")
    g.add_edge("conversation", "output_guardrail")

    # ========================================
    # ✅ FIX: OUTPUT GUARDRAIL WITH REGENERATION LOOP
    # ========================================
    def route_after_output_guardrail(state: State) -> str:
        """
        Route based on output guardrail decision:
        - pass/conditional/fail → END (send response to user)
        - regenerate → loop back to orchestrator (if retries left)
        """
        validation_result = state.get("output_guardrail", {})
        decision = validation_result.get("decision", "pass")
        retry_count = state.get("retry_count", settings.llm.max_regeneration_attempts)

        if decision == "regenerate":
            print(f"[GRAPH] Output guardrail triggered regeneration (attempt {retry_count})")
            # ✅ LOOP BACK: Go to orchestrator to regenerate response
            return "orchestrator"
        else:
            # pass, conditional, or fail → END (send to user)
            print(f"[GRAPH] Output guardrail decision: {decision} → ending workflow")
            return "end"

    g.add_conditional_edges(
        "output_guardrail",
        route_after_output_guardrail,
        {
            "orchestrator": "orchestrator",  # ✅ LOOP BACK FOR REGENERATION
            "end": END
        }
    )

    return g.compile()