"""
auth_models.py
User model + signup/login helpers, backed by MongoDB.
Passwords are hashed with werkzeug's generate_password_hash — the plain
password is never stored, only its hash.
"""

from bson.objectid import ObjectId
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from utils.db import get_users_collection


class User(UserMixin):
    def __init__(self, user_doc):
        self.id = str(user_doc["_id"])
        self.email = user_doc["email"]
        self.avatar_data = user_doc.get("avatar_data", "")  # data: URL, or "" if none set

    @staticmethod
    def get_by_id(user_id):
        try:
            doc = get_users_collection().find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None
        return User(doc) if doc else None

    @staticmethod
    def create(email, password):
        """Returns (User, None) on success, or (None, error_message) on failure."""
        email = email.lower().strip()
        if not email or "@" not in email:
            return None, "Please enter a valid email address."
        if len(password) < 6:
            return None, "Password must be at least 6 characters."
        if get_users_collection().find_one({"email": email}):
            return None, "An account with that email already exists."

        password_hash = generate_password_hash(password)
        result = get_users_collection().insert_one({
            "email": email,
            "password_hash": password_hash,
        })
        doc = get_users_collection().find_one({"_id": result.inserted_id})
        return User(doc), None

    @staticmethod
    def verify_password(email, password):
        """Returns the User on success, or None if email/password don't match."""
        doc = get_users_collection().find_one({"email": email.lower().strip()})
        if not doc:
            return None
        if check_password_hash(doc["password_hash"], password):
            return User(doc)
        return None

    @staticmethod
    def update_avatar(user_id, data_url):
        get_users_collection().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"avatar_data": data_url}},
        )
