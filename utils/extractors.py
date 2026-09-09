"""
extractors.py
Pulls raw text out of an uploaded file:
PDF -> text layer, Image -> OCR (Gemini vision, or local Tesseract fallback).

Audio/video file uploads were removed in favor of pasting a video URL
instead (see utils/video_url.py) — that path calls extract_text_from_audio()
directly on a downloaded .wav file, so it's kept here as a shared helper
even though it's no longer reachable via a direct file upload.
"""

import os
import tempfile

import pdfplumber
from PIL import Image
import pytesseract
import speech_recognition as sr
from pydub import AudioSegment

PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


def get_file_kind(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in PDF_EXTS:
        return "pdf"
    if ext in IMAGE_EXTS:
        return "image"
    raise ValueError(f"Unsupported file type: {ext}")


def extract_text_from_pdf(path: str) -> str:
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:60]:  # cap runaway documents
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts).strip()


def extract_text_from_image(path: str) -> str:
    """Try Gemini's vision API first (no local install needed) — falls back
    to local Tesseract OCR only if no Gemini key is configured, or if the
    API call fails for some reason (offline, rate-limited, etc)."""
    ext = os.path.splitext(path)[1].lower()

    if os.environ.get("GEMINI_API_KEY"):
        try:
            from utils.gemini_engine import extract_text_from_image as gemini_ocr
            text = gemini_ocr(path, ext)
            if text:
                return text
        except Exception as e:
            print(f"[extractors] Gemini vision OCR failed, falling back to local Tesseract: {e}")

    # local fallback — requires the Tesseract program installed separately
    # (not a pip package). See README for install instructions.
    image = Image.open(path)
    return pytesseract.image_to_string(image).strip()


def _wav_from_any_audio(path: str) -> str:
    """Convert any supported audio format to a temp wav file pydub/SR can read."""
    audio = AudioSegment.from_file(path)
    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio.export(tmp_wav.name, format="wav")
    return tmp_wav.name


def extract_text_from_audio(path: str) -> str:
    wav_path = _wav_from_any_audio(path)
    recognizer = sr.Recognizer()
    full_text = []
    try:
        with sr.AudioFile(wav_path) as source:
            # chunk long audio into ~55s windows so recognition stays reliable
            duration = source.DURATION
            chunk_len = 55
            offset = 0
            while offset < duration:
                audio_data = recognizer.record(source, duration=chunk_len)
                try:
                    text = recognizer.recognize_google(audio_data)
                    full_text.append(text)
                except sr.UnknownValueError:
                    pass  # silent/unclear chunk, skip
                except sr.RequestError as e:
                    raise RuntimeError(f"Speech recognition service error: {e}")
                offset += chunk_len
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
    return " ".join(full_text).strip()


def extract_text(path: str, filename: str) -> str:
    kind = get_file_kind(filename)
    if kind == "pdf":
        return extract_text_from_pdf(path)
    if kind == "image":
        return extract_text_from_image(path)
    raise ValueError("Unhandled file kind")
