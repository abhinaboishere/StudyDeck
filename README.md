# 📚 Study Deck

**Turn a PDF, a photo, or a YouTube link into flashcards, notes, and a quiz — automatically.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-API-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-API-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![License](https://img.shields.io/badge/License-Personal%20Project-lightgrey?style=for-the-badge)

---

## ✨ What it does

Upload a **PDF** or an **image** of a page, or paste a **YouTube link**, and Study Deck reads it and generates:

| 🃏 Flashcards | 📝 Key Notes | ❓ Quiz |
|---|---|---|
| Clean term/definition pairs, flip to reveal the answer | The most important points, in plain language | Up to ~24 multiple-choice questions with explanations |

Every generated study pack is saved to **My Library**, tied to your account, so you can come back to it later without regenerating anything.

---

## 🧠 Three generation engines

Study Deck can generate content three different ways — you don't have to pick manually, it auto-detects based on what's configured:

| Engine | Quality | Cost | When it's used |
|---|---|---|---|
| 🟣 **Claude** (`utils/llm_engine.py`) | Highest — varied, well-written | Paid | If `ANTHROPIC_API_KEY` is set |
| 🔵 **Gemini** (`utils/gemini_engine.py`) | High — varied, well-written | Free tier available | If `GEMINI_API_KEY` is set and Claude isn't |
| ⚪ **Local NLP** (`utils/nlp_engine.py`) | Good — mechanical (fill-in-the-blank quiz) | Free, fully offline | Automatic fallback if no key is set, or if an API call fails |

Configure keys at **`/admin/config`** (deliberately not linked in the main UI — bookmark it). Every generated study pack records which engine actually produced it.

---

## 🔑 Key features

- 🔐 **Accounts** — email/password signup & login (MongoDB-backed, passwords hashed with werkzeug)
- 🖼️ **Smart image OCR** — uses Gemini's vision model first (no local install needed), falls back to local Tesseract if unavailable
- 🎥 **YouTube video support** — pulls official captions when available; downloads & transcribes audio only if a video has none
- 📚 **My Library** — every past upload saved, searchable by date, one click to revisit, one click to delete
- 🌗 **Dark mode** — persists across sessions
- 🖥️ **Desktop app** — native window via `pywebview`, no browser needed (`python desktop_app.py`)
- 📱 **Android-ready** — wrap it in a WebView app (Android Studio) or install as a PWA
- 🎨 **Custom UI** — glassmorphic cards, animated gradient background, gradient-text branding

---

## 🚀 Setup

### 1. System dependencies

```bash
# ffmpeg — needed for the YouTube audio-transcription fallback
sudo apt-get install ffmpeg        # Linux
brew install ffmpeg                # macOS
# Windows: download from ffmpeg.org and add to PATH
```

> Tesseract OCR is **optional** — only needed as a fallback if you don't set a Gemini key. See [github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki) for the Windows installer.

### 2. Python environment

```bash
python3 -m venv flash_card_env
source flash_card_env/bin/activate      # Windows: flash_card_env\Scripts\activate

pip install -r requirements.txt
python -m spacy download en_core_web_sm   # only needed for the local NLP fallback
```

### 3. Configure secrets — `.env` file

Copy `.env.example` → `.env` and fill in your real values:

```env
MONGODB_URI=mongodb+srv://user:password@your-cluster.mongodb.net/
FLASK_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
```

Free MongoDB Atlas cluster: [mongodb.com/cloud/atlas](https://mongodb.com/cloud/atlas) (M0 tier, free forever).

API keys (Claude / Gemini) are configured **inside the running app** at `/admin/config`, not in `.env` — though you can also set `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` as real environment variables if you'd rather.

### 4. Run it

```bash
python app.py
```

Open **http://localhost:5000** → you'll be sent to `/signup` first.

---

## 🖥️ Desktop app

```bash
pip install pywebview
python desktop_app.py
```

Opens Study Deck in its own native window — no browser tab. See the comment at the top of `desktop_app.py` for optional `PyInstaller` packaging into a standalone `.exe`.

---

## 📱 Android

Two options:

**A) Real APK (Android Studio)** — wrap the running Flask server in a WebView app. Steps and ready-to-paste `MainActivity.kt` / `activity_main.xml` are in the project notes; the short version:
1. New Project → Empty Views Activity (Kotlin)
2. Add `INTERNET` permission + `usesCleartextTraffic="true"` to the manifest
3. Point the WebView at `http://10.0.2.2:5000` (emulator) or your PC's LAN IP (real phone)
4. Build → Build APK(s)

**B) Installable PWA** — "Add to Home Screen" from Chrome. Requires HTTPS (or `localhost`) — for local testing over WiFi, tunnel your server with `ngrok http 5000` to get a temporary HTTPS URL first.

Either way: your phone can only reach the app while your PC is on and `python app.py` is running on the same network. Permanent access from anywhere requires deploying the server (Render, Railway, etc.).

---

## 📁 Project structure

```
flashcard_generator/
├── app.py                    # Flask routes
├── desktop_app.py            # pywebview desktop launcher
├── requirements.txt
├── .env.example               # copy to .env and fill in
├── Procfile                    # for Heroku-style deployment
├── utils/
│   ├── extractors.py           # PDF / image -> raw text
│   ├── video_url.py             # YouTube captions/audio -> raw text
│   ├── nlp_engine.py             # local NLP generation (no API)
│   ├── llm_engine.py              # Claude-powered generation
│   ├── gemini_engine.py            # Gemini-powered generation + vision OCR
│   ├── auth_models.py               # User model (MongoDB + Flask-Login)
│   ├── db.py                         # MongoDB connection
│   ├── history.py                     # saved study packs (My Library)
│   └── config_store.py                 # engine/API-key config persistence
├── templates/
│   ├── login.html · signup.html
│   ├── index.html                       # main app + library-item view
│   ├── settings.html                     # profile picture + logout
│   ├── admin_config.html                  # engine/API key config (unlinked)
│   └── library.html                        # past uploads list
└── static/
    ├── css/style.css                        # glassmorphism + dark mode
    └── js/main.js · theme.js
```

---

## ⚠️ Known limits

- Scanned PDFs with no text layer and no OCR fallback on the PDF path itself won't extract — convert to an image first.
- Gemini's free tier is rate-limited; uploading several files back-to-back may hit it (the quiz generator alone makes 3 API calls per upload).
- YouTube videos with no captions and no clear speech (music-only, heavy background noise) will produce weak or empty results.
- API keys and MongoDB credentials are stored in plain text (`config.json` / `.env`) — fine for personal local use, **not** suitable for a shared or public deployment without switching to real secrets management.
