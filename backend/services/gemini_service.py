"""
Nexa AI — Gemini AI Service
Integrates with Google Gemini API for chat response generation.
Uses the official google-genai SDK with async streaming support.
"""

import asyncio
import logging
import os
import time
from typing import AsyncIterator, Dict, List, Optional

from config import settings

logger = logging.getLogger("nexa.gemini")

# Singleton Gemini client
_gemini_client = None
_client_initialized = False


def _init_client():
    """Initialize the Gemini client (singleton)."""
    global _gemini_client, _client_initialized

    if _client_initialized:
        return _gemini_client

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.warning("[Gemini] API key not configured.")
        _client_initialized = True
        return None

    try:
        from google import genai
        _gemini_client = genai.Client(api_key=api_key)
        logger.info(f"[Gemini] Client initialized. Model: {settings.GEMINI_MODEL}")
    except Exception as exc:
        logger.error(f"[Gemini] Client initialization failed: {exc}")
        _gemini_client = None

    _client_initialized = True
    return _gemini_client


def get_client():
    """Get or initialize the Gemini client."""
    return _init_client()


def is_available() -> bool:
    """Check if Gemini is configured and available."""
    return get_client() is not None


def format_prompt(
    message: str,
    history: Optional[List[Dict]] = None,
    file_context: str = "",
) -> str:
    """Format the conversation context into a prompt for Gemini."""
    parts = []

    system_instruction = (
        "You are Nexa AI, a helpful, intelligent, and technically accurate AI assistant.\n"
        "Provide clean, direct, informative answers with proper markdown formatting when appropriate.\n"
        "Use code blocks with language tags for code examples."
    )
    parts.append(system_instruction)

    if file_context and file_context.strip():
        parts.append(
            f"\n--- ATTACHED DOCUMENT CONTEXT ---\n{file_context.strip()}\n"
            "Answer queries based on the document context when relevant.\n--- END CONTEXT ---"
        )

    if history:
        parts.append("\n--- CONVERSATION HISTORY ---")
        for turn in history[-10:]:
            if isinstance(turn, dict):
                role = turn.get("role", "user")
                content = (turn.get("content") or "").strip()
                if content:
                    label = "User" if role == "user" else "Nexa AI"
                    parts.append(f"{label}: {content}")
        parts.append("--- END HISTORY ---\n")

    parts.append(f"User: {message.strip()}\nNexa AI:")
    return "\n\n".join(parts)


async def stream_response(
    message: str,
    history: Optional[List[Dict]] = None,
    file_context: str = "",
) -> AsyncIterator[Dict]:
    """
    Async streaming response generator using Google Gemini.
    Yields dict chunks: {"type": "token", "text": "..."} or {"type": "usage", ...}
    Supports resilient model fallback if a specific model encounters temporary capacity spikes.
    """
    client = get_client()
    if not client:
        yield {"type": "error", "message": "Gemini API not configured. Check GEMINI_API_KEY."}
        return

    formatted = format_prompt(message, history, file_context)
    
    # Model candidate order: primary configured model first, followed by stable flash fallbacks
    candidate_models = [settings.GEMINI_MODEL]
    for alt in ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    stream_started = False
    last_err = ""

    for model in candidate_models:
        try:
            logger.info(f"[Gemini] Attempting generation with model: {model}")
            stream = await client.aio.models.generate_content_stream(
                model=model,
                contents=formatted,
            )

            async for chunk in stream:
                if chunk.text:
                    stream_started = True
                    yield {"type": "token", "text": chunk.text}

                # Capture usage metadata on final chunk
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    yield {
                        "type": "usage",
                        "prompt_token_count": getattr(chunk.usage_metadata, "prompt_token_count", None),
                        "candidates_token_count": getattr(chunk.usage_metadata, "candidates_token_count", None),
                        "total_token_count": getattr(chunk.usage_metadata, "total_token_count", None),
                        "model_used": model,
                    }
            
            # Successfully completed stream
            return

        except Exception as exc:
            last_err = str(exc)
            logger.warning(f"[Gemini] Model '{model}' error: {last_err}")
            # If we already sent partial tokens, do not retry with another model (avoid duplicated prefix)
            if stream_started:
                yield {"type": "error", "message": f"Stream interrupted on {model}: {last_err}"}
                return

    # If all candidate models failed before streaming any tokens
    yield {"type": "error", "message": f"Gemini API error on all models: {last_err}"}


async def generate_async(
    message: str,
    history: Optional[List[Dict]] = None,
) -> Dict:
    """Async Gemini response using client.aio for non-blocking execution in FastAPI routes."""
    client = get_client()
    if not client:
        return {"response": "Gemini API not configured.", "latency": 0.0}

    t0 = time.time()
    formatted = format_prompt(message, history)

    candidate_models = [settings.GEMINI_MODEL]
    for alt in ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    last_err = ""
    for model in candidate_models:
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=formatted,
            )
            latency = round(time.time() - t0, 3)
            text = response.text or "I have processed your query."
            return {"response": text, "latency": latency, "model_used": model}
        except Exception as exc:
            last_err = str(exc)
            logger.warning(f"[Gemini] Async '{model}' error: {last_err}")

    latency = round(time.time() - t0, 3)
    return {"response": f"Generation error: {last_err}", "latency": latency}


def generate_sync(
    message: str,
    history: Optional[List[Dict]] = None,
) -> Dict:
    """Synchronous (non-streaming) Gemini response with resilient fallback."""
    client = get_client()
    if not client:
        return {"response": "Gemini API not configured.", "latency": 0.0}

    t0 = time.time()
    formatted = format_prompt(message, history)

    candidate_models = [settings.GEMINI_MODEL]
    for alt in ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    last_err = ""
    for model in candidate_models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=formatted,
            )
            latency = round(time.time() - t0, 3)
            text = response.text or "I have processed your query."
            return {"response": text, "latency": latency, "model_used": model}
        except Exception as exc:
            last_err = str(exc)
            logger.warning(f"[Gemini] Sync '{model}' error: {last_err}")

    latency = round(time.time() - t0, 3)
    return {"response": f"Generation error: {last_err}", "latency": latency}
