"""
history.py
Persists each generated study pack (notes/cards/quiz) to MongoDB, scoped
to the user who uploaded it, so it can be revisited later without
re-processing the file.
"""

from datetime import datetime

from bson.objectid import ObjectId

from utils.db import get_db


def get_uploads_collection():
    return get_db()["uploads"]


def save_upload_record(user_id: str, filename: str, file_type: str, study_pack: dict):
    """Stores one completed study pack. Returns the new record's id as a string."""
    doc = {
        "user_id": user_id,
        "filename": filename,
        "file_type": file_type,
        "engine": study_pack.get("engine", "unknown"),
        "notes": study_pack.get("notes", []),
        "cards": study_pack.get("cards", []),
        "quiz": study_pack.get("quiz", []),
        "uploaded_at": datetime.utcnow(),
    }
    result = get_uploads_collection().insert_one(doc)
    return str(result.inserted_id)


def list_uploads_for_user(user_id: str):
    """Lightweight list for the library page — no need to ship full
    notes/cards/quiz content just to render a list of past uploads."""
    cursor = get_uploads_collection().find(
        {"user_id": user_id},
        projection={"filename": 1, "file_type": 1, "engine": 1, "uploaded_at": 1,
                    "notes": 1, "cards": 1, "quiz": 1},
    ).sort("uploaded_at", -1)

    results = []
    for doc in cursor:
        results.append({
            "id": str(doc["_id"]),
            "filename": doc.get("filename", "Untitled"),
            "file_type": doc.get("file_type", "file"),
            "engine": doc.get("engine", "unknown"),
            # stored as naive UTC (datetime.utcnow()) — mark it explicitly as UTC
            # ("Z") so the browser's JS can convert it to the viewer's own local
            # time instead of displaying the raw UTC value as if it were local
            "uploaded_at_iso": doc["uploaded_at"].isoformat() + "Z",
            "card_count": len(doc.get("cards", [])),
            "quiz_count": len(doc.get("quiz", [])),
        })
    return results


def get_upload_by_id(user_id: str, upload_id: str):
    """Returns the full record only if it belongs to this user — prevents
    one user from viewing another user's study pack by guessing an id."""
    try:
        doc = get_uploads_collection().find_one({
            "_id": ObjectId(upload_id),
            "user_id": user_id,
        })
    except Exception:
        return None
    return doc


def delete_upload(user_id: str, upload_id: str) -> bool:
    """Deletes a record only if it belongs to this user. Returns True if
    something was actually deleted."""
    try:
        result = get_uploads_collection().delete_one({
            "_id": ObjectId(upload_id),
            "user_id": user_id,
        })
    except Exception:
        return False
    return result.deleted_count > 0
