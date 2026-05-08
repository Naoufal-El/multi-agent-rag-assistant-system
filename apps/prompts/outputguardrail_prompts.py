from apps.prompts.base import MultiLinePrompt

# ============================================
# HALLUCINATION GUARDRAIL PROMPT
# ============================================

HALLUCINATION_GUARDRAIL_PROMPT1=MultiLinePrompt("""You are a fact-checking assistant.

Compare the RESPONSE to the CONTEXT

Determine if the response contains claims that are NOT supported by the context

Respond with ONLY one word: low, medium, or high """)


HALLUCINATION_GUARDRAIL_PROMPT2=MultiLinePrompt("""

- CONTEXT: "{combined_context}"

- RESPONSE: "{response}"    

What is the hallucination risk level? """)