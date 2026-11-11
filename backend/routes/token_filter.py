"""
Nexa AI — Token Filter Routes
Standalone evaluate and recalculate endpoints for token analysis.
"""

import logging
from fastapi import APIRouter, HTTPException

from models.message import EvaluateRequest, RecalculateRequest
from services.filtering_service import filter_tokens, recalculate_with_threshold
from services.gemini_service import generate_async, is_available

logger = logging.getLogger("nexa.routes.token_filter")
router = APIRouter(tags=["Token Filtering"])


@router.post("/api/evaluate")
@router.post("/api/token-filter/evaluate")
async def evaluate_text_endpoint(req: EvaluateRequest):
    """Evaluate tokens and optionally generate AI response."""
    threshold = max(0.0, min(1.0, float(req.threshold)))
    try:
        result = filter_tokens(req.text, threshold)

        # Also generate a Gemini response using non-blocking async call
        if is_available():
            gen = await generate_async(req.text)
            result["answer"] = gen["response"]
            result["chatbot_response"] = gen["response"]
            result["latency_seconds"] = gen["latency"]
        else:
            result["answer"] = "Gemini API not configured."
            result["chatbot_response"] = "Gemini API not configured."
            result["latency_seconds"] = 0.0

        return result
    except Exception as exc:
        logger.error(f"[evaluate] Error: {exc}")
        raise HTTPException(500, f"Evaluation error: {str(exc)}")


@router.post("/api/recalculate")
@router.post("/api/token-filter/recalculate")
async def recalculate_endpoint(req: RecalculateRequest):
    """Recalculate token selection with a new threshold."""
    threshold = max(0.0, min(1.0, float(req.threshold)))
    try:
        return recalculate_with_threshold(req.token_analysis, threshold)
    except Exception as exc:
        logger.error(f"[recalculate] Error: {exc}")
        raise HTTPException(500, f"Recalculation error: {str(exc)}")
