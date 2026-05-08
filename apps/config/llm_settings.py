from envyaml import EnvYAML
from pydantic import BaseModel

envLLM = EnvYAML("apps/config/llm_conf.yaml")
params = envLLM.get("params", {})

class LLMSettings(BaseModel):
    ip: str
    port: int
    model: str
    conversation_temperature: float
    guardrails_temperature: float
    rag_temperature: float = 0.3
    routing_temperature: float
    verbose: bool
    embedding_model: str
    max_history_msgs: int
    max_tokens: int
    output_confidence_threshold: float
    min_retrieved_chunks: int
    max_regeneration_attempts: int
    min_response_length: int

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}"

llm_settings = LLMSettings(**params)