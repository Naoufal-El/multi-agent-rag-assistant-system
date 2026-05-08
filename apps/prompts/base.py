"""
Base Prompt System - Template Engine for Dynamic Prompts
"""
import textwrap

class PromptTemplate:
    """
    Simple prompt template that supports variable substitution
    """
    def __init__(self, template: str):
        self.template = template

    def format(self, **kwargs) -> str:
        """Format template with provided variables"""
        return self.template.format(**kwargs)

    def __call__(self, **kwargs) -> str:
        """Allow direct calling: prompt(var1=val1, var2=val2)"""
        return self.format(**kwargs)


class MultiLinePrompt(PromptTemplate):
    """
    Multi-line prompt that auto-strips leading whitespace
    """
    def __init__(self, template: str):
        # Clean up indentation while preserving structure
        cleaned = textwrap.dedent(template).strip()
        super().__init__(cleaned)