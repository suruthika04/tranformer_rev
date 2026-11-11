"""
Nexa AI — Metrics Service
Tracks and reports performance metrics for token evaluation and AI response.
"""

import time
from typing import Dict, Optional


class MetricsCollector:
    """Collects timing and performance metrics for a single request."""

    def __init__(self):
        self._start_time = time.time()
        self._marks: Dict[str, float] = {}
        self._values: Dict[str, any] = {}

    def mark(self, name: str):
        """Record a timestamp mark."""
        self._marks[name] = time.time()

    def set(self, name: str, value):
        """Set a metric value."""
        self._values[name] = value

    def elapsed_since(self, name: str) -> float:
        """Get elapsed time since a mark in seconds."""
        if name in self._marks:
            return round(time.time() - self._marks[name], 3)
        return 0.0

    def total_elapsed(self) -> float:
        """Get total elapsed time since creation."""
        return round(time.time() - self._start_time, 3)

    def get_report(self) -> Dict:
        """Generate a complete metrics report."""
        report = {
            "total_time_seconds": self.total_elapsed(),
        }

        # Add timing marks as durations
        prev_time = self._start_time
        for name, mark_time in sorted(self._marks.items(), key=lambda x: x[1]):
            report[f"{name}_time_seconds"] = round(mark_time - prev_time, 3)
            prev_time = mark_time

        # Add custom values
        report.update(self._values)

        return report


def compute_response_metrics(
    eval_metrics: Dict,
    gemini_usage: Dict,
    generation_time: float,
    ttft: float,
    model_name: str,
) -> Dict:
    """Combine token evaluation and generation metrics into a unified report."""
    return {
        # Token evaluation metrics
        "original_tokens": eval_metrics.get("original_tokens", 0),
        "selected_tokens": eval_metrics.get("selected_tokens", 0),
        "filtered_tokens_count": eval_metrics.get("filtered_tokens_count", 0),
        "token_saving_percentage": eval_metrics.get("token_saving_percentage", 0.0),
        "evaluator_latency_ms": eval_metrics.get("evaluator_latency_ms", 0.0),
        "confidence_threshold": eval_metrics.get("confidence_threshold", 0.5),
        "message_confidence": eval_metrics.get("message_confidence", 0.0),
        "semantic_preservation_passed": eval_metrics.get("semantic_preservation_passed", True),

        # Generation metrics
        "generation_time_seconds": generation_time,
        "ttft_seconds": ttft,
        "model_name": model_name,

        # Gemini API usage (if available)
        "gemini_prompt_tokens": gemini_usage.get("prompt_token_count"),
        "gemini_completion_tokens": gemini_usage.get("candidates_token_count"),
        "gemini_total_tokens": gemini_usage.get("total_token_count"),
    }
