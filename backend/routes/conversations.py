"""
Nexa AI — Conversation Routes
CRUD operations for conversations with user-specific access control.
"""

import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from database import db_available, get_collection
from models.conversation import ConversationCreateRequest, ConversationRenameRequest
from config import settings

logger = logging.getLogger("nexa.routes.conversations")
router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


def now_utc():
    return datetime.now(timezone.utc)


@router.get("")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    if not db_available():
        return []
    col = get_collection("Conversation")
    cursor = col.find(
        {"user_id": current_user["user_id"]},
        {"_id": 1, "title": 1, "created_at": 1, "updated_at": 1, "model_name": 1},
    ).sort("updated_at", -1).limit(100)
    docs = await cursor.to_list(100)
    return [
        {
            "id": str(d["_id"]),
            "title": d.get("title", "New Conversation"),
            "model_name": d.get("model_name", settings.GEMINI_MODEL),
            "created_at": d.get("created_at", "").isoformat()
            if hasattr(d.get("created_at", ""), "isoformat")
            else str(d.get("created_at", "")),
            "updated_at": d.get("updated_at", "").isoformat()
            if hasattr(d.get("updated_at", ""), "isoformat")
            else str(d.get("updated_at", "")),
        }
        for d in docs
    ]


@router.post("", status_code=201)
async def create_conversation(
    req: ConversationCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    if not db_available():
        raise HTTPException(503, "Database unavailable.")
    col = get_collection("Conversation")
    doc = {
        "user_id": current_user["user_id"],
        "title": req.title or "New Conversation",
        "model_name": settings.GEMINI_MODEL,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    result = await col.insert_one(doc)
    return {"id": str(result.inserted_id), "title": doc["title"]}


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    if not db_available():
        return []

    conv_col = get_collection("Conversation")
    try:
        conv = await conv_col.find_one({"_id": ObjectId(conversation_id)})
    except Exception:
        raise HTTPException(400, "Invalid conversation ID.")

    if not conv:
        raise HTTPException(404, "Conversation not found.")
    if conv.get("user_id") != current_user["user_id"]:
        raise HTTPException(403, "Access denied to this conversation.")

    msg_col = get_collection("Message")
    cursor = msg_col.find(
        {"conversation_id": conversation_id},
    ).sort("created_at", 1).limit(200)
    docs = await cursor.to_list(200)
    return [
        {
            "id": str(d["_id"]),
            "role": d.get("role", ""),
            "content": d.get("content", ""),
            "created_at": d.get("created_at", "").isoformat()
            if hasattr(d.get("created_at", ""), "isoformat")
            else str(d.get("created_at", "")),
            "status": d.get("status", "completed"),
            "metrics": d.get("metrics"),
        }
        for d in docs
    ]


@router.patch("/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    req: ConversationRenameRequest,
    current_user: dict = Depends(get_current_user),
):
    if not db_available():
        raise HTTPException(503, "Database unavailable.")
    conv_col = get_collection("Conversation")
    try:
        result = await conv_col.update_one(
            {"_id": ObjectId(conversation_id), "user_id": current_user["user_id"]},
            {"$set": {"title": req.title.strip(), "updated_at": now_utc()}},
        )
    except Exception:
        raise HTTPException(400, "Invalid conversation ID.")
    if result.matched_count == 0:
        raise HTTPException(404, "Conversation not found or access denied.")
    return {"ok": True, "title": req.title.strip()}


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    if not db_available():
        raise HTTPException(503, "Database unavailable.")
    conv_col = get_collection("Conversation")
    msg_col = get_collection("Message")
    try:
        result = await conv_col.delete_one(
            {"_id": ObjectId(conversation_id), "user_id": current_user["user_id"]}
        )
    except Exception:
        raise HTTPException(400, "Invalid conversation ID.")
    if result.deleted_count == 0:
        raise HTTPException(404, "Conversation not found or access denied.")
    await msg_col.delete_many({"conversation_id": conversation_id})
    return {"ok": True}
