"""
Nexa AI — Filtering Service
Applies threshold-based token selection with semantic safety.

Workflow:
1. Receive token analysis with confidence scores
2. Apply threshold to classify tokens as Selected/Filtered
3. Protect critical tokens via semantic validator
4. Validate semantic preservation
5. Fall back to original prompt if safety check fails
"""

import time
from typing import List, Dict, Tuple

from services.tokenizer import NexaTokenizer
from services.confidence_evaluator import evaluate_all_tokens
from services.semantic_validator import validate_semantic_preservation, get_protected_tokens


# Module-level singleton tokenizer
_tokenizer = NexaTokenizer()


def get_tokenizer() -> NexaTokenizer:
    return _tokenizer


def filter_tokens(
    text: str,
    threshold: float = 0.50,
) -> Dict:
    """
    Complete token evaluation and filtering pipeline.

    Steps:
    1. Tokenize input text
    2. Extract features and compute confidence for each token
    3. Apply threshold-based selection
    4. Protect semantically critical tokens
    5. Validate semantic preservation
    6. Return complete analysis

    Returns a dictionary with all token metrics.
    """
    t0 = time.time()

    if not text or not text.strip():
        return _empty_result(threshold)

    # Step 1: Tokenize
    tokens = _tokenizer.tokenize(text)
    if not tokens:
        return _empty_result(threshold)

    # Step 2: Evaluate confidence for all tokens
    token_analysis = evaluate_all_tokens(tokens, text)

    # Step 3: Get protected token indices
    protected_indices = get_protected_tokens(tokens)

    # Step 4: Apply threshold with protection
    retained_tokens = []
    filtered_tokens = []

    for item in token_analysis:
        idx = item["id"]
        is_protected = idx in protected_indices
        meets_threshold = item["confidence"] >= threshold

        if meets_threshold or is_protected:
            item["status"] = "Selected"
            item["retained"] = True
            if is_protected and not meets_threshold:
                item["status"] = "Protected"
            retained_tokens.append(item["token"])
        else:
            item["status"] = "Filtered"
            item["retained"] = False
            filtered_tokens.append(item["token"])

    # Step 5: Guarantee at least one token retained
    if not retained_tokens and token_analysis:
        best = max(token_analysis, key=lambda x: x["confidence"])
        best["status"] = "Selected"
        best["retained"] = True
        retained_tokens.append(best["token"])
        if best["token"] in filtered_tokens:
            filtered_tokens.remove(best["token"])

    # Step 6: Semantic preservation check
    preservation_ok, preservation_msg = validate_semantic_preservation(
        tokens, retained_tokens, filtered_tokens
    )

    # If semantic check fails, use original prompt (fallback)
    semantic_fallback = not preservation_ok
    if semantic_fallback:
        # Restore all tokens as selected
        retained_tokens = list(tokens)
        filtered_tokens = []
        for item in token_analysis:
            item["status"] = "Selected (Fallback)"
            item["retained"] = True
        preservation_msg = f"Semantic fallback activated: {preservation_msg}. Original prompt preserved."

    # Step 7: Compute metrics
    original_count = len(tokens)
    selected_count = len(retained_tokens)
    filtered_count = original_count - selected_count
    reduction_pct = round((filtered_count / original_count) * 100, 2) if original_count > 0 else 0.0
    eval_time_ms = round((time.time() - t0) * 1000, 2)
    selected_text = " ".join(retained_tokens)

    # Compute overall message confidence
    if token_analysis:
        message_confidence = round(
            sum(item["confidence"] for item in token_analysis) / len(token_analysis) * 100, 1
        )
    else:
        message_confidence = 0.0

    return {
        "token_analysis": token_analysis,
        "original_tokens": original_count,
        "evaluated_tokens": original_count,
        "selected_tokens": selected_count,
        "filtered_tokens_count": filtered_count,
        "tokens_saved": filtered_count,
        "token_saving_percentage": reduction_pct,
        "reduction_percentage": reduction_pct,
        "retained_tokens": retained_tokens,
        "filtered_tokens": filtered_tokens,
        "confidence_threshold": threshold,
        "evaluator_latency_ms": eval_time_ms,
        "selected_text": selected_text,
        "original_text": text,
        "semantic_preservation_passed": preservation_ok or semantic_fallback,
        "semantic_preservation_message": preservation_msg,
        "semantic_fallback_activated": semantic_fallback,
        "message_confidence": message_confidence,
        "evaluation_type": "Baseline Confidence Evaluator (Weighted Feature Aggregation + Semantic Protection)",
    }


def recalculate_with_threshold(
    token_analysis: List[Dict],
    threshold: float,
) -> Dict:
    """
    Recalculate token selection with a new threshold.
    Uses existing confidence scores without re-evaluating.
    """
    tokens = [item.get("token", "") for item in token_analysis]
    protected_indices = get_protected_tokens(tokens)

    retained = []
    filtered = []
    updated_analysis = []

    for item in token_analysis:
        idx = item.get("id", 0)
        score = float(item.get("confidence", 0.0))
        is_protected = idx in protected_indices
        meets_threshold = score >= threshold

        new_item = {
            "id": idx,
            "token": item.get("token", ""),
            "confidence": score,
            "features": item.get("features", {}),
            "retained": meets_threshold or is_protected,
            "status": "Selected" if (meets_threshold or is_protected) else "Filtered",
        }
        if is_protected and not meets_threshold:
            new_item["status"] = "Protected"

        updated_analysis.append(new_item)

        if new_item["retained"]:
            retained.append(new_item["token"])
        else:
            filtered.append(new_item["token"])

    # Guarantee at least one retained
    if not retained and updated_analysis:
        best = max(updated_analysis, key=lambda x: x["confidence"])
        best["status"] = "Selected"
        best["retained"] = True
        retained.append(best["token"])
        if best["token"] in filtered:
            filtered.remove(best["token"])

    preservation_ok, preservation_msg = validate_semantic_preservation(
        tokens, retained, filtered
    )

    original_count = len(updated_analysis)
    selected_count = len(retained)
    filtered_count = original_count - selected_count
    reduction_pct = round((filtered_count / original_count) * 100, 2) if original_count > 0 else 0.0

    if updated_analysis:
        message_confidence = round(
            sum(item["confidence"] for item in updated_analysis) / len(updated_analysis) * 100, 1
        )
    else:
        message_confidence = 0.0

    return {
        "token_analysis": updated_analysis,
        "original_tokens": original_count,
        "evaluated_tokens": original_count,
        "selected_tokens": selected_count,
        "filtered_tokens_count": filtered_count,
        "tokens_saved": filtered_count,
        "token_saving_percentage": reduction_pct,
        "reduction_percentage": reduction_pct,
        "retained_tokens": retained,
        "filtered_tokens": filtered,
        "confidence_threshold": threshold,
        "selected_text": " ".join(retained),
        "semantic_preservation_passed": preservation_ok,
        "semantic_preservation_message": preservation_msg,
        "message_confidence": message_confidence,
    }


def _empty_result(threshold: float) -> Dict:
    """Return empty result for empty/whitespace input."""
    return {
        "token_analysis": [],
        "original_tokens": 0,
        "evaluated_tokens": 0,
        "selected_tokens": 0,
        "filtered_tokens_count": 0,
        "tokens_saved": 0,
        "token_saving_percentage": 0.0,
        "reduction_percentage": 0.0,
        "retained_tokens": [],
        "filtered_tokens": [],
        "confidence_threshold": threshold,
        "evaluator_latency_ms": 0.0,
        "selected_text": "",
        "original_text": "",
        "semantic_preservation_passed": True,
        "semantic_preservation_message": "Empty input",
        "semantic_fallback_activated": False,
        "message_confidence": 0.0,
        "evaluation_type": "Baseline Confidence Evaluator",
    }
