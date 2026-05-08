import httpx, asyncpg
from typing import Dict
import redis.asyncio as redis
from apps.core.workflow.state import Route
from apps.core.workflow.state import State
from apps.core.workflow.graph import build_graph
from apps.config.settings import settings


class ControllerError(Exception):
    """Custom exception for Controller errors"""
    pass


class ControllerTimeoutError(ControllerError):
    """Exception for timeout errors"""
    pass


class HealthCheckError(ControllerError):
    """Exception for health check failures"""
    pass


class HealthService:
    def __init__(self):
        self.graph = build_graph()
        self.health_status = {
            "ollama": "unknown",
            "redis": "unknown",
            "postgres": "unknown",
            "qdrant": "unknown"
        }
        self.redis_url = settings.redis.url
        self.ollama_url = settings.llm.url
        self.qdrant_url = settings.qdrant.url
        self.postgres_url = settings.db.url
        # self.engine = create_engine(url= self.postgres_url)
        # self.Session = sessionmaker(self.engine, expire_on_commit=False)

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

    def update_health_status(self, service: str, status: str):
        """Update health status for monitoring"""
        self.health_status[service] = status

    async def health_check(self) -> Dict[str, str]:
        """Perform health checks on dependencies"""
        results = {}

        # Check Redis
        try:
            r = redis.from_url(self.redis_url, decode_responses=True)
            response = await r.ping()
            results["redis"] = "ok" if response else "error"
            await r.aclose()
        except Exception as e:
            results["redis"] = f"error: {str(e)}"

        # Check Ollama
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.ollama_url)
                if response.status_code == 200:
                    results["ollama"] = "ok"
                else:
                    results["ollama"] = f"error: status {response.status_code}"
        except Exception as e:
            results["ollama"] = f"error: {str(e)}"

        # Check PostgreSQL (use singleton instance)
        # session = self.Session()
        # try:
        #     is_healthy = await postgres_client.health_check(session)
        #     results["postgres"] = "ok" if is_healthy else "error"
        # except Exception as e:
        #     results["postgres"] = f"error: {str(e)}"

        # Check PostgreSQL - Direct connection test (like Redis)
        try:
            # Create a temporary connection to test
            conn = await asyncpg.connect(self.postgres_url)
            # Execute simple query to verify connection
            result = await conn.fetchval("SELECT 1")
            await conn.close()
            results["postgres"] = "ok" if result == 1 else "error"
        except Exception as e:
            results["postgres"] = f"error: {str(e)}"

        # Check Qdrant
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.qdrant_url}")
                if response.status_code == 200:
                    results["qdrant"] = "ok"
                else:
                    results["qdrant"] = f"error: status {response.status_code}"
        except Exception as e:
            results["qdrant"] = f"error: {str(e)}"

        # Update internal health status
        for service, status in results.items():
            self.health_status[service] = status

        results["controller"] = "ok"
        return results


# Global controller instance
healthService = HealthService()