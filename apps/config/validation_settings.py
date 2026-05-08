"""
Validation Configuration Settings
Manages input validation rules and thresholds
"""

from envyaml import EnvYAML
from pydantic import BaseModel, Field
from typing import List

# Load configuration from YAML with .env variable substitution
envValidation = EnvYAML("apps/config/validation_conf.yaml")
params = envValidation.get("params", {})


class ValidationSettings(BaseModel):
    """Input validation configuration"""

    # Text length constraints
    min_length: int = Field(ge=1, le=100)
    max_length: int = Field(ge=100, le=10000)

    # Character ratio thresholds
    max_emoji_ratio: float = Field(ge=0.0, le=1.0)
    max_special_char_ratio: float = Field(ge=0.0, le=1.0)

    # Rate limiting
    rate_limit_enabled: bool
    max_requests_per_minute: int = Field(ge=1, le=1000)
    max_requests_per_hour: int = Field(ge=1, le=10000)

    # Spam detection
    spam_detection_enabled: bool
    max_repeated_queries: int = Field(ge=1, le=10)

    # Execution strategy
    strategy: str = Field(pattern="^(fail_fast|collect_all)$")

    layer2_threshold: int

    # Critical keywords (hardcoded - not in .env)
    @property
    def critical_keywords(self) -> List[str]:
        """Keywords that trigger immediate blocking"""
        return [
            "bomb", "weapon", "kill", "murder", "attack", "terrorism",
            "exploit", "hack", "crack", "vulnerability", "sql injection"
        ]

    # Injection patterns (hardcoded - regex too complex for .env)
    @property
    def injection_patterns(self) -> List[str]:
        """Regex patterns for prompt injection detection"""
        return [
            r"ignore\s+(all\s+)?previous\s+instructions",
            r"disregard\s+(all\s+)?(previous\s+)?instructions",
            r"you\s+are\s+now\s+(in\s+)?developer\s+mode",
            r"system\s*:\s*",
            r"<\|im_start\|>",
            r"<\|im_end\|>",
        ]


# Singleton instance
validation_settings = ValidationSettings(**params)