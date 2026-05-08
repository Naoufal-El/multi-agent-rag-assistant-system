"""
Input Guardrail - Hybrid Two-Layer Approach
Layer 1: Fast format validation using rule engine (1-5ms)
Layer 2: LLM context checking (100-200ms)
"""

import json
import time
from apps.core.llm.ollama_client import ollama_client
from typing import Tuple, Dict, Any, Optional
from collections import defaultdict
from apps.prompts.inputguardrail_promts import INPUT_GUARDRAIL_PROMPT
from apps.utils.validation.rule_engine import rule_engine
from apps.config.settings import settings


class InputGuardrail:
    """
    Two-layer hybrid input validation
    Layer 1: Rule-based format checks
    Layer 2: LLM-based content validation
    """

    def __init__(self):
        self.rate_limit_tracker = defaultdict(list)
        self.query_history = defaultdict(list)

    def validate(
            self,
            query: str,
            session_id: Optional[str] = None,
            context: Optional[Dict[str, Any]] = None  # ← NEW: Added context parameter
    ) -> Dict[str, Any]:
        """
        Main validation method

        Args:
            query: User input to validate
            session_id: Optional session ID for rate limiting
            context: Optional context dict (e.g., {"skip_domain_check": True})

        Returns:
            Validation result dictionary
        """
        context = context or {}  # ← NEW: Initialize context

        result = {
            "passed": False,
            "layer1_passed": False,
            "layer2_passed": None,
            "blocked_reason": None,
            "layer1_checks": {},
            "layer2_score": None,
            "warnings": []
        }

        # Layer 1: Format checks
        layer1_passed, reason, checks = self._layer1_format_check(query, session_id)
        result["layer1_passed"] = layer1_passed
        result["layer1_checks"] = checks

        if not layer1_passed:
            result["blocked_reason"] = reason
            print(f"[INPUT_GUARDRAIL] Layer 1 BLOCKED: {reason}")
            return result

        print("[INPUT_GUARDRAIL] ✅ Layer 1 PASSED")

        # Add warnings
        if "warnings" in checks:
            result["warnings"].extend(checks["warnings"])

        # Layer 2: LLM check (SKIP if context says so)
        skip_domain = context.get("skip_domain_check", False)  # ← NEW

        if skip_domain:
            print("[INPUT_GUARDRAIL] Skipping Layer 2 (domain check disabled)")
            result["layer2_passed"] = True
            result["layer2_score"] = 10.0
            result["passed"] = True
            return result

        layer2_passed, reason, llm_score = self._layer2_llm_check(query)
        result["layer2_passed"] = layer2_passed
        result["layer2_score"] = llm_score

        if not layer2_passed:
            result["blocked_reason"] = reason
            print(f"[INPUT_GUARDRAIL] Layer 2 BLOCKED: {reason} (score: {llm_score})")
            return result

        print(f"[INPUT_GUARDRAIL] Layer 2 PASSED (score: {llm_score})")

        # Success
        result["passed"] = True
        print("[INPUT_GUARDRAIL] ✅ PASSED")

        # Track query for spam detection
        if settings.validation.spam_detection_enabled and session_id:
            self.query_history[session_id].append(query)
            self.query_history[session_id] = self.query_history[session_id][-5:]

        return result

    def _layer1_format_check(
            self,
            query: str,
            session_id: Optional[str]
    ) -> Tuple[bool, Optional[str], Dict]:
        """Layer 1: Fast format validation using rule engine"""

        checks = {"warnings": []}

        rules_to_run = [
            "empty",
            "length",
            "unicode_exploits",
            "injection_patterns",
            "critical_keywords",
            "meaningful_text",
            "emoji_ratio",
            "special_char_ratio",
            "pii_patterns",
        ]

        validation_result = rule_engine.run(
            text=query,
            rules=rules_to_run,
            strategy=settings.validation.strategy
        )

        checks["rule_results"] = validation_result.to_dict()
        checks["rules_passed"] = len(validation_result.passed_rules)
        checks["rules_failed"] = len(validation_result.failed_rules)

        # Collect warnings
        for rule_result in validation_result.failed_rules:
            if rule_result.severity.value == "low":
                checks["warnings"].append(
                    f"{rule_result.rule_name}: {rule_result.reason}"
                )

        # Rate limiting
        if settings.validation.rate_limit_enabled and session_id:
            rate_ok, rate_reason = self._check_rate_limit(session_id)
            checks["rate_limit_ok"] = rate_ok
            if not rate_ok:
                return False, rate_reason, checks

        # Spam detection
        if settings.validation.spam_detection_enabled and session_id:
            spam_ok, spam_reason = self._check_spam(query, session_id)
            checks["spam_ok"] = spam_ok
            if not spam_ok:
                return False, spam_reason, checks

        # Check if validation failed
        if not validation_result.passed:
            first_failure = validation_result.first_failure
            return False, first_failure.reason, checks

        return True, None, checks

    def _layer2_llm_check(self, query: str) -> Tuple[bool, Optional[str], float]:
        """
        Layer 2: LLM-based safety and domain validation

        Checks:
        1. Safety (toxic, threats, spam)
        2. Domain appropriateness (electronics/customer service related)

        Returns: (passed, reason, score)
        """
        try:
            # ✅ UPDATED: Domain-specific prompt
            system_prompt = INPUT_GUARDRAIL_PROMPT

            user_prompt = f'Evaluate: "{query}"'

            prompt = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # Use temperature=0.0 for deterministic classification
            llm_response = ollama_client.generate_response(prompt, temperature=settings.llm.guardrails_temperature).strip()

            # Robust JSON extraction
            start_idx = llm_response.find('{')
            end_idx = llm_response.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = llm_response[start_idx:end_idx+1]
            else:
                json_str = llm_response

            # Parse JSON
            parsed_result = json.loads(json_str)
            score_value = float(parsed_result.get("score", 5))
            is_appropriate = parsed_result.get("appropriate", True)
            category = parsed_result.get("category", "unknown")
            reason_text = parsed_result.get("reason", "")

            print(f"[INPUT_GUARDRAIL] Layer 2 result: score={score_value}, appropriate={is_appropriate}, category={category}")

            # Block if score < 5 or explicitly inappropriate
            threshold = settings.validation.layer_2_threshold
            if score_value < threshold or not is_appropriate:
                print(f"[INPUT_GUARDRAIL] Layer 2 BLOCK: {reason_text} (category: {category})")
                return False, reason_text or "content_validation_failed", score_value

            return True, None, score_value

        except json.JSONDecodeError as e:
            print(f"[INPUT_GUARDRAIL] LLM JSON parse error: {e}")
            print(f"[INPUT_GUARDRAIL] Raw response: {llm_response[:200]}")
            # On parse error, default to BLOCK (safer)
            return False, "content_validation_error", 0.0
        except Exception as e:
            print(f"[INPUT_GUARDRAIL] LLM error: {e}")
            # On other errors, BLOCK
            return False, "system_error", 0.0

    def _check_rate_limit(self, session_id: str) -> Tuple[bool, Optional[str]]:
        """Check rate limits for session"""
        now = time.time()

        self.rate_limit_tracker[session_id] = [
            ts for ts in self.rate_limit_tracker[session_id]
            if ts > now - 3600
        ]

        timestamps = self.rate_limit_tracker[session_id]

        # Check per-minute
        recent = [ts for ts in timestamps if ts > now - 60]
        if len(recent) >= settings.validation.max_requests_per_minute:
            return False, "rate_limit_exceeded_minute"

        # Check per-hour
        if len(timestamps) >= settings.validation.max_requests_per_hour:
            return False, "rate_limit_exceeded_hour"

        self.rate_limit_tracker[session_id].append(now)
        return True, None

    def _check_spam(self, query: str, session_id: str) -> Tuple[bool, Optional[str]]:
        """Check for repeated queries (spam detection)"""
        history = self.query_history.get(session_id, [])
        if not history:
            return True, None

        query_lower = query.lower().strip()
        repeat_count = sum(1 for q in history if q.lower().strip() == query_lower)

        if repeat_count >= settings.validation.max_repeated_queries:
            return False, "repeated_query_spam"

        return True, None


# Singleton instance
input_guardrail = InputGuardrail()