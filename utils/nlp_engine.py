"""
nlp_engine.py
Pure-NLP pipeline (no LLM calls) that turns raw text into:
- key notes (extractive summary)
- flashcards (key term -> defining sentence)
- a multiple-choice quiz (blank-the-keyword + distractors)
"""

import random
import re
from collections import Counter

import spacy
import nltk
from nltk.tokenize import sent_tokenize
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer as SumyTokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer

from utils.content_counts import get_content_counts

# One-time NLTK data (safe to call repeatedly; no-ops if already present)
for pkg in ("punkt", "punkt_tab"):
    try:
        nltk.data.find(f"tokenizers/{pkg}")
    except LookupError:
        nltk.download(pkg, quiet=True)

_nlp = None


def get_nlp():
    """Lazy-load the spaCy model so app startup stays fast."""
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------- keywords

GENERIC_LEAD_WORDS = {
    "this", "that", "these", "those", "other", "such", "some", "any",
    "each", "every", "another", "the same", "which", "what",
}
GENERIC_HEAD_NOUNS = {
    "process", "stage", "place", "thing", "factor", "factors", "way",
    "part", "kind", "type", "use", "case", "reason", "result", "point",
    "example", "aspect", "issue", "matter", "level",
}


def _is_generic_chunk(chunk_doc) -> bool:
    """Filter out low-information noun chunks like 'this stage' or 'other factors'."""
    tokens = [t.text.lower() for t in chunk_doc]
    if not tokens:
        return True
    if tokens[0] in GENERIC_LEAD_WORDS:
        return True
    root = chunk_doc.root.lemma_.lower()
    if root in GENERIC_HEAD_NOUNS and len(tokens) <= 2:
        return True
    return False


def extract_keywords(text: str, top_n: int = 15):
    """Rank candidate terms (nouns, proper nouns, named entities) by frequency."""
    nlp = get_nlp()
    doc = nlp(text)

    candidates = []
    for chunk in doc.noun_chunks:
        term = chunk.text.strip()
        if 2 <= len(term) <= 40 and term.lower() not in ENGLISH_STOP_TERMS and not _is_generic_chunk(chunk):
            candidates.append(term.lower())
    for ent in doc.ents:
        if ent.label_ in ("PERSON", "ORG", "GPE", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "NORP"):
            candidates.append(ent.text.strip().lower())

    freq = Counter(candidates)
    ranked = [term for term, _ in freq.most_common(top_n * 2)]

    # de-duplicate near-identical terms (e.g. "the cell" vs "cell")
    seen = set()
    final = []
    for term in ranked:
        stripped = re.sub(r"^(the|a|an)\s+", "", term)
        if stripped in seen or len(stripped) < 3:
            continue
        seen.add(stripped)
        final.append(stripped)
        if len(final) >= top_n:
            break
    return final


ENGLISH_STOP_TERMS = {
    "it", "this", "that", "these", "those", "he", "she", "they", "we", "i",
    "you", "there", "what", "which", "who", "something", "someone", "anything",
}


# ---------------------------------------------------------------- notes

def generate_notes(text: str, count: int = 7):
    """Extractive summary via LexRank -> top N standalone sentences."""
    parser = PlaintextParser.from_string(text, SumyTokenizer("english"))
    summarizer = LexRankSummarizer()
    sentences = summarizer(parser.document, count)
    notes = [str(s).strip() for s in sentences if len(str(s).strip()) > 15]
    if not notes:
        # fallback: just take the first few real sentences
        notes = sent_tokenize(text)[:count]
    return notes


# ---------------------------------------------------------------- flashcards

def _sentence_for_term(term: str, sentences):
    term_l = term.lower()
    for s in sentences:
        if term_l in s.lower():
            return s.strip()
    return None


def generate_flashcards(text: str, count: int = 10):
    sentences = sent_tokenize(text)
    keywords = extract_keywords(text, top_n=count * 2)

    cards = []
    used_sentences = set()
    for term in keywords:
        sentence = _sentence_for_term(term, sentences)
        if not sentence or sentence in used_sentences:
            continue
        used_sentences.add(sentence)
        cards.append({
            "front": term.title(),
            "back": sentence,
        })
        if len(cards) >= count:
            break
    return cards


# ---------------------------------------------------------------- quiz

def generate_quiz(text: str, count: int = 6):
    sentences = [s for s in sent_tokenize(text) if 40 <= len(s) <= 220]
    keywords = extract_keywords(text, top_n=count * 3)

    quiz = []
    used_terms = set()
    for term in keywords:
        sentence = _sentence_for_term(term, sentences)
        if not sentence or term in used_terms:
            continue

        pattern = re.compile(re.escape(term), re.IGNORECASE)
        if not pattern.search(sentence):
            continue

        blanked = pattern.sub("_____", sentence, count=1)
        used_terms.add(term)

        # Build distractors from other keywords, same rough word-length bucket
        pool = [k for k in keywords if k != term and k not in used_terms]
        random.shuffle(pool)
        distractors = pool[:3]
        while len(distractors) < 3:
            distractors.append(random.choice(keywords))

        options = [term.title()] + [d.title() for d in distractors]
        random.shuffle(options)
        correct_index = options.index(term.title())

        quiz.append({
            "question": f"Fill in the blank: {blanked}",
            "options": options,
            "correctIndex": correct_index,
            "explanation": f'The original sentence reads: "{sentence}"',
        })
        if len(quiz) >= count:
            break
    return quiz


# ---------------------------------------------------------------- pipeline

def build_study_pack(raw_text: str):
    text = clean_text(raw_text)
    if len(text) < 150:
        raise ValueError(
            "Not enough readable text was found in this file to build a study pack."
        )
    # Cap very large documents so processing stays snappy
    text = text[:20000]
    counts = get_content_counts(text)

    return {
        "notes": generate_notes(text, count=counts["notes"]),
        "cards": generate_flashcards(text, count=counts["cards"]),
        "quiz": generate_quiz(text, count=counts["quiz"]),
    }
