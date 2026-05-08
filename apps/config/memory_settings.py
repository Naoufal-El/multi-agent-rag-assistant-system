"""
Memory Configuration Settings
Manages Redis, PostgreSQL, and Hybrid Memory settings
"""
from envyaml import EnvYAML
from pydantic import BaseModel
from typing import Literal

# Load configuration from YAML (with .env variable substitution)
envMemory = EnvYAML("apps/config/memory_conf.yaml")
params = envMemory.get("params", {})


class MemorySettings(BaseModel):
    """Memory management configuration"""

    # Memory Strategy
    strategy: Literal["redis_only", "postgres_only", "hybrid"]

    # Redis Cache Settings
    redis_ttl_days: int
    redis_max_history_buffer: int

    # PostgreSQL Settings
    max_history_from_db: int

    # PostgreSQL Connection Pool
    postgres_pool_size: int
    postgres_max_overflow: int
    postgres_pool_recycle: int

    # Cache Behavior
    cache_warm_on_load: bool


# Singleton instance
memory_settings = MemorySettings(**params)