"""Pydantic models for Message and Chat documents."""

from pydantic import BaseModel, Field
from typing import Any, List, Optional


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(min_length=1, max_length=12000)
    threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    file_id: Optional[str] = None


class EvaluateRequest(BaseModel):
    text: str
    threshold: float = 0.50


class RecalculateRequest(BaseModel):
    token_analysis: List[dict]
    threshold: float = 0.50


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: Optional[str] = None
    status: Optional[str] = "completed"
    metrics: Optional[dict] = None
