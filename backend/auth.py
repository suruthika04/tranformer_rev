"""
Authentication utilities using PyJWT + bcrypt.
100% compatible with Python 3.14 and bcrypt 5.x.
"""
import os
import logging

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if os.getenv("RENDER"):
        raise RuntimeError("SECRET_KEY is required in the Render environment.")
    SECRET_KEY = "local-development-only-change-this-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------------------------------------------------------
# Password helpers (Native bcrypt)
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    """Hash a password using bcrypt with standard 72-byte truncation."""
    encoded = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(encoded, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against stored bcrypt hash."""
    try:
        encoded = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(encoded, hashed.encode("utf-8"))
    except Exception as exc:
        logger.debug(f"[Auth] Password verification failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "iat": now, "exp": expire}
    return pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        logger.debug("[Auth] Token expired")
        return None
    except pyjwt.InvalidTokenError:
        return None


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """Dependency that returns the authenticated user payload or raises 401."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"user_id": payload["sub"], "email": payload.get("email", "")}


async def get_optional_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[dict]:
    """Like get_current_user but returns None instead of raising for unauthenticated."""
    if not token:
        return None
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None
    return {"user_id": payload["sub"], "email": payload.get("email", "")}
