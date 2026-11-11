"""
Nexa AI — MongoDB Atlas Database Connection
Database: Transformer
Collections: Users, Conversation, Message, Uploaded_collection
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from config import settings

logger = logging.getLogger("nexa.database")

_client: AsyncIOMotorClient = None
_db = None


def get_db():
    """Return the database instance."""
    return _db


def get_collection(name: str):
    """Return a MongoDB collection by name."""
    if _db is None:
        return None
    # Normalize upload collection name
    if name in ("Uploaded_collection", "Uploded_collection"):
        return _db["Uploaded_collection"]
    return _db[name]


def db_available() -> bool:
    """Check if the database connection is active."""
    return _db is not None


async def connect_db() -> bool:
    """Connect to MongoDB Atlas and create indexes."""
    global _client, _db

    if not settings.MONGODB_URI:
        logger.warning("[DB] MONGODB_URI not set. Database features disabled.")
        return False

    try:
        _client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
            maxPoolSize=25,
        )
        # Verify connection
        await _client.admin.command("ping")
        _db = _client[settings.MONGODB_DB_NAME]
        logger.info(f"[DB] Connected to MongoDB Atlas — database: {settings.MONGODB_DB_NAME}")

        await _create_indexes()
        return True
    except Exception as exc:
        logger.error(f"[DB] Connection failed: {exc}")
        _client = None
        _db = None
        return False


async def _create_indexes():
    """Create required indexes on collections."""
    try:
        # Users: unique email index
        await _db["Users"].create_index(
            [("email", ASCENDING)], unique=True, name="email_unique"
        )
        # Conversation: list by user, sorted by time
        await _db["Conversation"].create_index(
            [("user_id", ASCENDING), ("updated_at", DESCENDING)],
            name="conv_user_updated",
        )
        # Message: ordered messages per conversation
        await _db["Message"].create_index(
            [("conversation_id", ASCENDING), ("created_at", ASCENDING)],
            name="msg_conv_order",
        )
        # Uploaded_collection: files by user
        await _db["Uploaded_collection"].create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="upload_user_time",
        )
        await _db["Uploaded_collection"].create_index(
            [("file_id", ASCENDING)],
            name="upload_file_id",
        )
        logger.info("[DB] Indexes verified on all collections.")
    except Exception as exc:
        logger.warning(f"[DB] Index creation note: {exc}")


async def close_db():
    """Close the database connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("[DB] Connection closed.")
