"""
app.py
Flask backend for the Smart Study Deck generator.
Accepts a PDF, image, audio, or video file, extracts its text
(OCR / speech-to-text where needed), then runs a pure-NLP pipeline
(spaCy + sumy + NLTK — no LLM calls) to produce flashcards, key
notes, and a multiple-choice quiz.
"""

import base64
import io
import json
import os
import traceback
import uuid

from dotenv import load_dotenv
load_dotenv()  # reads a .env file in this folder into os.environ, if one exists

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user,
)
from werkzeug.utils import secure_filename
from PIL import Image

from utils.extractors import extract_text, get_file_kind
from utils import nlp_engine
from utils import llm_engine
from utils import gemini_engine
from utils import config_store
from utils.auth_models import User
from utils import history
from utils import video_url

config_store.sync_env_from_config()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Audio/video file uploads were dropped in favor of pasting a video URL
# instead (see /upload-url) — no local ffmpeg/moviepy processing needed
# for the common case of "I have a link to a video", and it avoids asking
# users to download a video just to upload it back.
ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp",
}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB, video files are large
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-this-before-deploying")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to use Study Deck."


@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            flash("Passwords don't match.")
            return render_template("signup.html")

        try:
            user, error = User.create(email, password)
        except RuntimeError as e:
            error = str(e)  # e.g. MONGODB_URI not set
            user = None
        if error:
            flash(error)
            return render_template("signup.html")
        login_user(user)
        return redirect(url_for("index"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        try:
            user = User.verify_password(email, password)
        except RuntimeError as e:
            flash(str(e))  # e.g. MONGODB_URI not set
            return render_template("login.html")
        if not user:
            flash("Incorrect email or password.")
            return render_template("login.html")
        login_user(user)
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
def index():
    if not current_user.is_authenticated:
        return render_template("landing.html")
    return render_template(
        "index.html",
        active_provider=config_store.active_provider(),
        user_email=current_user.email,
        preloaded_json=None,
    )


@app.route("/library")
@login_required
def library():
    uploads = history.list_uploads_for_user(current_user.id)
    return render_template("library.html", uploads=uploads)


@app.route("/library/<upload_id>")
@login_required
def library_item(upload_id):
    doc = history.get_upload_by_id(current_user.id, upload_id)
    if doc is None:
        flash("That study pack couldn't be found.")
        return redirect(url_for("library"))

    preloaded = {
        "notes": doc.get("notes", []),
        "cards": doc.get("cards", []),
        "quiz": doc.get("quiz", []),
        "engine": doc.get("engine", ""),
        "sourceType": doc.get("file_type", ""),
        "sourceName": doc.get("filename", ""),
        "uploadedAtIso": doc["uploaded_at"].isoformat() + "Z" if doc.get("uploaded_at") else None,
    }
    return render_template(
        "index.html",
        active_provider=config_store.active_provider(),
        user_email=current_user.email,
        preloaded_json=json.dumps(preloaded),
    )


@app.route("/library/<upload_id>/delete", methods=["POST"])
@login_required
def delete_library_item(upload_id):
    history.delete_upload(current_user.id, upload_id)
    return redirect(url_for("library"))


@app.route("/settings", methods=["GET"])
@login_required
def settings():
    # Deliberately minimal: just the user's own profile picture + logout.
    # Engine/API-key configuration lives at /admin/config instead — not
    # linked anywhere in the UI — since that's app-wide config, not
    # something every user account should see or touch.
    return render_template("settings.html")


@app.route("/admin/config", methods=["GET", "POST"])
@login_required
def admin_config():
    saved = False
    if request.method == "POST":
        existing = config_store.load_config()
        anthropic_input = request.form.get("anthropic_api_key", "").strip()
        gemini_input = request.form.get("gemini_api_key", "").strip()
        config_store.save_config({
            # blank field = keep whatever was already saved
            "anthropic_api_key": anthropic_input or existing.get("anthropic_api_key", ""),
            "gemini_api_key": gemini_input or existing.get("gemini_api_key", ""),
            "preferred_provider": request.form.get("preferred_provider", "auto"),
        })
        config_store.sync_env_from_config(force=True)
        saved = True

    config = config_store.load_config()
    return render_template(
        "admin_config.html",
        saved=saved,
        anthropic_masked=config_store.mask_key(config.get("anthropic_api_key", "")),
        gemini_masked=config_store.mask_key(config.get("gemini_api_key", "")),
        preferred_provider=config.get("preferred_provider", "auto"),
        active_provider=config_store.active_provider(),
    )


@app.route("/settings/avatar", methods=["POST"])
@login_required
def upload_avatar():
    file = request.files.get("avatar")
    if not file or file.filename == "":
        flash("No image selected.")
        return redirect(url_for("settings"))

    try:
        img = Image.open(file.stream)
        img = img.convert("RGB")
        img.thumbnail((240, 240))  # keep the stored doc small
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        data_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        User.update_avatar(current_user.id, data_url)
    except Exception:
        traceback.print_exc()
        flash("Couldn't process that image — try a standard JPG or PNG.")

    return redirect(url_for("settings"))


def generate_study_pack_for_text(raw_text: str) -> dict:
    """Shared by /upload and /upload-url: runs the raw extracted text
    through whichever engine is currently configured (Claude, Gemini, or
    local NLP), with automatic fallback to local NLP if an LLM call fails."""
    provider = config_store.active_provider()
    if provider == "anthropic":
        try:
            study_pack = llm_engine.build_study_pack(raw_text)
            study_pack["engine"] = "claude"
        except Exception:
            traceback.print_exc()
            study_pack = nlp_engine.build_study_pack(raw_text)
            study_pack["engine"] = "nlp-fallback (claude call failed)"
    elif provider == "gemini":
        try:
            study_pack = gemini_engine.build_study_pack(raw_text)
            study_pack["engine"] = "gemini"
        except Exception:
            traceback.print_exc()
            study_pack = nlp_engine.build_study_pack(raw_text)
            study_pack["engine"] = "nlp-fallback (gemini call failed)"
    else:
        study_pack = nlp_engine.build_study_pack(raw_text)
        study_pack["engine"] = "nlp (no API key set)"
    return study_pack


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file was sent."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file was selected."}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 400

    safe_name = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
    file.save(save_path)

    try:
        kind = get_file_kind(file.filename)
        raw_text = extract_text(save_path, file.filename)

        if not raw_text or len(raw_text.strip()) < 150:
            return jsonify({
                "error": (
                    "Couldn't find enough readable text in that file. "
                    "If it's a scanned document, try a clearer image."
                )
            }), 422

        study_pack = generate_study_pack_for_text(raw_text)
        study_pack["sourceType"] = kind
        study_pack["sourceName"] = file.filename

        try:
            upload_id = history.save_upload_record(current_user.id, file.filename, kind, study_pack)
            study_pack["uploadId"] = upload_id
        except Exception:
            # don't fail the whole request just because saving history failed
            # (e.g. MONGODB_URI misconfigured) — the user still gets their results
            traceback.print_exc()

        return jsonify(study_pack)

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": f"Processing failed: {exc}"}), 500

    finally:
        # clean up the uploaded file once we're done with it
        if os.path.exists(save_path):
            os.remove(save_path)


@app.route("/upload-url", methods=["POST"])
@login_required
def upload_url():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "No URL was provided."}), 400

    try:
        raw_text = video_url.extract_text_from_video_url(url)
    except ValueError as e:
        # a clean, expected error (bad URL, no captions, etc) — safe to show as-is
        return jsonify({"error": str(e)}), 400
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": f"Couldn't process that video URL: {exc}"}), 500

    if not raw_text or len(raw_text.strip()) < 150:
        return jsonify({
            "error": "Couldn't find enough spoken content or captions in that video."
        }), 422

    study_pack = generate_study_pack_for_text(raw_text)
    study_pack["sourceType"] = "video_url"
    study_pack["sourceName"] = url

    try:
        upload_id = history.save_upload_record(current_user.id, url, "video_url", study_pack)
        study_pack["uploadId"] = upload_id
    except Exception:
        traceback.print_exc()

    return jsonify(study_pack)


if __name__ == "__main__":
    provider = config_store.active_provider()
    if provider == "anthropic":
        print("[Study Deck] Using Claude.")
    elif provider == "gemini":
        print("[Study Deck] Using Gemini.")
    else:
        print("[Study Deck] No API key set — using local NLP engine. "
              "Visit /settings in the app to add one.")
    app.run(debug=True, host="0.0.0.0", port=5000)
