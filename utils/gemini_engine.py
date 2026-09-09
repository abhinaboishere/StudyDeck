"""
gemini_engine.py
Same job as llm_engine.py (Claude) and nlp_engine.py (local) — turn raw
extracted text into notes, flashcards, and a quiz — but using Google's
Gemini API, which has a usable free tier.

Requires the GEMINI_API_KEY environment variable.
Get a free key at https://aistudio.google.com/apikey

Model: gemini-3.6-flash. Google retired gemini-2.5-flash for new API keys
in mid-2026; if this model also gets retired later, change MODEL below —
everything else in this file stays the same. Check
https://ai.google.dev/gemini-api/docs/models for the current lineup if
you hit another 404 "no longer available" error.
"""

import json
import os
import re
import time
import traceback

import requests

MODEL = "gemini-3.6-flash"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

IMAGE_MIME_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".bmp": "image/bmp", ".tiff": "image/tiff", ".webp": "image/webp",
}


def extract_text_from_image(path: str, ext: str) -> str:
    """Uses Gemini's vision capability to transcribe text straight out of an
    image — no local OCR program (Tesseract) required. Raises on failure so
    the caller can fall back to local OCR if one is available."""
    import base64

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    mime_type = IMAGE_MIME_TYPES.get(ext.lower(), "image/jpeg")
    with open(path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("ascii")

    payload = {
        "contents": [{
            "parts": [
                {"text": "Transcribe all readable text in this image, verbatim, "
                          "in reading order. Output only the transcribed text — "
                          "no commentary, no markdown, no descriptions of the image."},
                {"inline_data": {"mime_type": mime_type, "data": image_b64}},
            ]
        }],
        "generationConfig": {"maxOutputTokens": 4096, "temperature": 0.1},
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=60)
    if not resp.ok:
        raise RuntimeError(f"Gemini vision API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini vision returned no candidates: {json.dumps(data)[:500]}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    return text.strip()


def _extract_json_array(text: str):
    """Be forgiving about extra prose, code fences, or truncation (hitting
    the token limit mid-array) around the JSON array the model was asked
    to return."""
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("[")
    if start == -1:
        raise ValueError(f"No JSON array found in model output: {cleaned[:300]!r}")
    body = cleaned[start:]

    end = body.rfind("]")
    if end != -1:
        try:
            return json.loads(body[:end + 1])
        except json.JSONDecodeError:
            pass

    # likely truncated mid-object (hit the token limit) — trim back to the
    # last fully-closed object and close the array there instead of failing
    cursor = len(body)
    while True:
        last_close = body.rfind("}", 0, cursor)
        if last_close == -1:
            break
        candidate = body[:last_close + 1] + "]"
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            cursor = last_close
            continue

    raise ValueError(f"Could not find a JSON array in model output: {body[:300]!r}")


def _call_gemini(system_prompt: str, user_text: str, max_output_tokens: int = 2000):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_text}]}],
        "generationConfig": {
            "maxOutputTokens": max_output_tokens,
            "temperature": 0.4,
        },
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=60)

    if not resp.ok:
        # surface Google's actual error body instead of a generic HTTPError
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {json.dumps(data)[:500]}")

    finish_reason = candidates[0].get("finishReason")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)

    if not text.strip():
        raise RuntimeError(
            f"Gemini returned an empty response (finishReason={finish_reason}). "
            f"Full response: {json.dumps(data)[:500]}"
        )

    try:
        return _extract_json_array(text)
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(
            f"Could not parse Gemini's response as JSON (finishReason={finish_reason}): "
            f"{e}. Raw text: {text[:500]!r}"
        )


def generate_notes(text: str, count: int = 7):
    system = (
        "You are a study assistant. Read the provided source text and extract the "
        f"{count} most important points a student should remember. Respond with ONLY "
        "a JSON array of strings, each a clear, self-contained point written in your "
        "own words (1-2 sentences). No markdown, no preamble, no extra keys — just "
        "the JSON array."
    )
    try:
        result = _call_gemini(system, text)
        return result if isinstance(result, list) else []
    except Exception:
        print("[gemini_engine] generate_notes failed:")
        traceback.print_exc()
        return []


def generate_cards(text: str, count: int = 10):
    system = (
        "You are a study assistant. Read the provided source text and create "
        f"{count} flashcards for the most important terms, concepts, or facts. "
        'Respond with ONLY a JSON array of objects shaped as '
        '{"front": "term or question", "back": "concise, well-written answer or '
        'definition in your own words"}. No markdown, no preamble — just the JSON array.'
    )
    try:
        result = _call_gemini(system, text)
        return result if isinstance(result, list) else []
    except Exception:
        print("[gemini_engine] generate_cards failed:")
        traceback.print_exc()
        return []


def generate_quiz(text: str, target_count: int = 24, batch_size: int = 8):
    """Generates up to target_count questions across multiple smaller API
    calls instead of one big one. A single call asking for 24-30 detailed
    questions reliably hits the token ceiling and truncates; asking for
    ~8 at a time is far more likely to complete cleanly, and doing it in
    batches means one truncated/failed batch doesn't cost you the whole quiz."""
    system_template = (
        "You are a study assistant. Read the provided source text and write {n} "
        "multiple-choice questions testing understanding of it — vary the question "
        "style (conceptual, application, comparison), don't just do fill-in-the-blank. "
        'Respond with ONLY a JSON array of objects shaped as '
        '{{"question": "...", "options": ["...", "...", "...", "..."], '
        '"correctIndex": 0, "explanation": "one short sentence, under 15 words"}}. '
        "correctIndex is the 0-based index into options. Keep every field concise "
        "so the full array fits comfortably in the response.{avoid} "
        "No markdown, no preamble — just the JSON array."
    )

    all_questions = []
    seen = set()
    num_batches = -(-target_count // batch_size)  # ceil division

    for batch_num in range(num_batches):
        remaining = target_count - len(all_questions)
        if remaining <= 0:
            break
        this_batch_size = min(batch_size, remaining)

        avoid_clause = ""
        if all_questions:
            prior = [q.get("question", "") for q in all_questions[-15:] if q.get("question")]
            if prior:
                avoid_clause = (
                    " Do not repeat or closely rephrase any of these already-used "
                    "questions: " + " | ".join(prior)
                )

        system = system_template.format(n=this_batch_size, avoid=avoid_clause)

        try:
            batch = _call_gemini(system, text, max_output_tokens=4096)
        except Exception:
            print(f"[gemini_engine] generate_quiz batch {batch_num + 1} failed:")
            traceback.print_exc()
            continue  # one bad batch shouldn't sink the whole quiz

        if isinstance(batch, list):
            for q in batch:
                qtext = (q.get("question") or "").strip().lower()
                if not qtext or qtext in seen:
                    continue
                seen.add(qtext)
                all_questions.append(q)

        if batch_num < num_batches - 1:
            time.sleep(1.5)  # be gentle on free-tier rate limits between calls

    return all_questions


def build_study_pack(raw_text: str):
    text = raw_text.strip()
    if len(text) < 150:
        raise ValueError(
            "Not enough readable text was found in this file to build a study pack."
        )
    text = text[:20000]

    return {
        "notes": generate_notes(text),
        "cards": generate_cards(text),
        "quiz": generate_quiz(text, target_count=24, batch_size=8),
    }

