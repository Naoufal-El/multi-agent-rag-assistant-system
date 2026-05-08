import asyncio
from apps.core.workflow.state import Route
from apps.core.workflow.state import State
from apps.core.workflow.graph import build_graph
from apps.config.settings import settings
from apps.services.HealthService import healthService


class ControllerError(Exception):
    """Custom exception for Controller errors"""
    pass


class ControllerTimeoutError(ControllerError):
    """Exception for timeout errors"""
    pass


class ChatService:
    def __init__(self):
        self.graph = build_graph()
        self.health_status = {"ollama": "unknown", "redis": "unknown"}
        # Get service URLs from environment
        self.redis_url = settings.redis.url
        self.ollama_base = settings.llm.url

    async def invoke_with_supervision(self, state: State) -> State:
        """Execute graph with timeout, retries, and health checks"""

        timeout_seconds = settings.controller_timeout
        print(f"[CONTROLLER] Using timeout: {timeout_seconds}s")

        # Run health check if not done yet
        if self.health_status.get("ollama") == "unknown":
            print("[CONTROLLER] Running health check...")
            await healthService.health_check()

        # Add supervision metadata
        state["meta"] = state.get("meta", {})
        state["meta"]["health"] = self.health_status
        state["meta"]["flags"] = {
            "retrieval_enabled": self.health_status.get("redis") == "ok",
            "llm_fallback_enabled": True
        }

        try:
            # Execute with timeout
            result = await self._execute_with_timeout(state, timeout_seconds)
            return result

        except ControllerTimeoutError:
            print(f"[CONTROLLER] TIMEOUT after {timeout_seconds}s")
            return self._create_error_response(state, "Request timed out")

        except Exception as e:
            print(f"[CONTROLLER] ERROR: {e}")
            return self._create_error_response(state, f"System error: {str(e)}")

    async def _execute_with_timeout(self, state: State, timeout_seconds: int) -> State:
        """Execute graph with cross-platform timeout"""

        print(f"[CONTROLLER] Starting graph execution with {timeout_seconds}s timeout")

        try:
            # ← CHANGED: Use ainvoke() for async graphs
            result = await asyncio.wait_for(
                self.graph.ainvoke(state),  # ← FIXED: Changed from invoke to ainvoke
                timeout=timeout_seconds
            )

            print("[CONTROLLER] Graph execution completed successfully")
            return result

        except asyncio.TimeoutError:
            print(f"[CONTROLLER] TimeoutError caught after {timeout_seconds}s")
            raise ControllerTimeoutError(f"Operation exceeded {timeout_seconds} seconds")

    @staticmethod
    def _create_error_response(state: State, error_msg: str) -> State:
        """Create standardized error response"""

        state["messages"] = state.get("messages", [])
        state["messages"].append({
            "role": "assistant",
            "content": f"I apologize, but I'm experiencing technical difficulties: {error_msg}"
        })

        route: Route = "blocked"
        state["route"] = route
        return state


# Global controller instance
chatService = ChatService()