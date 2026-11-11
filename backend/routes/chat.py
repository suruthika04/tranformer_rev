"""
Nexa AI — Chat Routes (SSE Streaming)
Handles streaming chat with token evaluation + Gemini AI.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from auth import get_current_user, get_optional_user
from database import db_available, get_collection
from models.message import ChatRequest
from services import filtering_service, gemini_service
from services.metrics_service import compute_response_metrics
from config import settings

logger = logging.getLogger("nexa.routes.chat")
router = APIRouter(prefix="/api/chat", tags=["Chat"])


def now_utc():
    return datetime.now(timezone.utc)


async def _stream_chat_sse(
    message: str,
    history: list,
    threshold: float,
    conversation_id: Optional[str],
    user_id: Optional[str],
):
    """
    SSE generator:
    1. Evaluates input tokens using confidence evaluator
    2. Sends 'eval' event with token analysis
    3. Streams response from Gemini
    4. Sends 'done' event with performance metrics
    """
    # 1. Token Evaluation
    eval_metrics = {}
    try:
        eval_metrics = filtering_service.filter_tokens(message, threshold=threshold)
        yield f"data: {json.dumps({'type': 'eval', **eval_metrics}, default=str)}\n\n"
    except Exception as exc:
        logger.warning(f"[SSE] Evaluator error: {exc}")
        eval_metrics = {
            "token_analysis": [],
            "original_tokens": len(message.split()),
            "selected_tokens": len(message.split()),
            "tokens_saved": 0,
            "token_saving_percentage": 0.0,
            "confidence_threshold": threshold,
            "message_confidence": 0.0,
        }
        yield f"data: {json.dumps({'type': 'eval', **eval_metrics})}\n\n"

    # 2. Stream Gemini response
    t0 = time.time()
    first_token_time = None
    full_response = ""
    output_tokens_approx = 0
    gemini_usage = {}

    try:
        async for chunk in gemini_service.stream_response(
            message=message,
            history=history,
        ):
            c_type = chunk.get("type")
            if c_type == "token":
                if first_token_time is None:
                    first_token_time = round(time.time() - t0, 3)
                text = chunk.get("text", "")
                full_response += text
                output_tokens_approx += 1
                yield f"data: {json.dumps({'type': 'token', 'text': text})}\n\n"
                await asyncio.sleep(0)
            elif c_type == "usage":
                gemini_usage = chunk
            elif c_type == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': chunk.get('message', 'Error')})}\n\n"
                return

        total_latency = round(time.time() - t0, 3)
        ttft = first_token_time if first_token_time is not None else total_latency

        if not full_response.strip():
            full_response = "I have processed your message. How can I assist you further?"
            yield f"data: {json.dumps({'type': 'token', 'text': full_response})}\n\n"

        # 3. Persist to MongoDB
        if db_available() and conversation_id and user_id:
            try:
                msg_col = get_collection("Message")
                metrics = compute_response_metrics(
                    eval_metrics, gemini_usage, total_latency, ttft, settings.GEMINI_MODEL
                )
                await msg_col.insert_one({
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "role": "assistant",
                    "content": full_response,
                    "created_at": now_utc(),
                    "status": "completed",
                    "metrics": metrics,
                })

                # Auto-title conversation
                conv_col = get_collection("Conversation")
                conv = await conv_col.find_one({"_id": ObjectId(conversation_id)})
                update_fields = {"updated_at": now_utc()}
                if conv and conv.get("title") in ("New Conversation", None, ""):
                    auto_title = message.strip()[:50]
                    if len(message.strip()) > 50:
                        auto_title += "..."
                    update_fields["title"] = auto_title
                await conv_col.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$set": update_fields},
                )
            except Exception as db_exc:
                logger.warning(f"[SSE] DB persist error: {db_exc}")

        # 4. Done event
        done_payload = {
            "type": "done",
            "input_tokens": eval_metrics.get("original_tokens", 0),
            "output_tokens": output_tokens_approx,
            "latency_seconds": total_latency,
            "ttft_seconds": ttft,
            "model_name": settings.GEMINI_MODEL,
            "gemini_usage": gemini_usage,
            "token_saving_percentage": eval_metrics.get("token_saving_percentage", 0.0),
            "selected_tokens_count": eval_metrics.get("selected_tokens", 0),
            "filtered_tokens_count": eval_metrics.get("filtered_tokens_count", 0),
            "selected_text": eval_metrics.get("selected_text", ""),
            "message_confidence": eval_metrics.get("message_confidence", 0.0),
            "semantic_preservation_passed": eval_metrics.get("semantic_preservation_passed", True),
            "semantic_preservation_message": eval_metrics.get("semantic_preservation_message", "OK"),
            "semantic_fallback_activated": eval_metrics.get("semantic_fallback_activated", False),
        }
        yield f"data: {json.dumps(done_payload)}\n\n"

    except Exception as exc:
        logger.error(f"[SSE] Generation exception: {exc}")
        yield f"data: {json.dumps({'type': 'error', 'message': f'Generation error: {str(exc)}'})}\n\n"


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """Primary SSE streaming chat endpoint."""
    user_id = current_user["user_id"] if current_user else None
    conversation_id = req.conversation_id
    threshold = max(0.0, min(1.0, float(req.threshold)))

    # Load conversation history
    history = []
    if db_available() and conversation_id and user_id:
        try:
            conv_col = get_collection("Conversation")
            conv = await conv_col.find_one({"_id": ObjectId(conversation_id)})
            if not conv or conv.get("user_id") != user_id:
                raise HTTPException(403, "Access denied to this conversation.")

            msg_col = get_collection("Message")
            cursor = msg_col.find(
                {"conversation_id": conversation_id}
            ).sort("created_at", 1).limit(16)
            docs = await cursor.to_list(16)
            history = [{"role": d["role"], "content": d["content"]} for d in docs]
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"[Chat] History load error: {exc}")

    # Save user message
    if db_available() and conversation_id and user_id:
        try:
            msg_col = get_collection("Message")
            await msg_col.insert_one({
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": "user",
                "content": req.message,
                "created_at": now_utc(),
                "status": "completed",
            })
        except Exception as exc:
            logger.warning(f"[Chat] User message save error: {exc}")

    return StreamingResponse(
        _stream_chat_sse(req.message, history, threshold, conversation_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
