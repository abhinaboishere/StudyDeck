"""
llm_engine.py
Same job as nlp_engine.py — turn raw extracted text into notes,
flashcards, and a quiz — but using the Claude API for LLM-quality
output instead of local NLP heuristics.

Requires the ANTHROPIC_API_KEY environment variable to be set.
Get a key at https://console.anthropic.com
"""

import json
import os

from anthropic import Anthropic

from utils.content_counts import get_content_counts

MODEL = "claude-sonnet-5"

_client = None


def get_client():
    global _client
    if _client is None:
        _client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    return _client


def _call_claude(system_prompt: str, user_text: str, max_tokens: int = 1500):
    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    cleaned = text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


def generate_notes(text: str, count: int = 7):
    system = (
        "You are a study assistant. Read the provided source text and extract the "
        f"up to {count} distinct, important points a student should remember. "
        "Generate as many as the source supports without repetition. Respond with ONLY "
        "a JSON array of strings, each a clear, self-contained point (1-2 sentences). "
        "No markdown, no preamble, no extra keys — just the JSON array."
    )
    try:
        result = _call_claude(system, text)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def generate_cards(text: str, count: int = 10):
    system = (
        "You are a study assistant. Read the provided source text and create "
        f"up to {count} distinct flashcards for the most important terms, concepts, "
        "or facts. Generate as many as the source supports without repetition. "
        'Respond with ONLY a JSON array of objects shaped as '
        '{"front": "term or question", "back": "concise, well-written answer or '
        'definition in your own words"}. No markdown, no preamble — just the JSON array.'
    )
    try:
        max_tokens = min(8000, max(2000, count * 160))
        result = _call_claude(system, text, max_tokens=max_tokens)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def generate_quiz(text: str, count: int = 6):
    system = (
        "You are a study assistant. Read the provided source text and write a "
        f"up to {count} distinct multiple-choice questions testing understanding of it "
        "— generate as many as the source supports without repetition and vary "
        "the question style (conceptual, application, comparison), don't just do "
        'fill-in-the-blank. Respond with ONLY a JSON array of objects shaped as '
        '{"question": "...", "options": ["...", "...", "...", "..."], '
        '"correctIndex": 0, "explanation": "short reason the correct answer is right"}. '
        "correctIndex is the 0-based index into options. No markdown, no preamble — "
        "just the JSON array."
    )
    try:
        max_tokens = min(8000, max(3000, count * 220))
        result = _call_claude(system, text, max_tokens=max_tokens)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def build_study_pack(raw_text: str):
    text = raw_text.strip()
    if len(text) < 150:
        raise ValueError(
            "Not enough readable text was found in this file to build a study pack."
        )
    text = text[:20000]  # keep a lid on token usage / cost per request
    counts = get_content_counts(text)

    return {
        "notes": generate_notes(text, counts["notes"]),
        "cards": generate_cards(text, counts["cards"]),
        "quiz": generate_quiz(text, counts["quiz"]),
    }
