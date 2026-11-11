
"""
Nexa AI - Application Configuration
Loads environment variables and validates settings.
"""

import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger("nexa.config")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load local .env file.
# On Vercel, environment variables are provided by the platform.
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Settings:

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.1-flash-lite"
    )

    # MongoDB
    MONGODB_URI = os.getenv("MONGODB_URI", "")
    MONGODB_DB_NAME = os.getenv(
        "MONGODB_DB_NAME",
        "Transformer"
    )

    # JWT
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "nexa-ai-development-only-change-this-secret"
    )

    ALGORITHM = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")
    )

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")

    PORT = int(os.getenv("PORT", "8000"))

    # CORS
    ALLOWED_ORIGINS = [
        origin.strip().rstrip("/")
        for origin in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]

    @classmethod
    def validate(cls):

        status = {
            "gemini_configured": bool(cls.GEMINI_API_KEY),
            "gemini_model": cls.GEMINI_MODEL,
            "mongodb_configured": bool(cls.MONGODB_URI),
            "jwt_configured": (
                len(cls.SECRET_KEY) >= 32
                and "development-only" not in cls.SECRET_KEY
            ),
        }

        if not cls.GEMINI_API_KEY:
            logger.warning(
                "[Config] GEMINI_API_KEY is missing."
            )

        if not cls.MONGODB_URI:
            logger.warning(
                "[Config] MONGODB_URI is missing."
            )

        if not status["jwt_configured"]:
            logger.warning(
                "[Config] Configure a strong production SECRET_KEY."
            )

        if not cls.ALLOWED_ORIGINS:
            logger.warning(
                "[Config] No CORS origins configured."
            )

        return status


settings = Settings()
