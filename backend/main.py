"""
Nexa AI — FastAPI Application Entry Point
==========================================
Confidence-Based Token Evaluator in Transformer Models
Enterprise Chatbot with Google Gemini Integration
"""

import logging
import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import connect_db, close_db, db_available, get_collection
from auth import get_current_user
from services import gemini_service

# Import routers
from routes.auth import router as auth_router
from routes.conversations import router as conversations_router
from routes.chat import router as chat_router
from routes.token_filter import router as token_filter_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("nexa")

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Nexa AI",
    description="Confidence-Based Token Evaluator in Transformer Models",
    version="3.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Normalize double /api/api/ prefix
@app.middleware("http")
async def fix_duplicate_api_prefix(request: Request, call_next):
    if request.scope.get("path", "").startswith("/api/api/"):
        request.scope["path"] = request.scope["path"][4:]
    return await call_next(request)


# ---------------------------------------------------------------------------
# Register Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(token_filter_router)


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
# Startup / Shutdown
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    # Validate configuration
    config_status = settings.validate()
    logger.info(f"[Startup] Config: {config_status}")

    # Connect MongoDB
    ok = await connect_db()
    if ok:
        logger.info("[Startup] MongoDB Atlas connected.")
    else:
        logger.warning("[Startup] Running without MongoDB.")

    # Initialize Gemini client
    if gemini_service.is_available():
        logger.info(f"[Startup] Gemini ready: {settings.GEMINI_MODEL}")
    else:
        logger.warning("[Startup] Gemini not available. Check API key.")


@app.on_event("shutdown")
async def shutdown_event():
    await close_db()


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
def now_utc():
    return datetime.now(timezone.utc)


@app.get("/api/health")
async def health_check():
    """Real health endpoint reporting actual service status."""
    mongo_ok = db_available()
    gemini_ok = gemini_service.is_available()

    # Test token evaluator
    evaluator_ok = False
    try:
        from services.filtering_service import filter_tokens
        test = filter_tokens("test", 0.5)
        evaluator_ok = test.get("original_tokens", 0) > 0
    except Exception:
        pass

    overall = "ok" if (mongo_ok and gemini_ok and evaluator_ok) else "degraded"

    return {
        "status": overall,
        "backend": "running",
        "mongodb_connected": mongo_ok,
        "gemini_configured": gemini_ok,
        "gemini_model": settings.GEMINI_MODEL,
        "token_evaluator": "ready" if evaluator_ok else "error",
        "timestamp": now_utc().isoformat(),
    }


# ---------------------------------------------------------------------------
# File Upload
# ---------------------------------------------------------------------------
def _extract_text(filename: str, content: bytes) -> str:
    """Extract text from uploaded documents."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    try:
        if ext == "txt" or ext == "md" or ext == "csv":
            return content.decode("utf-8", errors="replace")[:50000]
        elif ext == "json":
            return content.decode("utf-8", errors="replace")[:50000]
        elif ext == "pdf":
            try:
                from pypdf import PdfReader
                import io
                reader = PdfReader(io.BytesIO(content))
                text_parts = []
                for page in reader.pages[:50]:
                    text_parts.append(page.extract_text() or "")
                return "\n".join(text_parts)[:50000]
            except Exception:
                return ""
        elif ext == "docx":
            try:
                from docx import Document
                import io
                doc = Document(io.BytesIO(content))
                return "\n".join(p.text for p in doc.paragraphs)[:50000]
            except Exception:
                return ""
    except Exception:
        return ""
    return ""


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "upload"
    is_image = content_type in ALLOWED_IMAGE_TYPES
    is_doc = content_type in ALLOWED_DOC_TYPES or any(
        filename.endswith(ext)
        for ext in (".txt", ".md", ".csv", ".json", ".pdf", ".docx")
    )

    if not (is_image or is_doc):
        raise HTTPException(415, f"Unsupported file type: {content_type}")

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds 25 MB limit.")

    file_id = str(uuid.uuid4())
    safe_name = re.sub(r"[^\w.\-]", "_", filename)
    store_path = os.path.join(UPLOAD_DIR, f"{file_id}_{safe_name}")

    with open(store_path, "wb") as f:
        f.write(content)

    extracted_text = ""
    if is_doc:
        extracted_text = _extract_text(filename, content)

    if db_available():
        try:
            col = get_collection("Uploaded_collection")
            await col.insert_one({
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
        except Exception as exc:
            logger.warning(f"[Upload] DB error: {exc}")

    return {
        "file_id": file_id,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "is_image": is_image,
        "is_document": is_doc,
        "has_extracted_text": bool(extracted_text),
    }


@app.get("/api/files")
async def list_files(current_user: dict = Depends(get_current_user)):
    if not db_available():
        return []
    col = get_collection("Uploaded_collection")
    cursor = col.find(
        {"user_id": current_user["user_id"]},
        {"_id": 1, "file_id": 1, "filename": 1, "content_type": 1, "size_bytes": 1, "created_at": 1},
    ).sort("created_at", -1).limit(50)
    docs = await cursor.to_list(50)
    return [
        {
            "id": str(d["_id"]),
            "file_id": d.get("file_id"),
            "filename": d.get("filename"),
            "content_type": d.get("content_type"),
            "size_bytes": d.get("size_bytes"),
            "created_at": d.get("created_at", "").isoformat()
            if hasattr(d.get("created_at", ""), "isoformat")
            else str(d.get("created_at", "")),
        }
        for d in docs
    ]


@app.delete("/api/files/{file_id}")
async def delete_file(file_id: str, current_user: dict = Depends(get_current_user)):
    if not db_available():
        raise HTTPException(503, "Database unavailable.")
    col = get_collection("Uploaded_collection")
    doc = await col.find_one({"file_id": file_id, "user_id": current_user["user_id"]})
    if not doc:
        raise HTTPException(404, "File not found or access denied.")
    store_path = doc.get("store_path")
    if store_path and os.path.exists(store_path):
        try:
            os.remove(store_path)
        except Exception:
            pass
    await col.delete_one({"_id": doc["_id"]})
    return {"ok": True, "file_id": file_id}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)
