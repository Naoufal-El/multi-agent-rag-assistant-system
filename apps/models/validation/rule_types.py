"""
Rule Type Definitions
Defines data structures and enums for validation rules
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class RuleSeverity(Enum):
    """Rule severity levels"""
    CRITICAL = "critical"  # Must pass, blocks immediately
    HIGH = "high"          # Important, should pass
    MEDIUM = "medium"      # Standard check
    LOW = "low"            # Warning only


class RuleCategory(Enum):
    """Rule categorization"""
    FORMAT = "format"          # Text format validation
    SECURITY = "security"      # Security threats
    CONTENT = "content"        # Content quality
    RATE_LIMIT = "rate_limit"  # Rate limiting
    SPAM = "spam"              # Spam detection
    ERROR="error"            # Execution errors


@dataclass
class RuleResult:
    """Result of a validation rule execution"""

    # Core fields
    passed: bool
    rule_name: str
    severity: RuleSeverity
    category: RuleCategory

    # Optional details
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    score: Optional[float] = None

    def __repr__(self) -> str:
        status = "✓ PASSED" if self.passed else "✗ FAILED"
        return f"<RuleResult {self.rule_name}: {status}>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "passed": self.passed,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "category": self.category.value,
            "reason": self.reason,
            "details": self.details,
            "score": self.score,
        }


@dataclass
class ValidationResult:
    """Aggregated result of multiple rule validations"""

    passed: bool
    failed_rules: list[RuleResult]
    passed_rules: list[RuleResult]
    all_results: list[RuleResult]
    strategy: str

    @property
    def first_failure(self) -> Optional[RuleResult]:
        """Get the first failed rule (for fail_fast strategy)"""
        return self.failed_rules[0] if self.failed_rules else None

    @property
    def critical_failures(self) -> list[RuleResult]:
        """Get all critical severity failures"""
        return [r for r in self.failed_rules if r.severity == RuleSeverity.CRITICAL]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "passed": self.passed,
            "strategy": self.strategy,
            "failed_count": len(self.failed_rules),
            "passed_count": len(self.passed_rules),
            "failed_rules": [r.to_dict() for r in self.failed_rules],
            "passed_rules": [r.to_dict() for r in self.passed_rules],
        }