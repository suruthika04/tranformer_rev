"""
Nexa AI — Application Configuration
Loads environment variables and validates required settings on startup.
"""

import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger("nexa.config")

# Load .env file
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)


class Settings:
    """Application settings loaded from environment variables."""

    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    # MongoDB
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "Transformer")

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "nexa-ai-default-secret-change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    # CORS
    ALLOWED_ORIGINS: list = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    ]

    @classmethod
    def validate(cls) -> dict:
        """Validate configuration and return status report. Never logs secrets."""
        status = {
            "gemini_configured": bool(cls.GEMINI_API_KEY),
            "gemini_model": cls.GEMINI_MODEL,
            "mongodb_configured": bool(cls.MONGODB_URI),
            "jwt_configured": len(cls.SECRET_KEY) >= 16,
        }

        if not cls.GEMINI_API_KEY:
            logger.warning("[Config] GEMINI_API_KEY is not set. AI features will be unavailable.")
        if not cls.MONGODB_URI:
            logger.warning("[Config] MONGODB_URI is not set. Database features will be disabled.")
        if len(cls.SECRET_KEY) < 16:
            logger.warning("[Config] SECRET_KEY is too short. Use at least 16 characters.")

        return status


settings = Settings()
