"""
MongoDB Atlas database connection and collection helpers.
Database: Transformer
Collections: Users, Conversation, Message, Uploded_collection (Uploaded_collection)
"""
import os
import logging

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient = None
_db = None


def get_client() -> AsyncIOMotorClient:
    return _client


def get_db():
    return _db


def get_collection(name: str):
    if _db is None:
        return None
    # Normalize upload collection name to match actual MongoDB collection
    if name in ("Uploaded_collection", "Uploded_collection"):
        return _db["Uploaded_collection"]
    return _db[name]


async def connect_db():
    """Connect to MongoDB Atlas and create indexes."""
    global _client, _db

    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "Transformer")
    if not uri:
        logger.warning(
            "[DB] MONGODB_URI not set. Database features (auth, history, uploads) will be disabled."
        )
        return False

    try:
        _client = AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
            maxPoolSize=25,
        )
        # Verify connection
        await _client.admin.command("ping")
        _db = _client[db_name]
        logger.info(f"[DB] Successfully connected to MongoDB Atlas — database: {db_name}")

        await _create_indexes()
        return True
    except Exception as exc:
        logger.error("[DB] Connection failed (%s): %s", type(exc).__name__, str(exc).split("@")[-1])
        _client = None
        _db = None
        return False


async def _create_indexes():
    """Create required indexes on existing collections."""
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
        logger.info("[DB] Indexes verified successfully on MongoDB Atlas collections.")
    except Exception as exc:
        logger.warning(f"[DB] Index creation note: {exc}")


async def close_db():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("[DB] Connection closed.")


def db_available() -> bool:
    return _db is not None
