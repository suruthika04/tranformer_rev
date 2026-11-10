"""
Nexa AI — Production FastAPI Backend
====================================
Features:
  - Official Google Gemini AI Streaming Engine (google-genai async client)
  - Confidence-Based Token Evaluator (PyTorch MLP: Embedding -> Linear -> GELU -> Linear -> Sigmoid)
  - JWT Authentication & Bcrypt Password Hashing
  - MongoDB Atlas Cloud Persistence (Users, Conversation, Message, Uploaded_collection)
  - Document & Image File Processing (PDF, DOCX, TXT, CSV, JSON)
  - User Data Isolation & Ownership Validation
  - SSE Streaming Responses with TTFT and Token Metrics
"""

import asyncio
import io
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

# Local modules
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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("nexa")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Nexa AI",
    description="Confidence-Based Token Evaluator in Transformer Models — Production Chatbot API",
    version="3.0.0",
)

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip() and o.strip() != "*"]
if not allowed_origins:
    allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def fix_duplicate_api_prefix(request: Request, call_next):
    """Seamlessly normalize /api/api/... paths if client has base /api + path /api."""
    if request.scope.get("path", "").startswith("/api/api/"):
        request.scope["path"] = request.scope["path"][4:]
    return await call_next(request)

# ---------------------------------------------------------------------------
# Model Service Singleton (Loaded once at startup)
# ---------------------------------------------------------------------------
service: Optional[TransformerEvaluatorService] = None

# ---------------------------------------------------------------------------
# Upload Config
# ---------------------------------------------------------------------------
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_DOC_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Startup / Shutdown Events
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    global service
    # 1. Connect MongoDB Atlas
    ok = await connect_db()
    if ok:
        logger.info("[Startup] MongoDB Atlas connected successfully.")
    else:
        logger.warning("[Startup] Running without MongoDB. Auth and chat persistence disabled.")

    # 2. Initialize AI & Evaluator Service
    try:
        service = TransformerEvaluatorService()
        logger.info(
            f"[Startup] AI Service ready: model='{service.model_name}' on device='{service.device}'"
        )
    except Exception as exc:
        logger.error(f"[Startup] AI Service initialization failed: {exc}")


@app.on_event("shutdown")
async def shutdown_event():
    await close_db()


# ===========================================================================
# SCHEMAS
# ===========================================================================
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


# ===========================================================================
# HELPERS
# ===========================================================================
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize_user(doc: dict) -> dict:
    """Return user dict safe for API response (never exposing password hash)."""
    return {
        "id": str(doc.get("_id", "")),
        "name": doc.get("name", ""),
        "email": doc.get("email", ""),
        "created_at": doc.get("created_at", "").isoformat()
        if hasattr(doc.get("created_at", ""), "isoformat")
        else str(doc.get("created_at", "")),
    }


async def _get_file_context(file_id: str, user_id: str) -> str:
    """Retrieve extracted text for a file owned by user."""
    if not db_available() or not file_id:
        return ""
    try:
        col = get_collection("Uploaded_collection")
        doc = await col.find_one({"file_id": file_id, "user_id": user_id})
        if doc:
            return doc.get("extracted_text", "")
    except Exception:
        pass
    return ""


# ===========================================================================
# HEALTH CHECK
# ===========================================================================
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "model_loaded": service is not None,
        "model_name": service.model_name if service else "None",
        "device": service.device if service else "None",
        "gemini_connected": bool(service and service.gemini_client),
        "db_connected": db_available(),
        "timestamp": now_utc().isoformat(),
    }


# ===========================================================================
# AUTHENTICATION (Against MongoDB Users Collection)
# ===========================================================================
@app.post("/api/auth/signup", status_code=201)
async def signup(req: SignupRequest):
    if not db_available():
        raise HTTPException(503, "Database unavailable. Cannot create account.")

    email_norm = req.email.strip().lower()
    users = get_collection("Users")

    # Duplicate email prevention
    existing = await users.find_one({"email": email_norm})
    if existing:
        raise HTTPException(409, "An account with this email already exists.")

    doc = {
        "name": req.name.strip(),
        "email": email_norm,
        "password_hash": hash_password(req.password),
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "last_login_at": now_utc(),
    }
    result = await users.insert_one(doc)
    user_id = str(result.inserted_id)
    token = create_access_token(user_id, email_norm)
    return {"token": token, "user": {"id": user_id, "name": doc["name"], "email": email_norm}}


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    if not db_available():
        raise HTTPException(503, "Database unavailable. Authentication disabled.")

    email_norm = req.email.strip().lower()
    users = get_collection("Users")
    doc = await users.find_one({"email": email_norm})

    if not doc or not verify_password(req.password, doc.get("password_hash", "")):
        raise HTTPException(401, "Incorrect email or password.")

    user_id = str(doc["_id"])
    await users.update_one({"_id": doc["_id"]}, {"$set": {"last_login_at": now_utc()}})
    token = create_access_token(user_id, email_norm)
    return {"token": token, "user": _sanitize_user(doc)}


@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    if not db_available():
        return current_user
    from bson import ObjectId
    users = get_collection("Users")
    try:
        doc = await users.find_one({"_id": ObjectId(current_user["user_id"])})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(404, "User not found.")
    return _sanitize_user(doc)


# ===========================================================================
# CONVERSATIONS (User Specific)
# ===========================================================================
@app.get("/api/conversations")
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
            "model_name": d.get("model_name", service.model_name if service else ""),
            "created_at": d.get("created_at", "").isoformat() if hasattr(d.get("created_at", ""), "isoformat") else str(d.get("created_at", "")),
            "updated_at": d.get("updated_at", "").isoformat() if hasattr(d.get("updated_at", ""), "isoformat") else str(d.get("updated_at", "")),
        }
        for d in docs
    ]


@app.post("/api/conversations", status_code=201)
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
        "model_name": service.model_name if service else "Gemini",
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    result = await col.insert_one(doc)
    return {"id": str(result.inserted_id), "title": doc["title"]}


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    if not db_available():
        return []
    from bson import ObjectId
    # Ownership verification
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
            "created_at": d.get("created_at", "").isoformat() if hasattr(d.get("created_at", ""), "isoformat") else str(d.get("created_at", "")),
            "status": d.get("status", "completed"),
            "metrics": d.get("metrics"),
        }
        for d in docs
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


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    if not db_available():
        raise HTTPException(503, "Database unavailable.")
    from bson import ObjectId
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
    # Cascade delete all messages in this conversation
    await msg_col.delete_many({"conversation_id": conversation_id})
    return {"ok": True}


# ===========================================================================
# STREAMING CHAT (SSE) WITH TOKEN EVALUATOR + GEMINI
# ===========================================================================
async def _stream_chat_sse(
    message: str,
    history: list,
    threshold: float,
    conversation_id: Optional[str],
    user_id: Optional[str],
    file_context: str = "",
) -> AsyncIterator[str]:
    """
    Server-Sent Events generator:
    1. Evaluates input tokens using PyTorch ConfidenceEvaluator MLP.
    2. Sends 'eval' event containing token classification, savings % and latency.
    3. Streams conversational response tokens from Google Gemini.
    4. Computes Time-To-First-Token (TTFT) and total latency.
    5. Saves messages to MongoDB Atlas asynchronously.
    6. Sends 'done' event with complete performance & usage metrics.
    """
    if service is None:
        yield f"data: {json.dumps({'type':'error','message':'AI Service is initializing. Please retry shortly.'})}\n\n"
        return

    # 1. Safety check
    safety = service.check_safety(message)
    if safety:
        yield f"data: {json.dumps({'type':'token','text':safety})}\n\n"
        yield f"data: {json.dumps({'type':'done','input_tokens':0,'output_tokens':0,'latency_seconds':0.0,'ttft_seconds':0.0})}\n\n"
        return

    # 2. Confidence-Based Token Evaluator
    eval_metrics = {}
    try:
        eval_metrics = service.evaluate_tokens(message, threshold=threshold)
        yield f"data: {json.dumps({'type':'eval', **eval_metrics})}\n\n"
    except Exception as exc:
        logger.warning(f"[SSE] Evaluator error: {exc}")
        eval_metrics = {
            "token_analysis": [],
            "original_tokens": len(message.split()),
            "selected_tokens": len(message.split()),
            "tokens_saved": 0,
            "token_saving_percentage": 0.0,
            "confidence_threshold": threshold,
        }
        yield f"data: {json.dumps({'type':'eval', **eval_metrics})}\n\n"

    # 3. Stream Google Gemini Generation
    t0 = time.time()
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
            c_type = chunk.get("type")
            if c_type == "token":
                if first_token_time is None:
                    first_token_time = round(time.time() - t0, 3)
                text = chunk.get("text", "")
                full_response += text
                output_tokens_approx += 1
                yield f"data: {json.dumps({'type':'token','text':text})}\n\n"
                await asyncio.sleep(0)  # yield control
            elif c_type == "usage":
                gemini_usage = chunk
            elif c_type == "error":
                yield f"data: {json.dumps({'type':'error','message':chunk.get('message', 'Error')})}\n\n"
                return

        total_latency = round(time.time() - t0, 3)
        ttft = first_token_time if first_token_time is not None else total_latency

        if not full_response.strip():
            full_response = "I have processed your message. How can I assist you further?"
            yield f"data: {json.dumps({'type':'token','text':full_response})}\n\n"

        # 4. Asynchronously Persist Assistant Response to MongoDB
        if db_available() and conversation_id and user_id:
            try:
                msg_col = get_collection("Message")
                from bson import ObjectId
                await msg_col.insert_one({
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "role": "assistant",
                    "content": full_response,
                    "created_at": now_utc(),
                    "status": "completed",
                    "metrics": {
                        "input_tokens": eval_metrics.get("original_tokens", len(message.split())),
                        "output_tokens": output_tokens_approx,
                        "latency_seconds": total_latency,
                        "ttft_seconds": ttft,
                        "model_name": service.model_name,
                        "gemini_usage": gemini_usage,
                        **eval_metrics,
                    },
                })
                # Update conversation timestamp & auto-title
                conv_col = get_collection("Conversation")
                conv = await conv_col.find_one({"_id": ObjectId(conversation_id)})
                update_fields = {"updated_at": now_utc()}
                if conv and conv.get("title") in ("New Conversation", None, ""):
                    auto_title = message.strip()[:50]
                    if len(message.strip()) > 50:
                        auto_title += "…"
                    update_fields["title"] = auto_title
                await conv_col.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$set": update_fields},
                )
            except Exception as db_exc:
                logger.warning(f"[SSE] DB persist error: {db_exc}")

        # 5. Emit 'done' event
        done_payload = {
            "type": "done",
            "input_tokens": eval_metrics.get("original_tokens", len(message.split())),
            "output_tokens": output_tokens_approx,
            "latency_seconds": total_latency,
            "ttft_seconds": ttft,
            "model_name": service.model_name,
            "gemini_usage": gemini_usage,
            "token_saving_percentage": eval_metrics.get("token_saving_percentage", 0.0),
            "selected_tokens_count": eval_metrics.get("selected_tokens", 0),
            "filtered_tokens_count": eval_metrics.get("filtered_tokens_count", 0),
            "selected_text": eval_metrics.get("selected_text", ""),
            "semantic_preservation_passed": eval_metrics.get("semantic_preservation_passed", True),
            "semantic_preservation_message": eval_metrics.get("semantic_preservation_message", "OK"),
            "gemini_input_mode": eval_metrics.get("gemini_input_mode", "Full Original Prompt Preserved"),
        }
        yield f"data: {json.dumps(done_payload)}\n\n"

    except Exception as exc:
        total_latency = round(time.time() - t0, 3)
        logger.error(f"[SSE] Generation exception: {exc}")
        yield f"data: {json.dumps({'type':'error','message':f'Generation error: {str(exc)}'})}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """Primary SSE streaming chat endpoint."""
    user_id = current_user["user_id"] if current_user else None
    conversation_id = req.conversation_id
    threshold = max(0.0, min(1.0, float(req.threshold)))

    # Load conversation context history
    history = []
    if db_available() and conversation_id and user_id:
        try:
            from bson import ObjectId
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

    # Save user message to MongoDB
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

    # Fetch document context if file_id attached
    file_context = ""
    if req.file_id and user_id:
        file_context = await _get_file_context(req.file_id, user_id)
        if file_context:
            file_context = build_document_context(file_context, req.message)

    return StreamingResponse(
        _stream_chat_sse(req.message, history, threshold, conversation_id, user_id, file_context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ===========================================================================
# NON-STREAMING EVALUATE & RECALCULATE
# ===========================================================================
@app.post("/api/evaluate")
async def evaluate_text_endpoint(req: EvaluateRequest):
    if service is None:
        raise HTTPException(503, "Model service is initializing. Please retry shortly.")
    safe_threshold = max(0.0, min(1.0, float(req.threshold)))
    try:
        result = service.evaluate_text(req.text, safe_threshold, req.history)
        return result
    except Exception as exc:
        logger.error(f"[evaluate] Error: {exc}")
        raise HTTPException(500, f"Inference error: {str(exc)}")


@app.post("/api/recalculate")
async def recalculate_metrics(req: RecalculateRequest):
    threshold = max(0.0, min(1.0, float(req.threshold)))
    token_analysis = req.token_analysis
    retained_tokens, filtered_tokens, updated_analysis = [], [], []

    for item in token_analysis:
        score = float(item.get("confidence", 0.0))
        is_retained = score >= threshold
        status_str = "Retained" if is_retained else "Filtered"
        updated_item = {
            "id": item.get("id"),
            "token": item.get("token"),
            "confidence": score,
            "status": status_str,
            "retained": is_retained,
        }
        updated_analysis.append(updated_item)
        (retained_tokens if is_retained else filtered_tokens).append(item.get("token"))

    # Guarantee at least 1 retained token
    if not retained_tokens and updated_analysis:
        highest = max(updated_analysis, key=lambda x: x["confidence"])
        highest["status"] = "Retained"
        highest["retained"] = True
        retained_tokens.append(highest["token"])
        if highest["token"] in filtered_tokens:
            filtered_tokens.remove(highest["token"])

    original_tokens = len(updated_analysis)
    selected_tokens = len(retained_tokens)
    tokens_saved = original_tokens - selected_tokens
    saving_pct = round((tokens_saved / original_tokens) * 100, 2) if original_tokens > 0 else 0.0

    from evaluator import validate_semantic_preservation
    original_token_strs = [item.get("token", "") for item in updated_analysis]
    preservation_ok, preservation_msg = validate_semantic_preservation(
        original_token_strs, retained_tokens, filtered_tokens
    )

    return {
        "token_analysis": updated_analysis,
        "original_tokens": original_tokens,
        "evaluated_tokens": original_tokens,
        "selected_tokens": selected_tokens,
        "tokens_saved": tokens_saved,
        "filtered_tokens_count": tokens_saved,
        "saving_percentage": saving_pct,
        "token_saving_percentage": saving_pct,
        "retained_tokens": retained_tokens,
        "filtered_tokens": filtered_tokens,
        "confidence_threshold": threshold,
        "selected_text": " ".join(retained_tokens),
        "semantic_preservation_passed": preservation_ok,
        "semantic_preservation_message": preservation_msg,
    }


# ===========================================================================
# FILE MANAGEMENT (Uploaded_collection in MongoDB)
# ===========================================================================
@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload document or image. Extracts text and stores metadata in MongoDB."""
    content_type = file.content_type or "application/octet-stream"
    is_image = content_type in ALLOWED_IMAGE_TYPES
    is_doc = content_type in ALLOWED_DOC_TYPES or any(
        (file.filename or "").lower().endswith(ext)
        for ext in (".txt", ".md", ".csv", ".json", ".pdf", ".docx")
    )

    if not (is_image or is_doc):
        raise HTTPException(
            415,
            f"Unsupported file type: {content_type}. Allowed: PDF, DOCX, TXT, MD, CSV, JSON, PNG, JPG, WEBP.",
        )

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds maximum size of 25 MB.")

    file_id = str(uuid.uuid4())
    safe_name = re.sub(r"[^\w.\-]", "_", file.filename or "upload")
    store_path = os.path.join(UPLOAD_DIR, f"{file_id}_{safe_name}")

    # Save to local uploads directory
    with open(store_path, "wb") as f:
        f.write(content)

    # Extract text for document context
    extracted_text = ""
    if is_doc:
        extracted_text = extract_text(file.filename or safe_name, content)

    # Persist metadata to MongoDB Uploaded_collection
    if db_available():
        try:
            col = get_collection("Uploaded_collection")
            await col.insert_one({
                "file_id": file_id,
                "user_id": current_user["user_id"],
                "filename": file.filename,
                "content_type": content_type,
                "size_bytes": len(content),
                "is_image": is_image,
                "is_document": is_doc,
                "extracted_text": extracted_text,
                "store_path": store_path,
                "created_at": now_utc(),
            })
        except Exception as exc:
            logger.warning(f"[Upload] DB insert error: {exc}")

    return {
        "file_id": file_id,
        "filename": file.filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "is_image": is_image,
        "is_document": is_doc,
        "has_extracted_text": bool(extracted_text),
        "preview_text": extracted_text[:300] if extracted_text else None,
    }


@app.get("/api/files")
async def list_files(current_user: dict = Depends(get_current_user)):
    """List uploaded files belonging exclusively to the current authenticated user."""
    if not db_available():
        return []
    col = get_collection("Uploaded_collection")
    cursor = col.find(
        {"user_id": current_user["user_id"]},
        {"_id": 1, "file_id": 1, "filename": 1, "content_type": 1, "size_bytes": 1, "is_image": 1, "created_at": 1},
    ).sort("created_at", -1).limit(50)
    docs = await cursor.to_list(50)
    return [
        {
            "id": str(d["_id"]),
            "file_id": d.get("file_id"),
            "filename": d.get("filename"),
            "content_type": d.get("content_type"),
            "size_bytes": d.get("size_bytes"),
            "is_image": d.get("is_image", False),
            "created_at": d.get("created_at", "").isoformat() if hasattr(d.get("created_at", ""), "isoformat") else str(d.get("created_at", "")),
        }
        for d in docs
    ]


@app.delete("/api/files/{file_id}")
async def delete_file(file_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an uploaded file (verifying user ownership)."""
    if not db_available():
        raise HTTPException(503, "Database unavailable.")
    col = get_collection("Uploaded_collection")
    doc = await col.find_one({"file_id": file_id, "user_id": current_user["user_id"]})
    if not doc:
        raise HTTPException(404, "File not found or access denied.")

    # Remove file from disk
    store_path = doc.get("store_path")
    if store_path and os.path.exists(store_path):
        try:
            os.remove(store_path)
        except Exception:
            pass

    # Delete metadata from MongoDB
    await col.delete_one({"_id": doc["_id"]})
    return {"ok": True, "file_id": file_id}


# ===========================================================================
# ENTRYPOINT
# ===========================================================================
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=False)
