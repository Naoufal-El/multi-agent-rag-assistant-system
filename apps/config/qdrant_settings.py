from envyaml import EnvYAML
from pydantic import BaseModel

envRedis = EnvYAML("apps/config/qdrant_conf.yaml")
params = envRedis.get("params", {})

class QdrantSettings(BaseModel):
    ip: str
    port: int
    customer_collection: str
    process_collection: str
    vector_size: int
    retrieval_enabled: bool
    retrieval_top_k: int


    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}"

qdrant_settings = QdrantSettings(**params)