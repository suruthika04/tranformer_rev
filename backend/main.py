
"""
Nexa AI - FastAPI Application Entry Point
Confidence-Based Token Evaluator in Transformer Models
"""

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import connect_db, close_db, db_available, get_collection
from auth import get_current_user
from services import gemini_service

from routes.auth import router as auth_router
from routes.conversations import router as conversations_router
from routes.chat import router as chat_router
from routes.token_filter import router as token_filter_router


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("nexa")


# --------------------------------------------------
# FASTAPI APP
# --------------------------------------------------

app = FastAPI(
    title="Nexa AI",
    description="Confidence-Based Token Evaluator in Transformer Models",
    version="3.0.0",
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

allowed_origins = settings.ALLOWED_ORIGINS

if isinstance(allowed_origins, str):
    allowed_origins = [
        origin.strip()
        for origin in allowed_origins.split(",")
        if origin.strip()
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# ROUTERS
# --------------------------------------------------

app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(token_filter_router)


# --------------------------------------------------
# FILE CONFIGURATION
# --------------------------------------------------

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

# Vercel provides temporary writable storage in /tmp.
# Files stored here are NOT persistent across deployments/instances.
UPLOAD_DIR = Path("/tmp/nexa_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# STARTUP
# --------------------------------------------------

@app.on_event("startup")
async def startup_event():

    try:
        settings.validate()
        logger.info("[Startup] Configuration validated.")
    except Exception:
        logger.exception("[Startup] Configuration validation failed.")

    try:
        connected = await connect_db()

        if connected:
            logger.info("[Startup] MongoDB connected.")
        else:
            logger.warning("[Startup] MongoDB unavailable.")

    except Exception:
        logger.exception("[Startup] MongoDB connection error.")

    try:
        if gemini_service.is_available():
            logger.info("[Startup] Gemini configured.")
        else:
            logger.warning("[Startup] Gemini unavailable.")

    except Exception:
        logger.exception("[Startup] Gemini initialization error.")


@app.on_event("shutdown")
async def shutdown_event():
    try:
        await close_db()
    except Exception:
        logger.exception("[Shutdown] Database closing error.")


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

def now_utc():
    return datetime.now(timezone.utc)


@app.get("/api/health")
async def health_check():

    mongo_ok = db_available()
    gemini_ok = gemini_service.is_available()

    evaluator_ok = False

    try:
        from services.filtering_service import filter_tokens

        result = filter_tokens("test", 0.5)

        evaluator_ok = (
            isinstance(result, dict)
            and result.get("original_tokens", 0) > 0
        )

    except Exception:
        logger.exception("[Health] Token evaluator error.")

    overall = (
        "ok"
        if mongo_ok and gemini_ok and evaluator_ok
        else "degraded"
    )

    return {
        "status": overall,
        "backend": "running",
        "mongodb_connected": mongo_ok,
        "gemini_configured": gemini_ok,
        "gemini_model": settings.GEMINI_MODEL,
        "token_evaluator": (
            "ready" if evaluator_ok else "error"
        ),
        "timestamp": now_utc().isoformat(),
    }


# --------------------------------------------------
# TEXT EXTRACTION
# --------------------------------------------------

def extract_text(filename: str, content: bytes) -> str:

    ext = Path(filename).suffix.lower()

    try:

        if ext in {".txt", ".md", ".csv", ".json"}:
            return content.decode(
                "utf-8",
                errors="replace"
            )[:50000]

        if ext == ".pdf":
            from pypdf import PdfReader
            import io

            reader = PdfReader(io.BytesIO(content))

            pages = [
                page.extract_text() or ""
                for page in reader.pages[:50]
            ]

            return "\n".join(pages)[:50000]

        if ext == ".docx":
            from docx import Document
            import io

            document = Document(io.BytesIO(content))

            return "\n".join(
                paragraph.text
                for paragraph in document.paragraphs
            )[:50000]

    except Exception:
        logger.exception("[Upload] Text extraction failed.")

    return ""


# --------------------------------------------------
# FILE UPLOAD
# --------------------------------------------------

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):

    filename = file.filename or "upload"
    content_type = file.content_type or "application/octet-stream"

    ext = Path(filename).suffix.lower()

    is_image = content_type in ALLOWED_IMAGE_TYPES

    is_doc = (
        content_type in ALLOWED_DOC_TYPES
        and ext in {".pdf", ".txt", ".md", ".csv", ".json", ".docx"}
    )

    if not (is_image or is_doc):
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type."
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Empty file."
        )

    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File exceeds 25 MB limit."
        )

    file_id = str(uuid.uuid4())

    safe_name = re.sub(
        r"[^\w.\-]",
        "_",
        Path(filename).name
    )

    store_path = UPLOAD_DIR / f"{file_id}_{safe_name}"

    try:
        store_path.write_bytes(content)
    except OSError:
        raise HTTPException(
            status_code=500,
            detail="File storage failed."
        )

    extracted_text = ""

    if is_doc:
        extracted_text = extract_text(filename, content)

    if not db_available():
        try:
            store_path.unlink(missing_ok=True)
        except OSError:
            pass

        raise HTTPException(
            status_code=503,
            detail="Database unavailable."
        )

    try:
        collection = get_collection("Uploaded_collection")

        await collection.insert_one({
            "file_id": file_id,
            "user_id": current_user["user_id"],
            "filename": filename,
            "content_type": content_type,
            "size_bytes": len(content),
            "is_image": is_image,
            "is_document": is_doc,
            "extracted_text": extracted_text,
            "store_path": str(store_path),
            "created_at": now_utc(),
        })

    except Exception:
        logger.exception("[Upload] Database storage failed.")

        try:
            store_path.unlink(missing_ok=True)
        except OSError:
            pass

        raise HTTPException(
            status_code=500,
            detail="Could not save file information."
        )

    return {
        "file_id": file_id,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "is_image": is_image,
        "is_document": is_doc,
        "has_extracted_text": bool(extracted_text),
    }


# --------------------------------------------------
# LIST FILES
# --------------------------------------------------

@app.get("/api/files")
async def list_files(
    current_user: dict = Depends(get_current_user)
):

    if not db_available():
        raise HTTPException(
            status_code=503,
            detail="Database unavailable."
        )

    collection = get_collection("Uploaded_collection")

    cursor = collection.find(
        {"user_id": current_user["user_id"]},
        {
            "_id": 1,
            "file_id": 1,
            "filename": 1,
            "content_type": 1,
            "size_bytes": 1,
            "created_at": 1,
        },
    ).sort("created_at", -1).limit(50)

    documents = await cursor.to_list(50)

    return [
        {
            "id": str(doc["_id"]),
            "file_id": doc.get("file_id"),
            "filename": doc.get("filename"),
            "content_type": doc.get("content_type"),
            "size_bytes": doc.get("size_bytes"),
            "created_at": (
                doc["created_at"].isoformat()
                if hasattr(doc.get("created_at"), "isoformat")
                else str(doc.get("created_at", ""))
            ),
        }
        for doc in documents
    ]


# --------------------------------------------------
# DELETE FILE
# --------------------------------------------------

@app.delete("/api/files/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):

    if not db_available():
        raise HTTPException(
            status_code=503,
            detail="Database unavailable."
        )

    collection = get_collection("Uploaded_collection")

    document = await collection.find_one({
        "file_id": file_id,
        "user_id": current_user["user_id"],
    })

    if not document:
        raise HTTPException(
            status_code=404,
            detail="File not found or access denied."
        )

    store_path = document.get("store_path")

    if store_path:
        try:
            Path(store_path).unlink(missing_ok=True)
        except OSError:
            logger.warning("[Upload] Temporary file could not be deleted.")

    await collection.delete_one({
        "_id": document["_id"]
    })

    return {
        "ok": True,
        "file_id": file_id,
    }


# --------------------------------------------------
# ROOT
# --------------------------------------------------

@app.get("/")
async def root():
    return {
        "application": "Nexa AI",
        "status": "running",
        "version": "3.0.0",
    }


# --------------------------------------------------
# LOCAL EXECUTION
# --------------------------------------------------

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
