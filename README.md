<<<<<<< HEAD
# StudyDeck
=======
# Study Deck — Smart Flashcard Generator (Flask + Claude)

Upload a PDF, an image, an audio file, or a video, and this app pulls out the
text (via a text layer, OCR, or speech-to-text) and generates:

- **Flashcards** — clean, well-written term/definition pairs
- **Key notes** — the most important points, written in plain language
- **A quiz** — varied multiple-choice questions (not just fill-in-the-blank), with explanations

## Two generation engines

- **LLM engine** (`utils/llm_engine.py`) — calls the Claude API for genuinely
  well-written, varied output. This is what runs whenever an `ANTHROPIC_API_KEY`
  is set in the environment. **This is the recommended mode.**
- **Local NLP engine** (`utils/nlp_engine.py`) — spaCy + sumy + NLTK, no API
  calls, no cost, works offline. Output is more mechanical (e.g. quiz
  questions are fill-in-the-blank). This automatically kicks in if no API key
  is found, or as a silent fallback if an LLM call ever fails.

You don't need to choose manually — `app.py` checks for the API key at
startup and picks the engine accordingly, and the response JSON includes an
`"engine"` field so you can see which one ran.

## Three generation engines

- **Claude** (`utils/llm_engine.py`) — used automatically if `ANTHROPIC_API_KEY` is set.
- **Gemini** (`utils/gemini_engine.py`) — used automatically if `GEMINI_API_KEY` is set
  and `ANTHROPIC_API_KEY` is not. Google AI Studio has a usable free tier, so this is
  the no-cost way to get LLM-quality output.
- **Local NLP** (`utils/nlp_engine.py`) — spaCy + sumy + NLTK, no API calls, no cost,
  fully offline. Used automatically if neither key is set, and as a silent fallback if
  an LLM call ever throws (network error, rate limit, bad response, etc).

`app.py` picks the engine at startup based on which key is present, and every response
includes an `"engine"` field so you can always see which one actually ran — the UI
shows it right under the file name after upload. If you ever see the fill-in-the-blank
quiz style when you expected an LLM, check that field first: it means the key wasn't
picked up, or the LLM call failed and it silently fell back.

### Getting a free Gemini key

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in.
2. Create an API key.
3. Set it before running the app:

```bash
export GEMINI_API_KEY=AIza...        # macOS/Linux
setx GEMINI_API_KEY "AIza..."        # Windows
```

The free tier is rate-limited (check Google AI Studio for current limits) but fine for
personal use. `utils/gemini_engine.py` calls `gemini-3.6-flash` — if Google renames or
retires that model, just change the `MODEL` constant at the top of the file.

### Getting a Claude key (paid, higher quality ceiling)

Sign up / log in at [console.anthropic.com](https://console.anthropic.com),
create an API key, then set it before running the app:

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # macOS/Linux
setx ANTHROPIC_API_KEY "sk-ant-..."        # Windows
```

Each upload makes 3 API calls (notes, cards, quiz) using `claude-sonnet-5`.
Text sent per call is capped at 20,000 characters to keep cost predictable —
see [Anthropic's pricing page](https://www.anthropic.com/pricing) for current rates.

## How each file type is handled

| Type  | Extensions | Extraction method |
|-------|-----------|--------------------|
| PDF   | `.pdf` | `pdfplumber` reads the text layer |
| Image | `.png .jpg .jpeg .bmp .tiff .webp` | `pytesseract` OCR |
| Audio | `.wav .mp3 .m4a .ogg .flac` | `SpeechRecognition` (Google Web Speech API), chunked in ~55s windows |
| Video | `.mp4 .mov .avi .mkv .webm` | `moviepy` extracts the audio track, then the audio pipeline above runs on it |

The NLP layer (`utils/nlp_engine.py`) uses **spaCy** for keyword/entity
extraction, **sumy** (LexRank) for summarization, and **NLTK** for sentence
tokenizing — all local, nothing sent to an external AI API.

## Setup

### 1. System dependencies (required — these are not pip packages)

```bash
# Tesseract OCR (for image uploads)
sudo apt-get install tesseract-ocr

# ffmpeg (for audio/video handling via pydub + moviepy)
sudo apt-get install ffmpeg
```

On macOS: `brew install tesseract ffmpeg`

On Windows, install Tesseract OCR from the [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki),
or run:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

If it is installed in a non-standard location, set `TESSERACT_CMD` to the full
path of `tesseract.exe` before starting Flask.

### 2. Python environment

```bash
python3 -m venv flash_card_env
source flash_card_env/bin/activate      # Windows: flash_card_env\Scripts\activate

pip install -r requirements.txt
python -m spacy download en_core_web_sm   # only needed for the local NLP fallback
```

### 3. Set your API key (for LLM-quality output — recommended)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Run it

```bash
python app.py
```

Then open **http://localhost:5000**.

## Notes on the speech-to-text step

`SpeechRecognition`'s `recognize_google` uses Google's free Web Speech API,
which requires an internet connection at runtime and is rate-limited — fine
for personal/small-scale use, not for heavy production traffic. For
production use or offline transcription, swap `extract_text_from_audio` in
`utils/extractors.py` for a local model (e.g. `openai-whisper` or
`faster-whisper`) — the rest of the pipeline (NLP, flashcards, quiz) doesn't
need to change.

## Project structure

```
flashcard_generator/
├── app.py                 # Flask routes
├── requirements.txt
├── Procfile                # for Heroku-style deployment
├── utils/
│   ├── extractors.py       # PDF / image / audio / video -> raw text
│   └── nlp_engine.py       # raw text -> notes / flashcards / quiz
├── templates/
│   └── index.html
├── static/
│   ├── css/style.css
│   └── js/main.js
└── uploads/                # temp storage, files are deleted after processing
```

## Known limits

- Scanned PDFs with no text layer and no OCR fallback on the PDF path itself
  won't extract — convert to an image first, or extend `extract_text_from_pdf`
  to OCR each page as a fallback.
- Very long audio/video files will take a while — each ~55s chunk is a
  separate API call to the speech recognizer.
- Quiz distractors are drawn from other keywords in the same document, so
  very short or narrow documents may produce fewer/weaker quiz questions.
>>>>>>> e0b077b (Initial Study Deck deployment)
