
"""
Nexa AI - MongoDB Atlas Database Connection

Database: Transformer

Collections:
- Users
- Conversation
- Message
- Uploaded_collection
"""

import logging

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from config import settings

logger = logging.getLogger("nexa.database")

_client = None
_db = None
_indexes_created = False


def get_client():
    return _client


def get_db():
    return _db


def get_collection(name: str):

    if _db is None:
        return None

    if name in (
        "Uploaded_collection",
        "Uploded_collection"
    ):
        return _db["Uploaded_collection"]

    return _db[name]


def db_available() -> bool:
    return _client is not None and _db is not None


async def connect_db() -> bool:

    global _client, _db, _indexes_created

    if not settings.MONGODB_URI:
        logger.warning(
            "[DB] MONGODB_URI not configured."
        )
        return False

    # Reuse an existing client when possible.
    if _client is not None and _db is not None:

        try:
            await _client.admin.command("ping")
            return True

        except Exception:
            logger.warning(
                "[DB] Existing connection failed. Reconnecting."
            )

            try:
                _client.close()
            except Exception:
                pass

            _client = None
            _db = None
            _indexes_created = False

    try:

        _client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
            maxPoolSize=10,
            minPoolSize=0,
            retryWrites=True,
        )

        await _client.admin.command("ping")

        _db = _client[settings.MONGODB_DB_NAME]

        logger.info(
            "[DB] MongoDB Atlas connected: %s",
            settings.MONGODB_DB_NAME
        )

        if not _indexes_created:
            await create_indexes()
            _indexes_created = True

        return True

    except Exception:

        logger.exception(
            "[DB] MongoDB connection failed."
        )

        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass

        _client = None
        _db = None
        _indexes_created = False

        return False


async def create_indexes():

    global _db

    if _db is None:
        return

    try:

        await _db["Users"].create_index(
            [("email", ASCENDING)],
            unique=True,
            name="email_unique",
        )

        await _db["Conversation"].create_index(
            [
                ("user_id", ASCENDING),
                ("updated_at", DESCENDING),
            ],
            name="conv_user_updated",
        )

        await _db["Message"].create_index(
            [
                ("conversation_id", ASCENDING),
                ("created_at", ASCENDING),
            ],
            name="msg_conv_order",
        )

        await _db["Uploaded_collection"].create_index(
            [
                ("user_id", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="upload_user_time",
        )

        await _db["Uploaded_collection"].create_index(
            [("file_id", ASCENDING)],
            name="upload_file_id",
        )

        logger.info(
            "[DB] MongoDB indexes verified."
        )

    except Exception:

        logger.exception(
            "[DB] Index creation failed."
        )

        raise


async def close_db():

    global _client, _db, _indexes_created

    if _client is not None:

        try:
            _client.close()
        except Exception:
            logger.exception(
                "[DB] Error closing connection."
            )

    _client = None
    _db = None
    _indexes_created = False

    logger.info("[DB] Connection closed.")
