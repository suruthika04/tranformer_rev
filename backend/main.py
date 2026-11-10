
"""
Nexa AI — Production FastAPI Backend
====================================
Features:
  - Google Gemini AI Streaming Engine
  - Confidence-Based Token Evaluator
  - JWT Authentication
  - MongoDB Atlas Persistence
  - Document & Image File Processing
  - User Data Isolation
  - SSE Streaming Responses
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, List, Optional

from dotenv import load_dotenv

# Load local environment without overriding Render variables
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path, override=False)

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from auth import (
    create_access_token,
    get_current_user,
    get_optional_user,
    hash_password,
    verify_password,
)
from database import close_db, connect_db, db_available, get_collection
from file_processor import build_document_context, extract_text
from model import TransformerEvaluatorService


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("nexa")


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Nexa AI",
    description="Confidence-Based Token Evaluator in Transformer Models",
    version="3.0.0",
)


# ============================================================
# CORS CONFIGURATION
# ============================================================

allowed_origins_raw = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)

allowed_origins = [
    origin.strip()
    for origin in allowed_origins_raw.split(",")
    if origin.strip() and origin.strip() != "*"
]

if not allowed_origins:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# MIDDLEWARE
# ============================================================

@app.middleware("http")
async def fix_duplicate_api_prefix(request: Request, call_next):
    if request.scope.get("path", "").startswith("/api/api/"):
        request.scope["path"] = request.scope["path"][4:]

    return await call_next(request)


# ============================================================
# GLOBAL SERVICES
# ============================================================

service: Optional[TransformerEvaluatorService] = None
service_init_task: Optional[asyncio.Task] = None


# ============================================================
# FILE CONFIGURATION
# ============================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

ALLOWED_DOC_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_FILE_BYTES = 25 * 1024 * 1024

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# STARTUP AND SHUTDOWN
# ============================================================

async def initialize_ai_service():
    global service

    try:
        logger.info("[Startup] Initializing AI service...")

        service = await asyncio.to_thread(
            TransformerEvaluatorService
        )

        logger.info(
            "[Startup] AI Service ready: model='%s' device='%s'",
            service.model_name,
            service.device,
        )

    except Exception:
        service = None
        logger.exception("[Startup] AI Service initialization failed.")


@app.on_event("startup")
async def startup_event():
    global service_init_task

    logger.info("[Startup] Connecting to MongoDB Atlas...")

    try:
        connected = await connect_db()

        if connected:
            logger.info("[Startup] MongoDB Atlas connected successfully.")
        else:
            logger.warning(
                "[Startup] MongoDB unavailable. "
                "Authentication and persistence are disabled."
            )

    except Exception:
        logger.exception("[Startup] MongoDB connection error.")

    # Start AI initialization in the background.
    # This prevents model loading from blocking FastAPI startup.
    service_init_task = asyncio.create_task(
        initialize_ai_service()
    )

    logger.info(
        "[Startup] FastAPI startup completed. "
        "AI initialization is running in the background."
    )


@app.on_event("shutdown")
async def shutdown_event():
    global service_init_task

    if service_init_task and not service_init_task.done():
        service_init_task.cancel()

        try:
            await service_init_task
        except asyncio.CancelledError:
            pass

    await close_db()

    logger.info("[Shutdown] Application stopped.")


# ============================================================
# REQUEST SCHEMAS
# ============================================================

class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None


class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(min_length=1, max_length=12000)
    threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    file_id: Optional[str] = None


class EvaluateRequest(BaseModel):
    text: str
    threshold: float = 0.50
    history: Optional[List[Any]] = None


class RecalculateRequest(BaseModel):
    token_analysis: List[dict]
    threshold: float = 0.50


# ============================================================
# COMMON HELPERS
# ============================================================

def now_utc():
    return datetime.now(timezone.utc)


def sanitize_user(doc: dict):
    created_at = doc.get("created_at", "")

    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()

    return {
        "id": str(doc.get("_id", "")),
        "name": doc.get("name", ""),
        "email": doc.get("email", ""),
        "created_at": str(created_at),
    }


async def get_file_context(file_id: str, user_id: str):
    if not db_available() or not file_id:
        return ""

    try:
        collection = get_collection("Uploded_collection")

        doc = await collection.find_one(
            {
                "file_id": file_id,
                "user_id": user_id,
            }
        )

        if doc:
            return doc.get("extracted_text", "")

    except Exception:
        logger.exception("[File] Failed to retrieve file context.")

    return ""


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
async def root():
    return {
        "application": "Nexa AI",
        "status": "running",
    }


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "model_loaded": service is not None,
        "model_name": service.model_name if service else "None",
        "device": service.device if service else "None",
        "gemini_connected": bool(
            service and service.gemini_client
        ),
        "db_connected": db_available(),
        "timestamp": now_utc().isoformat(),
    }


# ============================================================
# AUTHENTICATION
# ============================================================

@app.post("/api/auth/signup", status_code=201)
async def signup(req: SignupRequest):

    if not db_available():
        raise HTTPException(
            503,
            "Database unavailable. Cannot create account.",
        )

    email = req.email.strip().lower()
    users = get_collection("Users")

    existing = await users.find_one({"email": email})

    if existing:
        raise HTTPException(
            409,
            "An account with this email already exists.",
        )

    doc = {
        "name": req.name.strip(),
        "email": email,
        "password_hash": hash_password(req.password),
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "last_login_at": now_utc(),
    }

    result = await users.insert_one(doc)

    user_id = str(result.inserted_id)

    token = create_access_token(user_id, email)

    return {
        "token": token,
        "user": {
            "id": user_id,
            "name": doc["name"],
            "email": email,
        },
    }


@app.post("/api/auth/login")
async def login(req: LoginRequest):

    if not db_available():
        raise HTTPException(
            503,
            "Database unavailable. Authentication disabled.",
        )

    email = req.email.strip().lower()

    users = get_collection("Users")

    doc = await users.find_one({"email": email})

    if not doc or not verify_password(
        req.password,
        doc.get("password_hash", ""),
    ):
        raise HTTPException(
            401,
            "Incorrect email or password.",
        )

    user_id = str(doc["_id"])

    await users.update_one(
        {"_id": doc["_id"]},
        {"$set": {"last_login_at": now_utc()}},
    )

    token = create_access_token(user_id, email)

    return {
        "token": token,
        "user": sanitize_user(doc),
    }


@app.get("/api/auth/me")
async def get_me(
    current_user: dict = Depends(get_current_user),
):

    if not db_available():
        return current_user

    from bson import ObjectId

    users = get_collection("Users")

    try:
        doc = await users.find_one(
            {"_id": ObjectId(current_user["user_id"])}
        )
    except Exception:
        doc = None

    if not doc:
        raise HTTPException(404, "User not found.")

    return sanitize_user(doc)


# ============================================================
# CONVERSATIONS
# ============================================================

@app.get("/api/conversations")
async def list_conversations(
    current_user: dict = Depends(get_current_user),
):

    if not db_available():
        return []

    collection = get_collection("Conversation")

    cursor = collection.find(
        {"user_id": current_user["user_id"]},
        {
            "_id": 1,
            "title": 1,
            "created_at": 1,
            "updated_at": 1,
            "model_name": 1,
        },
    ).sort("updated_at", -1).limit(100)

    docs = await cursor.to_list(100)

    return [
        {
            "id": str(doc["_id"]),
            "title": doc.get("title", "New Conversation"),
            "model_name": doc.get(
                "model_name",
                service.model_name if service else "",
            ),
            "created_at": (
                doc.get("created_at").isoformat()
                if hasattr(doc.get("created_at"), "isoformat")
                else str(doc.get("created_at", ""))
            ),
            "updated_at": (
                doc.get("updated_at").isoformat()
                if hasattr(doc.get("updated_at"), "isoformat")
                else str(doc.get("updated_at", ""))
            ),
        }
        for doc in docs
    ]


@app.post("/api/conversations", status_code=201)
async def create_conversation(
    req: ConversationCreateRequest,
    current_user: dict = Depends(get_current_user),
):

    if not db_available():
        raise HTTPException(503, "Database unavailable.")

    collection = get_collection("Conversation")

    doc = {
        "user_id": current_user["user_id"],
        "title": req.title or "New Conversation",
        "model_name": service.model_name if service else "Gemini",
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }

    result = await collection.insert_one(doc)

    return {
        "id": str(result.inserted_id),
        "title": doc["title"],
    }


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):

    if not db_available():
        return []

    from bson import ObjectId

    conversations = get_collection("Conversation")

    try:
        conversation = await conversations.find_one(
            {"_id": ObjectId(conversation_id)}
        )
    except Exception:
        raise HTTPException(400, "Invalid conversation ID.")

    if not conversation:
        raise HTTPException(404, "Conversation not found.")

    if conversation.get("user_id") != current_user["user_id"]:
        raise HTTPException(
            403,
            "Access denied to this conversation.",
        )

    messages = get_collection("Message")

    cursor = messages.find(
        {"conversation_id": conversation_id}
    ).sort("created_at", 1).limit(200)

    docs = await cursor.to_list(200)

    return [
        {
            "id": str(doc["_id"]),
            "role": doc.get("role", ""),
            "content": doc.get("content", ""),
            "created_at": (
                doc.get("created_at").isoformat()
                if hasattr(doc.get("created_at"), "isoformat")
                else str(doc.get("created_at", ""))
            ),
            "status": doc.get("status", "completed"),
            "metrics": doc.get("metrics"),
        }
        for doc in docs
    ]


@app.patch("/api/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    req: ConversationRenameRequest,
    current_user: dict = Depends(get_current_user),
):

    if not db_available():
        raise HTTPException(503, "Database unavailable.")

    from bson import ObjectId

    collection = get_collection("Conversation")

    try:
        result = await collection.update_one(
            {
                "_id": ObjectId(conversation_id),
                "user_id": current_user["user_id"],
            },
            {
                "$set": {
                    "title": req.title.strip(),
                    "updated_at": now_utc(),
                }
            },
        )
    except Exception:
        raise HTTPException(400, "Invalid conversation ID.")

    if result.matched_count == 0:
        raise HTTPException(
            404,
            "Conversation not found or access denied.",
        )

    return {
        "ok": True,
        "title": req.title.strip(),
    }


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):

    if not db_available():
        raise HTTPException(503, "Database unavailable.")

    from bson import ObjectId

    conversations = get_collection("Conversation")
    messages = get_collection("Message")

    try:
        result = await conversations.delete_one(
            {
                "_id": ObjectId(conversation_id),
                "user_id": current_user["user_id"],
            }
        )
    except Exception:
        raise HTTPException(400, "Invalid conversation ID.")

    if result.deleted_count == 0:
        raise HTTPException(
            404,
            "Conversation not found or access denied.",
        )

    await messages.delete_many(
        {"conversation_id": conversation_id}
    )

    return {"ok": True}


# ============================================================
# GEMINI STREAMING CHAT
# ============================================================

async def stream_chat_sse(
    message: str,
    history: list,
    threshold: float,
    conversation_id: Optional[str],
    user_id: Optional[str],
    file_context: str = "",
) -> AsyncIterator[str]:

    if service is None:
        yield (
            "data: "
            + json.dumps({
                "type": "error",
                "message": "AI Service is initializing. Please retry shortly.",
            })
            + "\n\n"
        )
        return

    # Safety check
    safety = service.check_safety(message)

    if safety:
        yield (
            "data: "
            + json.dumps({
                "type": "token",
                "text": safety,
            })
            + "\n\n"
        )

        yield (
            "data: "
            + json.dumps({
                "type": "done",
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_seconds": 0.0,
                "ttft_seconds": 0.0,
            })
            + "\n\n"
        )

        return

    # Token evaluator
    eval_metrics = {}

    try:
        eval_metrics = service.evaluate_tokens(
            message,
            threshold=threshold,
        )

        yield (
            "data: "
            + json.dumps({
                "type": "eval",
                **eval_metrics,
            })
            + "\n\n"
        )

    except Exception:
        logger.exception("[SSE] Evaluator error.")

        eval_metrics = {
            "token_analysis": [],
            "original_tokens": len(message.split()),
            "selected_tokens": len(message.split()),
            "tokens_saved": 0,
            "token_saving_percentage": 0.0,
            "confidence_threshold": threshold,
        }

        yield (
            "data: "
            + json.dumps({
                "type": "eval",
                **eval_metrics,
            })
            + "\n\n"
        )

    # Gemini streaming
    start_time = time.time()
    first_token_time = None
    full_response = ""
    output_tokens_approx = 0
    gemini_usage = {}

    try:

        async for chunk in service.stream_gemini_response(
            message=message,
            history=history,
            file_context=file_context,
        ):

            chunk_type = chunk.get("type")

            if chunk_type == "token":

                if first_token_time is None:
                    first_token_time = round(
                        time.time() - start_time,
                        3,
                    )

                text = chunk.get("text", "")

                full_response += text
                output_tokens_approx += 1

                yield (
                    "data: "
                    + json.dumps({
                        "type": "token",
                        "text": text,
                    })
                    + "\n\n"
                )

                await asyncio.sleep(0)

            elif chunk_type == "usage":
                gemini_usage = chunk

            elif chunk_type == "error":

                yield (
                    "data: "
                    + json.dumps({
                        "type": "error",
                        "message": chunk.get("message", "Error"),
                    })
                    + "\n\n"
                )

                return

        total_latency = round(
            time.time() - start_time,
            3,
        )

        ttft = (
            first_token_time
            if first_token_time is not None
            else total_latency
        )

        if not full_response.strip():

            full_response = (
                "I have processed your message. "
                "How can I assist you further?"
            )

            yield (
                "data: "
                + json.dumps({
                    "type": "token",
                    "text": full_response,
                })
                + "\n\n"
            )

        # Save assistant response
        if db_available() and conversation_id and user_id:

            try:
                from bson import ObjectId

                messages = get_collection("Message")

                await messages.insert_one({
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "role": "assistant",
                    "content": full_response,
                    "created_at": now_utc(),
                    "status": "completed",
                    "metrics": {
                        "input_tokens": eval_metrics.get(
                            "original_tokens",
                            len(message.split()),
                        ),
                        "output_tokens": output_tokens_approx,
                        "latency_seconds": total_latency,
                        "ttft_seconds": ttft,
                        "model_name": service.model_name,
                        "gemini_usage": gemini_usage,
                        **eval_metrics,
                    },
                })

                conversations = get_collection("Conversation")

                conversation = await conversations.find_one(
                    {"_id": ObjectId(conversation_id)}
                )

                update_fields = {
                    "updated_at": now_utc(),
                }

                if conversation and conversation.get("title") in (
                    "New Conversation",
                    None,
                    "",
                ):

                    auto_title = message.strip()[:50]

                    if len(message.strip()) > 50:
                        auto_title += "…"

                    update_fields["title"] = auto_title

                await conversations.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$set": update_fields},
                )

            except Exception:
                logger.exception("[SSE] Database persistence error.")

        # Final metrics
        done_payload = {
            "type": "done",
            "input_tokens": eval_metrics.get(
                "original_tokens",
                len(message.split()),
            ),
            "output_tokens": output_tokens_approx,
            "latency_seconds": total_latency,
            "ttft_seconds": ttft,
            "model_name": service.model_name,
            "gemini_usage": gemini_usage,
            "token_saving_percentage": eval_metrics.get(
                "token_saving_percentage",
                0.0,
            ),
            "selected_tokens_count": eval_metrics.get(
                "selected_tokens",
                0,
            ),
            "filtered_tokens_count": eval_metrics.get(
                "filtered_tokens_count",
                0,
            ),
            "selected_text": eval_metrics.get(
                "selected_text",
                "",
            ),
            "semantic_preservation_passed": eval_metrics.get(
                "semantic_preservation_passed",
                True,
            ),
            "semantic_preservation_message": eval_metrics.get(
                "semantic_preservation_message",
                "OK",
            ),
            "gemini_input_mode": eval_metrics.get(
                "gemini_input_mode",
                "Full Original Prompt Preserved",
            ),
        }

        yield (
            "data: "
            + json.dumps(done_payload)
            + "\n\n"
        )

    except Exception:
        logger.exception("[SSE] Generation exception.")

        yield (
            "data: "
            + json.dumps({
                "type": "error",
                "message": "Generation failed. Please try again.",
            })
            + "\n\n"
        )


@app.post("/api/chat/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: Optional[dict] = Depends(get_optional_user),
):

    user_id = (
        current_user["user_id"]
        if current_user
        else None
    )

    conversation_id = req.conversation_id

    threshold = max(
        0.0,
        min(1.0, float(req.threshold)),
    )

    history = []

    # Load conversation history
    if db_available() and conversation_id and user_id:

        try:
            from bson import ObjectId

            conversations = get_collection("Conversation")

            conversation = await conversations.find_one(
                {"_id": ObjectId(conversation_id)}
            )

            if (
                not conversation
                or conversation.get("user_id") != user_id
            ):
                raise HTTPException(
                    403,
                    "Access denied to this conversation.",
                )

            messages = get_collection("Message")

            cursor = messages.find(
                {"conversation_id": conversation_id}
            ).sort("created_at", 1).limit(16)

            docs = await cursor.to_list(16)

            history = [
                {
                    "role": doc["role"],
                    "content": doc["content"],
                }
                for doc in docs
            ]

        except HTTPException:
            raise

        except Exception:
            logger.exception("[Chat] History loading failed.")

    # Save user message
    if db_available() and conversation_id and user_id:

        try:
            messages = get_collection("Message")

            await messages.insert_one({
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": "user",
                "content": req.message,
                "created_at": now_utc(),
                "status": "completed",
            })

        except Exception:
            logger.exception("[Chat] User message save failed.")

    # File context
    file_context = ""

    if req.file_id and user_id:

        file_context = await get_file_context(
            req.file_id,
            user_id,
        )

        if file_context:
            file_context = build_document_context(
                file_context,
                req.message,
            )

    return StreamingResponse(
        stream_chat_sse(
            req.message,
            history,
            threshold,
            conversation_id,
            user_id,
            file_context,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ============================================================
# EVALUATION
# ============================================================

@app.post("/api/evaluate")
async def evaluate_text_endpoint(req: EvaluateRequest):

    if service is None:
        raise HTTPException(
            503,
            "Model service is initializing. Please retry shortly.",
        )

    threshold = max(
        0.0,
        min(1.0, float(req.threshold)),
    )

    try:
        return service.evaluate_text(
            req.text,
            threshold,
            req.history,
        )

    except Exception:
        logger.exception("[Evaluate] Inference error.")

        raise HTTPException(
            500,
            "Inference failed.",
        )


@app.post("/api/recalculate")
async def recalculate_metrics(req: RecalculateRequest):

    threshold = max(
        0.0,
        min(1.0, float(req.threshold)),
    )

    token_analysis = req.token_analysis

    retained_tokens = []
    filtered_tokens = []
    updated_analysis = []

    for item in token_analysis:

        score = float(item.get("confidence", 0.0))

        is_retained = score >= threshold

        updated_item = {
            "id": item.get("id"),
            "token": item.get("token"),
            "confidence": score,
            "status": (
                "Retained"
                if is_retained
                else "Filtered"
            ),
            "retained": is_retained,
        }

        updated_analysis.append(updated_item)

        if is_retained:
            retained_tokens.append(item.get("token"))
        else:
            filtered_tokens.append(item.get("token"))

    # Keep at least one token
    if not retained_tokens and updated_analysis:

        highest = max(
            updated_analysis,
            key=lambda item: item["confidence"],
        )

        highest["status"] = "Retained"
        highest["retained"] = True

        retained_tokens.append(highest["token"])

        if highest["token"] in filtered_tokens:
            filtered_tokens.remove(highest["token"])

    original_tokens = len(updated_analysis)
    selected_tokens = len(retained_tokens)

    tokens_saved = original_tokens - selected_tokens

    saving_percentage = (
        round(
            (tokens_saved / original_tokens) * 100,
            2,
        )
        if original_tokens > 0
        else 0.0
    )

    from evaluator import validate_semantic_preservation

    original_token_strings = [
        item.get("token", "")
        for item in updated_analysis
    ]

    preservation_ok, preservation_message = (
        validate_semantic_preservation(
            original_token_strings,
            retained_tokens,
            filtered_tokens,
        )
    )

    return {
        "token_analysis": updated_analysis,
        "original_tokens": original_tokens,
        "evaluated_tokens": original_tokens,
        "selected_tokens": selected_tokens,
        "tokens_saved": tokens_saved,
        "filtered_tokens_count": tokens_saved,
        "saving_percentage": saving_percentage,
        "token_saving_percentage": saving_percentage,
        "retained_tokens": retained_tokens,
        "filtered_tokens": filtered_tokens,
        "confidence_threshold": threshold,
        "selected_text": " ".join(retained_tokens),
        "semantic_preservation_passed": preservation_ok,
        "semantic_preservation_message": preservation_message,
    }


# ============================================================
# FILE UPLOAD
# ============================================================

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):

    content_type = file.content_type or "application/octet-stream"

    is_image = content_type in ALLOWED_IMAGE_TYPES

    filename = file.filename or "upload"

    is_doc = (
        content_type in ALLOWED_DOC_TYPES
        or any(
            filename.lower().endswith(extension)
            for extension in (
                ".txt",
                ".md",
                ".csv",
                ".json",
                ".pdf",
                ".docx",
            )
        )
    )

    if not (is_image or is_doc):
        raise HTTPException(
            415,
            "Unsupported file type. Allowed: PDF, DOCX, TXT, MD, CSV, JSON, PNG, JPG, WEBP.",
        )

    content = await file.read()

    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            413,
            "File exceeds maximum size of 25 MB.",
        )

    file_id = str(uuid.uuid4())

    safe_name = re.sub(
        r"[^\w.\-]",
        "_",
        filename,
    )

    store_path = os.path.join(
        UPLOAD_DIR,
        f"{file_id}_{safe_name}",
    )

    with open(store_path, "wb") as file_object:
        file_object.write(content)

    extracted_text = ""

    if is_doc:
        extracted_text = extract_text(
            filename,
            content,
        )

    # Store metadata in MongoDB
    if db_available():

        try:
            collection = get_collection("Uploded_collection")

            await collection.insert_one({
                "file_id": file_id,
                "user_id": current_user["user_id"],
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(content),
                "is_image": is_image,
                "is_document": is_doc,
                "extracted_text": extracted_text,
                "store_path": store_path,
                "created_at": now_utc(),
            })

        except Exception:
            logger.exception("[Upload] Database insert failed.")

    return {
        "file_id": file_id,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "is_image": is_image,
        "is_document": is_doc,
        "has_extracted_text": bool(extracted_text),
        "preview_text": (
            extracted_text[:300]
            if extracted_text
            else None
        ),
    }


@app.get("/api/files")
async def list_files(
    current_user: dict = Depends(get_current_user),
):

    if not db_available():
        return []

    collection = get_collection("Uploded_collection")

    cursor = collection.find(
        {"user_id": current_user["user_id"]},
        {
            "_id": 1,
            "file_id": 1,
            "filename": 1,
            "content_type": 1,
            "size_bytes": 1,
            "is_image": 1,
            "created_at": 1,
        },
    ).sort("created_at", -1).limit(50)

    docs = await cursor.to_list(50)

    return [
        {
            "id": str(doc["_id"]),
            "file_id": doc.get("file_id"),
            "filename": doc.get("filename"),
            "content_type": doc.get("content_type"),
            "size_bytes": doc.get("size_bytes"),
            "is_image": doc.get("is_image", False),
            "created_at": (
                doc.get("created_at").isoformat()
                if hasattr(doc.get("created_at"), "isoformat")
                else str(doc.get("created_at", ""))
            ),
        }
        for doc in docs
    ]


@app.delete("/api/files/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
):

    if not db_available():
        raise HTTPException(
            503,
            "Database unavailable.",
        )

    collection = get_collection("Uploded_collection")

    doc = await collection.find_one(
        {
            "file_id": file_id,
            "user_id": current_user["user_id"],
        }
    )

    if not doc:
        raise HTTPException(
            404,
            "File not found or access denied.",
        )

    store_path = doc.get("store_path")

    if store_path and os.path.exists(store_path):

        try:
            os.remove(store_path)
        except Exception:
            logger.exception("[File] Local file deletion failed.")

    await collection.delete_one(
        {"_id": doc["_id"]}
    )

    return {
        "ok": True,
        "file_id": file_id,
    }


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
