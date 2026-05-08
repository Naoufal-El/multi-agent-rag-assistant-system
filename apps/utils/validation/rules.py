"""
Validation rules for Layer 1 input checks
Each rule returns a RuleResult with pass/fail status
"""

import re
import unicodedata
from apps.models.validation.rule_types import RuleResult, RuleSeverity, RuleCategory
from apps.config.settings import settings


def check_empty(text: str) -> RuleResult:
    """Check if text is empty or whitespace only"""
    passed = bool(text and text.strip())
    return RuleResult(
        passed=passed,
        rule_name="empty_check",
        severity=RuleSeverity.CRITICAL,
        category=RuleCategory.FORMAT,
        reason="Empty message not allowed" if not passed else None
    )


def check_length(text: str) -> RuleResult:
    """Check text length boundaries"""
    length = len(text)
    min_len = settings.validation.min_length
    max_len = settings.validation.max_length

    if length < min_len:
        return RuleResult(
            passed=False,
            rule_name="length_check",
            severity=RuleSeverity.HIGH,
            category=RuleCategory.FORMAT,
            reason="Text too short",
            details={"length": length, "min_required": min_len}
        )

    if length > max_len:
        return RuleResult(
            passed=False,
            rule_name="length_check",
            severity=RuleSeverity.HIGH,
            category=RuleCategory.FORMAT,
            reason="Text too long",
            details={"length": length, "max_allowed": max_len}
        )

    return RuleResult(
        passed=True,
        rule_name="length_check",
        severity=RuleSeverity.HIGH,
        category=RuleCategory.FORMAT,
        details={"length": length}
    )


def check_unicode_exploits(text: str) -> RuleResult:
    """Check for dangerous Unicode control characters"""
    dangerous_categories = {'Cc', 'Cf', 'Cs', 'Co', 'Cn'}

    for char in text:
        if unicodedata.category(char) in dangerous_categories:
            if char not in ['\n', '\t', '\r', ' ']:
                return RuleResult(
                    passed=False,
                    rule_name="unicode_check",
                    severity=RuleSeverity.CRITICAL,
                    category=RuleCategory.SECURITY,
                    reason="Dangerous Unicode control characters detected"
                )

    return RuleResult(
        passed=True,
        rule_name="unicode_check",
        severity=RuleSeverity.CRITICAL,
        category=RuleCategory.SECURITY
    )


def check_injection_patterns(text: str) -> RuleResult:
    """Check for prompt injection attempts"""
    injection_patterns = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?(previous\s+)?instructions",
        r"you\s+are\s+now\s+(in\s+)?developer\s+mode",
        r"system\s*:\s*",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
    ]

    text_lower = text.lower()
    for pattern in injection_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return RuleResult(
                passed=False,
                rule_name="injection_check",
                severity=RuleSeverity.CRITICAL,
                category=RuleCategory.SECURITY,
                reason="Prompt injection detected"
            )

    return RuleResult(
        passed=True,
        rule_name="injection_check",
        severity=RuleSeverity.CRITICAL,
        category=RuleCategory.SECURITY
    )


def check_critical_keywords(text: str) -> RuleResult:
    """Check for critical security keywords"""
    critical_keywords = [
        "bomb", "weapon", "kill", "murder", "attack", "terrorism",
        "exploit", "hack", "crack", "vulnerability", "sql injection"
    ]

    text_lower = text.lower()
    for keyword in critical_keywords:
        if keyword in text_lower:
            return RuleResult(
                passed=False,
                rule_name="keyword_check",
                severity=RuleSeverity.CRITICAL,
                category=RuleCategory.SECURITY,
                reason="Critical keyword detected"
            )

    return RuleResult(
        passed=True,
        rule_name="keyword_check",
        severity=RuleSeverity.CRITICAL,
        category=RuleCategory.SECURITY
    )


def check_meaningful_text(text: str) -> RuleResult:
    """Check if text contains meaningful content (not just emojis/symbols)"""
    # Remove emojis and special chars
    text_no_emoji = re.sub(r'[^\w\s?!.,;:]+', '', text)

    # Check for alphanumeric content
    has_alphanumeric = bool(re.search(r'[a-zA-Z0-9]', text_no_emoji))

    return RuleResult(
        passed=has_alphanumeric,
        rule_name="meaningful_text_check",
        severity=RuleSeverity.MEDIUM,
        category=RuleCategory.CONTENT,
        reason="No meaningful text content" if not has_alphanumeric else None
    )


def check_emoji_ratio(text: str) -> RuleResult:
    """Check emoji-to-text ratio - FIXED to exclude accented letters"""
    if not text:
        return RuleResult(
            passed=True,
            rule_name="emoji_ratio_check",
            severity=RuleSeverity.LOW,
            category=RuleCategory.CONTENT,
            details={"ratio": 0.0}
        )

    # Count ONLY actual emojis/symbols, NOT letter modifiers or accented letters
    emoji_count = 0
    for c in text:
        cat = unicodedata.category(c)
        # Only count symbol categories: So (Other Symbol), Sk (Modifier Symbol), Sm (Math Symbol)
        # EXCLUDE: Lm (Modifier Letter), Mn (Nonspacing Mark), etc.
        if cat in ['So', 'Sk', 'Sm']:
            # Additional check: skip combining marks
            if unicodedata.combining(c) == 0:
                emoji_count += 1

    ratio = emoji_count / len(text)
    max_ratio = settings.validation.max_emoji_ratio

    return RuleResult(
        passed=ratio <= max_ratio,
        rule_name="emoji_ratio_check",
        severity=RuleSeverity.LOW,
        category=RuleCategory.CONTENT,
        reason=f"Excessive emojis ({ratio:.2%} > {max_ratio:.2%})" if ratio > max_ratio else None,
        details={"ratio": round(ratio, 3), "max_allowed": max_ratio, "emoji_count": emoji_count}
    )


def check_special_char_ratio(text: str) -> RuleResult:
    """Check special character ratio"""
    if not text:
        return RuleResult(
            passed=True,
            rule_name="special_char_check",
            severity=RuleSeverity.MEDIUM,
            category=RuleCategory.CONTENT,
            details={"ratio": 0.0}
        )

    # Count non-alphanumeric, non-whitespace, non-common-punctuation
    special_count = sum(1 for c in text if not c.isalnum() and not c.isspace() and c not in '.,!?;:\'"()-')

    ratio = special_count / len(text)
    max_ratio = settings.validation.max_special_char_ratio

    return RuleResult(
        passed=ratio <= max_ratio,
        rule_name="special_char_check",
        severity=RuleSeverity.MEDIUM,
        category=RuleCategory.CONTENT,
        reason=f"Excessive special chars ({ratio:.2%} > {max_ratio:.2%})" if ratio > max_ratio else None,
        details={"ratio": round(ratio, 3), "max_allowed": max_ratio}
    )


def check_pii_patterns(text: str) -> RuleResult:
    """Check for PII patterns (emails, phone numbers, credit cards) - WARNING ONLY"""
    patterns = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        "credit_card": r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
    }

    found_pii = []
    for pii_type, pattern in patterns.items():
        if re.search(pattern, text):
            found_pii.append(pii_type)

    return RuleResult(
        passed=True,  # Don't block, just warn
        rule_name="pii_check",
        severity=RuleSeverity.LOW,
        category=RuleCategory.SECURITY,
        reason=f"Potential PII detected: {', '.join(found_pii)}" if found_pii else None,
        details={"pii_types": found_pii}
    )

# Map rule names to their checker functions
AVAILABLE_RULES = {
    "empty": check_empty,
    "length": check_length,
    "unicode_exploits": check_unicode_exploits,
    "injection_patterns": check_injection_patterns,
    "critical_keywords": check_critical_keywords,
    "meaningful_text": check_meaningful_text,
    "emoji_ratio": check_emoji_ratio,
    "special_char_ratio": check_special_char_ratio,
    "pii_patterns": check_pii_patterns,
}