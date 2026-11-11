"""
Nexa AI — Authentication Routes
Handles user registration, login, and session management.
"""

import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from database import db_available, get_collection
from models.user import SignupRequest, LoginRequest

logger = logging.getLogger("nexa.routes.auth")
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def now_utc():
    return datetime.now(timezone.utc)


def _sanitize_user(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id", "")),
        "name": doc.get("name", ""),
        "email": doc.get("email", ""),
        "created_at": doc.get("created_at", "").isoformat()
        if hasattr(doc.get("created_at", ""), "isoformat")
        else str(doc.get("created_at", "")),
    }


@router.post("/signup", status_code=201)
async def signup(req: SignupRequest):
    if not db_available():
        raise HTTPException(503, "Database unavailable. Cannot create account.")

    if req.password != req.confirm_password:
        raise HTTPException(400, "Passwords do not match.")

    email_norm = req.email.strip().lower()
    if "@" not in email_norm or "." not in email_norm.split("@")[-1]:
        raise HTTPException(400, "Invalid email format.")

    users = get_collection("Users")
    existing = await users.find_one({"email": email_norm})
    if existing:
        raise HTTPException(409, "An account with this email already exists.")

    doc = {
        "name": req.name.strip(),
        "email": email_norm,
        "password_hash": hash_password(req.password),
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    result = await users.insert_one(doc)
    user_id = str(result.inserted_id)
    token = create_access_token(user_id, email_norm)

    return {
        "message": "Account created successfully.",
        "token": token,
        "user": {"id": user_id, "name": doc["name"], "email": email_norm},
    }


@router.post("/login")
async def login(req: LoginRequest):
    if not db_available():
        raise HTTPException(503, "Database unavailable.")

    email_norm = req.email.strip().lower()
    users = get_collection("Users")
    doc = await users.find_one({"email": email_norm})

    if not doc or not verify_password(req.password, doc.get("password_hash", "")):
        raise HTTPException(401, "Incorrect email or password.")

    user_id = str(doc["_id"])
    await users.update_one({"_id": doc["_id"]}, {"$set": {"last_login_at": now_utc()}})
    token = create_access_token(user_id, email_norm)
    return {"token": token, "user": _sanitize_user(doc)}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    if not db_available():
        return current_user
    users = get_collection("Users")
    try:
        doc = await users.find_one({"_id": ObjectId(current_user["user_id"])})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(404, "User not found.")
    return _sanitize_user(doc)
