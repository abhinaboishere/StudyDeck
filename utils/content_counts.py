"""Choose study-pack sizes based on the amount of source content."""


def get_content_counts(text: str):
    """Return practical, content-dependent targets for generated material."""
    word_count = len(text.split())

    return {
        "notes": max(3, min(15, round(word_count / 140))),
        "cards": max(3, min(50, round(word_count / 70))),
        "quiz": max(3, min(20, round(word_count / 110))),
    }