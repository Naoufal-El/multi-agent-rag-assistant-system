"""
Authentication Configuration - Shared across controllers and middleware
"""

from envyaml import EnvYAML
from pydantic import BaseModel

# Load configuration from YAML with .env variable substitution
envValidation = EnvYAML("apps/config/auth_conf.yaml")
params = envValidation.get("params", {})

class AuthenticationSettings(BaseModel):
    """Input validation configuration"""
    secret_key: str
    algorithm: str
    min_to_expire: int

auth_settings = AuthenticationSettings(**params)