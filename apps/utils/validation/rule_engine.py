"""
Rule Engine - Orchestrates validation rule execution
Supports fail-fast and collect-all strategies
"""

from typing import List, Optional
from apps.models.validation.rule_types import RuleResult, ValidationResult, RuleSeverity, RuleCategory
from apps.utils.validation.rules import AVAILABLE_RULES
from apps.config.settings import settings


class RuleEngine:
    """
    Executes validation rules with configurable strategies
    """

    def run(
            self,
            text: str,
            rules: List[str],
            strategy: Optional[str] = None
    ) -> ValidationResult:
        """
        Execute validation rules on text

        Args:
            text: Text to validate
            rules: List of rule names to execute (from AVAILABLE_RULES)
            strategy: Execution strategy ('fail_fast' or 'collect_all')
                     If None, uses settings.validation.strategy

        Returns:
            ValidationResult with aggregated results
        """
        # Default strategy from settings
        if strategy is None:
            strategy = settings.validation.strategy

        passed_rules: List[RuleResult] = []
        failed_rules: List[RuleResult] = []
        all_results: List[RuleResult] = []

        for rule_name in rules:
            # Get rule function
            rule_func = AVAILABLE_RULES.get(rule_name)

            if rule_func is None:
                print(f"[RuleEngine] WARNING: Unknown rule '{rule_name}', skipping")
                continue

            # Execute rule
            try:
                result = rule_func(text)
                all_results.append(result)

                if result.passed:
                    passed_rules.append(result)
                else:
                    failed_rules.append(result)

                    # Fail-fast: Stop on first CRITICAL failure
                    if strategy == "fail_fast" and result.severity == RuleSeverity.CRITICAL:
                        print(f"[RuleEngine] FAIL-FAST: Critical rule '{rule_name}' failed")
                        break

            except Exception as e:
                print(f"[RuleEngine] ERROR executing rule '{rule_name}': {e}")
                # On error, create a failed result
                error_result = RuleResult(
                    passed=False,
                    rule_name=rule_name,
                    severity=RuleSeverity.HIGH,
                    category=RuleCategory.ERROR,
                    reason=f"Rule execution error: {str(e)[:100]}"
                )
                all_results.append(error_result)
                failed_rules.append(error_result)

        # Overall validation passed if no failures
        overall_passed = len(failed_rules) == 0

        return ValidationResult(
            passed=overall_passed,
            failed_rules=failed_rules,
            passed_rules=passed_rules,
            all_results=all_results,
            strategy=strategy
        )

    def get_available_rules(self) -> List[str]:
        """Get list of all available rule names"""
        return list(AVAILABLE_RULES.keys())


# Singleton instance
rule_engine = RuleEngine()