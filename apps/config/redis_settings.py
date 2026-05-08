from envyaml import EnvYAML
from pydantic import BaseModel

envRedis = EnvYAML("apps/config/redis_conf.yaml")
params = envRedis.get("params", {})

class RedisSettings(BaseModel):
    ip: str
    port: int
    index_database: int

    @property
    def url(self) -> str:
        return f"redis://{self.ip}:{self.port}/{self.index_database}"

redis_settings = RedisSettings(**params)