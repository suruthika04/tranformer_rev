"""Pydantic models for Conversation documents."""

from pydantic import BaseModel, Field
from typing import Optional


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None


class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationResponse(BaseModel):
    id: str
    title: str
    model_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
