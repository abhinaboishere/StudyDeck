"""
db.py
MongoDB connection setup, using MongoDB Atlas's free tier (M0).

Set MONGODB_URI in your environment before running the app, e.g.:
export MONGODB_URI="mongodb+srv://user:password@cluster0.xxxxx.mongodb.net/"

Connection is lazy — nothing happens at import time, so the rest of the
app still works even if this isn't configured yet.
"""

import os

from pymongo import MongoClient

_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError(
                "MONGODB_URI is not set. Add it to your environment "
                "(see README) before using login/signup."
            )
        _client = MongoClient(uri)
        _db = _client["study_deck"]
        _db["users"].create_index("email", unique=True)
    return _db


def get_users_collection():
    return get_db()["users"]
