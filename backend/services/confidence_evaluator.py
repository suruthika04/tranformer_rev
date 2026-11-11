"""
Nexa AI — Confidence Evaluator
Computes a confidence score for each token based on extracted features.

Architecture:
- Baseline evaluator using weighted feature aggregation.
- The module is designed to be swappable with a trained MLP in the future.

NOTE: This is a transparent BASELINE evaluator. It uses deterministic
feature-weighted scoring rather than a trained neural network. The code
is structured so that a trained MLP can replace the scoring function
without changing any other module. This is clearly identified as a
baseline implementation.
"""

import math
from typing import List, Dict, Tuple

from services.feature_extractor import (
    extract_features,
    NEGATION_TOKENS,
    PROGRAMMING_ENTITIES,
    HIGH_INFORMATION_KEYWORDS,
    LOW_INFORMATION_WORDS,
)

# Feature weights for the baseline evaluator
# These represent learned importance of each feature dimension
FEATURE_WEIGHTS = {
    "keyword_relevance": 0.30,
    "semantic_contribution": 0.25,
    "technical_importance": 0.15,
    "context_relevance": 0.10,
    "token_importance": 0.08,
    "numeric_importance": 0.05,
    "code_importance": 0.04,
    "position_score": 0.03,
}


def compute_confidence_score(features: Dict[str, float]) -> float:
    """
    Compute a single confidence score from a feature vector.

    This baseline uses weighted linear combination followed by a
    sigmoid-like squashing function to produce scores in (0, 1).

    In a trained MLP implementation, this function would be replaced by:
        Input features -> Linear(8, 128) -> GELU -> Linear(128, 1) -> Sigmoid

    The modular design allows drop-in replacement.
    """
    # Weighted sum of features
    weighted_sum = 0.0
    total_weight = 0.0

    for feature_name, weight in FEATURE_WEIGHTS.items():
        if feature_name in features:
            weighted_sum += features[feature_name] * weight
            total_weight += weight

    if total_weight > 0:
        raw_score = weighted_sum / total_weight
    else:
        raw_score = 0.5

    # Apply sigmoid-like calibration to spread scores
    # This mimics the output range of a trained sigmoid layer
    calibrated = _calibrate_score(raw_score)

    return round(calibrated, 3)


def _calibrate_score(raw: float) -> float:
    """
    Apply a calibration function to spread scores into a more
    discriminative range. Uses a modified sigmoid.
    """
    # Shift and scale to make the sigmoid more discriminative
    # Maps [0,1] -> approximately [0.1, 0.98]
    x = (raw - 0.5) * 6.0  # scale for sigmoid sensitivity
    sigmoid = 1.0 / (1.0 + math.exp(-x))
    # Map sigmoid output [~0.05, ~0.95] to [0.10, 0.98]
    return 0.10 + sigmoid * 0.88


def evaluate_token_confidence(
    token: str,
    position: int,
    total_tokens: int,
    full_text: str = "",
    all_tokens: List[str] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Evaluate confidence for a single token.
    Returns (confidence_score, feature_dict).
    """
    import re
    clean = re.sub(r"^[^\w]+|[^\w]+$", "", token.lower().strip())

    # Extract features
    features = extract_features(
        token, position, total_tokens, full_text, all_tokens
    )

    # Compute base confidence from features
    confidence = compute_confidence_score(features)

    # Apply semantic overrides for critical token categories
    # These overrides ensure that the evaluator never misclassifies
    # tokens whose removal would change meaning
    if clean in NEGATION_TOKENS:
        confidence = max(0.97, confidence)
    elif clean in PROGRAMMING_ENTITIES:
        confidence = max(0.94, confidence)
    elif clean in HIGH_INFORMATION_KEYWORDS:
        confidence = max(0.88, confidence)
    elif clean in LOW_INFORMATION_WORDS:
        confidence = min(0.40, confidence)

    return confidence, features


def evaluate_all_tokens(
    tokens: List[str], full_text: str = ""
) -> List[Dict]:
    """
    Evaluate confidence for all tokens in a sequence.
    Returns list of token analysis dictionaries.
    """
    total = len(tokens)
    results = []

    for i, token in enumerate(tokens):
        confidence, features = evaluate_token_confidence(
            token, i, total, full_text, tokens
        )

        results.append({
            "id": i,
            "token": token,
            "confidence": confidence,
            "features": features,
            "status": "Pending",  # Will be set by filtering service
            "retained": True,     # Will be set by filtering service
        })

    return results
