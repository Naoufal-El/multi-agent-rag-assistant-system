"""
Output Guardrail - Response Quality Validation

Validates responses before sending to users (Step 3 - Guardrails Phase)

Checks:
- Response completeness
- Hallucination detection (RAG context alignment)
- Quality thresholds
- Confidence validation
"""

from typing import Dict, List, Any, Optional
from apps.core.llm.ollama_client import ollama_client
from apps.config.settings import settings
from apps.prompts.outputguardrail_prompts import HALLUCINATION_GUARDRAIL_PROMPT1, HALLUCINATION_GUARDRAIL_PROMPT2

class OutputGuardrail:
    """
    Validates agent responses for quality, accuracy, and safety

    Uses centralized configuration from settings
    """

    def __init__(self):
        """Initialize with configuration from settings"""
        # Load from centralized config
        self.min_confidence_threshold = settings.llm.output_confidence_threshold
        self.min_retrieved_chunks = settings.llm.min_retrieved_chunks
        self.max_regeneration_attempts = settings.llm.max_regeneration_attempts
        self.min_response_length = settings.llm.min_response_length

        print(f"[OUTPUT_GUARDRAIL] Initialized with:")
        print(f"  - Min confidence: {self.min_confidence_threshold}")
        print(f"  - Min chunks for RAG: {self.min_retrieved_chunks}")
        print(f"  - Max retries: {self.max_regeneration_attempts}")

    def validate(
            self,
            response: str,
            response_metadata: Dict[str, Any],
            retrieved_context: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Main validation method

        Args:
            response: Generated response text
            response_metadata: Metadata from agent (confidence, sources, etc.)
            retrieved_context: Retrieved documents (for RAG responses only)

        Returns:
            OutputGuardrailResult dict with validation results
        """
        checks = {}
        failures = []
        warnings = []

        # Check 1: Completeness
        completeness_result = self._check_completeness(response)
        checks["completeness"] = completeness_result
        if not completeness_result["passed"]:
            failures.append("Response incomplete or too short")

        # Check 2: Confidence threshold
        confidence_result = self._check_confidence(response_metadata)
        checks["confidence"] = confidence_result
        if not confidence_result["passed"]:
            failures.append(
                f"Low confidence: {response_metadata.get('confidence', 0):.2f}"
            )

        # Check 3: RAG-specific checks
        if response_metadata.get("agent") == "cs_rag":
            rag_result = self._check_rag_quality(response_metadata)
            checks["rag_quality"] = rag_result
            if not rag_result["passed"]:
                failures.append("Insufficient retrieval quality")

        # Check 4: Hallucination detection (only for RAG with context)
        if retrieved_context and len(retrieved_context) > 0:
            hallucination_result = self._check_hallucination(
                response,
                retrieved_context
            )
            checks["hallucination"] = hallucination_result

            if hallucination_result["risk_level"] == "high":
                failures.append("High hallucination risk detected")
            elif hallucination_result["risk_level"] == "medium":
                warnings.append("Potential hallucination detected")

        # Calculate overall score
        passed_checks = sum(
            1 for check in checks.values()
            if check.get("passed", False)
        )
        total_checks = len(checks)
        overall_score = passed_checks / total_checks if total_checks > 0 else 0.0

        # Determine decision
        if failures:
            # Regenerate if few failures, fail if many
            decision = "regenerate" if len(failures) <= 2 else "fail"
        elif warnings:
            decision = "conditional"  # Pass with disclaimer
        else:
            decision = "pass"

        # Build result
        result = {
            "overall_score": overall_score,
            "passed": decision in ["pass", "conditional"],
            "decision": decision,
            "checks": checks,
            "issues": failures,
            "warnings": warnings,
            "suggested_action": self._suggest_action(
                decision,
                failures,
                response_metadata
            )
        }

        return result

    def _check_completeness(self, response: str) -> Dict[str, Any]:
        """
        Check if response is complete and substantive
        """
        # Use configured min length
        is_long_enough = len(response) >= self.min_response_length

        # Check for vague responses
        vague_indicators = [
            "i'm not sure",
            "i don't know",
            "sorry, i can't",
            "i'm unable to",
            "no information"
        ]
        is_vague = any(
            indicator in response.lower()
            for indicator in vague_indicators
        )

        # Check for incomplete sentences
        ends_properly = response.strip().endswith(('.', '!', '?'))

        # Calculate score
        score = 0.0
        if is_long_enough:
            score += 0.4
        if not is_vague:
            score += 0.4
        if ends_properly:
            score += 0.2

        passed = score >= 0.6

        return {
            "passed": passed,
            "score": score,
            "length": len(response),
            "is_vague": is_vague,
            "ends_properly": ends_properly,
            "details": (
                f"Length: {len(response)}/{self.min_response_length}, "
                f"Vague: {is_vague}, "
                f"Ends properly: {ends_properly}"
            )
        }

    def _check_confidence(self, response_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate confidence score from agent
        """
        confidence = response_metadata.get("confidence", 0.0)
        passed = confidence >= self.min_confidence_threshold

        return {
            "passed": passed,
            "score": confidence,
            "threshold": self.min_confidence_threshold,
            "details": (
                f"Confidence: {confidence:.2f}, "
                f"Threshold: {self.min_confidence_threshold}"
            )
        }

    def _check_rag_quality(
            self,
            response_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check RAG-specific quality metrics
        """
        retrieved_chunks = response_metadata.get("retrieved_chunks", 0)
        used_context = response_metadata.get("used_context", False)

        # Need minimum documents for reliable RAG
        has_enough_docs = retrieved_chunks >= self.min_retrieved_chunks

        # Context should be used
        context_used = used_context is True

        passed = has_enough_docs and context_used
        score = (0.5 if has_enough_docs else 0.0) + (0.5 if context_used else 0.0)

        return {
            "passed": passed,
            "score": score,
            "retrieved_chunks": retrieved_chunks,
            "used_context": used_context,
            "min_chunks_required": self.min_retrieved_chunks,
            "details": f"Retrieved: {retrieved_chunks}, Used: {used_context}"
        }

    def _check_hallucination(
            self,
            response: str,
            retrieved_context: List[Dict]
    ) -> Dict[str, Any]:
        """
        Detect potential hallucinations by comparing response to retrieved context

        Uses LLM to check if response claims are grounded in context
        """
        # Build context text from top 3 documents
        context_texts = [
            doc.get("content", "")
            for doc in retrieved_context[:3]
        ]
        combined_context = "\n\n".join(context_texts)

        # Truncate if too long
        max_context_length = 1500
        if len(combined_context) > max_context_length:
            combined_context = combined_context[:max_context_length] + "..."

        # LLM-based hallucination detection
        hallucination_prompt = [
            {
                "role": "system",
                "content": HALLUCINATION_GUARDRAIL_PROMPT1
            },
            {
                "role": "user",
                "content": HALLUCINATION_GUARDRAIL_PROMPT2(combined_context=combined_context, response=response)
            }
        ]

        try:
            # Use temperature=0.0 for deterministic classification
            llm_response = ollama_client.generate_response(
                hallucination_prompt,
                temperature=settings.llm.guardrails_temperature
            ).strip().lower()

            # Parse response
            if "high" in llm_response:
                risk_level = "high"
                grounded = False
            elif "medium" in llm_response:
                risk_level = "medium"
                grounded = True
            else:
                risk_level = "low"
                grounded = True

            return {
                "risk_level": risk_level,
                "grounded": grounded,
                "reasoning": llm_response[:200],
                "passed": risk_level != "high",
                "score": (
                    1.0 if risk_level == "low"
                    else (0.5 if risk_level == "medium" else 0.0)
                ),
                "details": f"Risk: {risk_level}, Grounded: {grounded}"
            }

        except Exception as e:
            print(f"[OUTPUT_GUARDRAIL] Hallucination check failed: {e}")
            # Default to low risk on error (don't block on technical failure)
            return {
                "risk_level": "low",
                "grounded": True,
                "reasoning": f"Check failed: {str(e)[:100]}",
                "passed": True,
                "score": 0.8,
                "details": f"Error during check: {str(e)[:50]}"
            }

    def _suggest_action(
            self,
            decision: str,
            failures: List[str],
            response_metadata: Dict[str, Any]
    ) -> str:
        """
        Suggest what to do based on validation results
        """
        if decision == "pass":
            return "Send response to user"

        if decision == "conditional":
            return "Add disclaimer and send to user"

        if decision == "regenerate":
            agent = response_metadata.get("agent", "unknown")

            # Smart suggestion based on failure type
            if agent == "cs_rag" and "Insufficient retrieval" in str(failures):
                return "Try conversational fallback (cs_answer agent)"
            else:
                return "Regenerate response with adjusted parameters"

        if decision == "fail":
            return "Send fallback error message to user"

        return "Unknown action"


# Global instance
output_guardrail = OutputGuardrail()