from envyaml import EnvYAML
from pydantic import BaseModel

envDB = EnvYAML("apps/config/db_conf.yaml")
params = envDB.get("params", {})

class DBSettings(BaseModel):
    user: str
    password: str
    ip: str
    port: int
    database: str

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.ip}:{self.port}/{self.database}"

db_settings = DBSettings(**params)