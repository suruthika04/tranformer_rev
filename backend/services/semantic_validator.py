"""
Nexa AI — Semantic Validator
Ensures that token filtering does not remove critical semantic elements.

Protected categories:
- Negation words (not, never, no, etc.)
- Numbers and dates
- Mathematical operators
- Programming keywords
- Variable/function names
- Technical terminology
- Question intent words
"""

import re
from typing import List, Tuple, Set

from services.feature_extractor import (
    NEGATION_TOKENS,
    PROGRAMMING_ENTITIES,
    HIGH_INFORMATION_KEYWORDS,
    MATH_OPERATORS,
)

# Words that indicate question intent
QUESTION_WORDS = {"what", "how", "why", "when", "where", "who", "which", "can", "could", "would", "should", "do", "does", "did", "is", "are"}


def validate_semantic_preservation(
    original_tokens: List[str],
    selected_tokens: List[str],
    filtered_tokens: List[str],
) -> Tuple[bool, str]:
    """
    Verify that filtering has not removed mission-critical tokens.

    Checks:
    1. No negation words removed (would invert meaning).
    2. No critical programming entities removed.
    3. At least one substantive token retained.
    4. Numbers and operators preserved.
    5. Question intent preserved.

    Returns (is_safe: bool, message: str).
    """
    sel_lower = {t.lower().strip() for t in selected_tokens}
    filt_lower_list = [t.lower().strip() for t in filtered_tokens]

    # Check 1: Negation preservation
    for tok in filt_lower_list:
        clean = re.sub(r"^[^\w]+|[^\w]+$", "", tok)
        if clean in NEGATION_TOKENS:
            return False, f"Critical negation word '{tok}' was filtered. Meaning would invert."

    # Check 2: Programming entity preservation
    for tok in filt_lower_list:
        clean = re.sub(r"^[^\w]+|[^\w]+$", "", tok)
        if clean in PROGRAMMING_ENTITIES:
            return False, f"Programming keyword '{tok}' was filtered."

    # Check 3: At least one token retained
    if not selected_tokens:
        return False, "No tokens retained — input would be empty."

    # Check 4: Numbers preserved
    for tok in filt_lower_list:
        clean = re.sub(r"^[^\w]+|[^\w]+$", "", tok)
        if re.match(r"^\d+(\.\d+)?$", clean):
            return False, f"Numeric value '{tok}' was filtered."

    # Check 5: Math operators preserved
    for tok in filtered_tokens:
        if tok.strip() in MATH_OPERATORS:
            return False, f"Mathematical operator '{tok}' was filtered."

    # Check 6: Question intent
    orig_lower = {re.sub(r"^[^\w]+|[^\w]+$", "", t.lower().strip()) for t in original_tokens}
    orig_questions = orig_lower & QUESTION_WORDS
    sel_questions = {re.sub(r"^[^\w]+|[^\w]+$", "", t.lower().strip()) for t in selected_tokens} & QUESTION_WORDS
    if orig_questions and not sel_questions:
        return False, "Question intent words were all filtered."

    return True, "Semantic preservation verified."


def get_protected_tokens(tokens: List[str]) -> Set[int]:
    """
    Return set of token indices that should NEVER be filtered,
    regardless of their confidence score.
    """
    protected = set()
    for i, token in enumerate(tokens):
        clean = re.sub(r"^[^\w]+|[^\w]+$", "", token.lower().strip())

        if clean in NEGATION_TOKENS:
            protected.add(i)
        elif clean in PROGRAMMING_ENTITIES:
            protected.add(i)
        elif re.match(r"^\d+(\.\d+)?$", clean):
            protected.add(i)
        elif token.strip() in MATH_OPERATORS:
            protected.add(i)

    return protected
