"""
Nexa AI — Token Feature Extractor
Extracts multiple features for each token to feed into the confidence evaluator.

Features extracted per token:
1. Token importance (length-based heuristic)
2. Token position (relative position in sequence)
3. Keyword relevance (match against known important keywords)
4. Context relevance (co-occurrence with neighboring tokens)
5. Semantic contribution (based on part-of-speech heuristics)
6. Technical importance (programming/technical terms)
7. Code-related importance (code syntax elements)
8. Numeric importance (numbers, dates, operators)
"""

import re
from typing import List, Dict, Any

# Critical token categories
NEGATION_TOKENS = {
    "not", "never", "no", "without", "neither", "nor", "none",
    "cannot", "can't", "don't", "doesn't", "didn't", "won't",
    "wouldn't", "shouldn't", "couldn't", "isn't", "aren't", "wasn't",
    "weren't", "hardly", "barely", "scarcely", "nothing", "nowhere",
}

PROGRAMMING_ENTITIES = {
    "python", "javascript", "typescript", "java", "c", "c++", "cpp", "c#",
    "rust", "golang", "go", "ruby", "php", "swift", "kotlin", "scala", "r",
    "sql", "mysql", "postgresql", "mongodb", "sqlite", "redis",
    "fastapi", "flask", "django", "express", "react", "nextjs", "vue", "angular",
    "pytorch", "tensorflow", "keras", "scikit", "pandas", "numpy",
    "docker", "kubernetes", "git", "linux", "bash",
    "html", "css", "graphql", "rest", "api", "json", "yaml", "jwt", "oauth",
    "def", "class", "import", "return", "print", "for", "while", "if", "else",
    "elif", "try", "except", "finally", "async", "await", "function", "const",
    "let", "var", "lambda", "yield", "raise", "pass", "break", "continue",
}

HIGH_INFORMATION_KEYWORDS = {
    "code", "algorithm", "program", "write", "create", "build", "implement",
    "calculate", "compute", "find", "search", "sort", "compare", "analyze",
    "explain", "describe", "define", "list", "convert", "generate", "optimize",
    "debug", "test", "deploy", "install", "configure", "setup", "connect",
    "addition", "subtraction", "multiplication", "division", "sum", "product",
    "difference", "average", "maximum", "minimum", "total", "count",
    "database", "table", "query", "index", "schema", "model", "server",
    "client", "request", "response", "endpoint", "authentication",
    "encryption", "hash", "token", "password", "login", "register",
    "network", "neural", "transformer", "attention", "learning", "training",
    "machine", "deep", "supervised", "unsupervised", "reinforcement",
    "chatbot", "prompt", "function", "variable", "array", "string",
    "integer", "boolean", "object", "dictionary", "loop", "recursion",
    "memory", "thread", "process", "file", "read", "write", "delete",
    "update", "insert", "select", "drop", "truncate", "salary", "highest",
    "second", "third", "lowest", "fibonacci", "factorial", "prime",
    "palindrome", "reverse", "binary", "stack", "queue", "tree", "graph",
    "matrix", "vector", "tensor", "gradient", "loss", "accuracy",
}

LOW_INFORMATION_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "into",
    "and", "or", "but", "so", "then", "because", "although", "while",
    "it", "its", "this", "that", "these", "those", "there", "here",
    "i", "me", "my", "we", "us", "our", "you", "your", "he", "him",
    "she", "her", "they", "them", "their", "give", "please", "can",
    "could", "would", "should", "want", "need", "like", "tell", "show",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "between", "among", "through", "during", "before", "after",
    "just", "also", "very", "really", "quite", "about", "some", "any",
}

MATH_OPERATORS = {"+", "-", "*", "/", "=", "<", ">", "^", "%", "!", "~"}

CODE_PUNCTUATION = {"(", ")", "{", "}", "[", "]", ";", ":", ".", ",", "=>", "->"}


def extract_features(token: str, position: int, total_tokens: int,
                     full_text: str = "", all_tokens: List[str] = None) -> Dict[str, float]:
    """
    Extract a feature vector for a single token.
    Returns a dictionary of feature name -> float score in [0, 1].
    """
    clean = token.lower().strip()
    clean_alpha = re.sub(r"^[^\w]+|[^\w]+$", "", clean)

    features = {}

    # 1. Token importance (length-based: longer tokens tend to carry more meaning)
    features["token_importance"] = min(len(clean_alpha) / 10.0, 1.0) if clean_alpha else 0.1

    # 2. Token position (relative position; first and last tokens often important)
    if total_tokens > 1:
        rel_pos = position / (total_tokens - 1)
        # U-shaped: beginning and end more important
        features["position_score"] = 1.0 - 2.0 * abs(rel_pos - 0.5) * 0.3
    else:
        features["position_score"] = 1.0

    # 3. Keyword relevance
    if clean_alpha in NEGATION_TOKENS:
        features["keyword_relevance"] = 1.0
    elif clean_alpha in PROGRAMMING_ENTITIES:
        features["keyword_relevance"] = 0.95
    elif clean_alpha in HIGH_INFORMATION_KEYWORDS:
        features["keyword_relevance"] = 0.90
    elif clean_alpha in LOW_INFORMATION_WORDS:
        features["keyword_relevance"] = 0.15
    else:
        features["keyword_relevance"] = 0.55

    # 4. Context relevance (check if token appears in meaningful context)
    features["context_relevance"] = _compute_context_relevance(
        clean_alpha, position, all_tokens or [], full_text
    )

    # 5. Semantic contribution
    features["semantic_contribution"] = _compute_semantic_contribution(clean_alpha, full_text)

    # 6. Technical importance
    features["technical_importance"] = 1.0 if clean_alpha in PROGRAMMING_ENTITIES else (
        0.8 if clean_alpha in HIGH_INFORMATION_KEYWORDS else 0.3
    )

    # 7. Code-related importance
    if token in MATH_OPERATORS or token in CODE_PUNCTUATION:
        features["code_importance"] = 0.85
    elif re.match(r"^[A-Z_][a-zA-Z0-9_]*$", token):  # CamelCase or UPPER_CASE
        features["code_importance"] = 0.90
    else:
        features["code_importance"] = 0.4

    # 8. Numeric importance
    if re.match(r"^\d+(\.\d+)?$", clean_alpha):
        features["numeric_importance"] = 0.92
    elif re.match(r"^\d+(st|nd|rd|th)$", clean_alpha):
        features["numeric_importance"] = 0.90
    elif token in MATH_OPERATORS:
        features["numeric_importance"] = 0.88
    else:
        features["numeric_importance"] = 0.3

    return features


def _compute_context_relevance(token: str, position: int,
                               all_tokens: List[str], full_text: str) -> float:
    """Compute context relevance based on neighboring tokens."""
    if not all_tokens or not token:
        return 0.5

    score = 0.5

    # Check if neighboring tokens are high-value
    for offset in [-2, -1, 1, 2]:
        idx = position + offset
        if 0 <= idx < len(all_tokens):
            neighbor = all_tokens[idx].lower().strip()
            neighbor_clean = re.sub(r"^[^\w]+|[^\w]+$", "", neighbor)
            if neighbor_clean in HIGH_INFORMATION_KEYWORDS or neighbor_clean in PROGRAMMING_ENTITIES:
                score += 0.1

    # Subword check: is this token part of a compound programming entity?
    if full_text:
        words = [re.sub(r"^[^\w]+|[^\w]+$", "", w.lower()) for w in full_text.split()]
        for word in words:
            if word in PROGRAMMING_ENTITIES and token in word and len(token) >= 2:
                score = max(score, 0.90)
            if word in HIGH_INFORMATION_KEYWORDS and token in word and len(token) >= 2:
                score = max(score, 0.85)

    return min(score, 1.0)


def _compute_semantic_contribution(token: str, full_text: str) -> float:
    """Estimate semantic contribution of a token to overall meaning."""
    if not token:
        return 0.2

    # Negation words have highest semantic contribution (meaning inversion)
    if token in NEGATION_TOKENS:
        return 1.0

    # Programming entities are semantically critical
    if token in PROGRAMMING_ENTITIES:
        return 0.95

    # Domain keywords carry high semantic load
    if token in HIGH_INFORMATION_KEYWORDS:
        return 0.88

    # Numbers carry factual information
    if re.match(r"^\d+(\.\d+)?$", token):
        return 0.90

    # Stop words carry minimal semantic content
    if token in LOW_INFORMATION_WORDS:
        return 0.20

    # General content words
    if len(token) >= 4:
        return 0.70
    elif len(token) >= 2:
        return 0.55
    else:
        return 0.30
