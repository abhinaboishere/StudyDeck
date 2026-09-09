"""
video_url.py
Given a YouTube URL, extracts text either from the video's official
captions/transcript (fast, no download needed) or, if none exist, by
downloading just the audio track and running speech-to-text on it.

Uses youtube-transcript-api (v1.x API — instance-based, not the old
static YouTubeTranscriptApi.get_transcript()) and yt-dlp as the
audio-download fallback.
"""

import os
import re
import tempfile

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled, NoTranscriptFound, VideoUnavailable,
)

from utils.extractors import extract_text_from_audio

YOUTUBE_PATTERNS = [
    r"(?:youtube\.com/watch\?v=|youtube\.com/shorts/|youtu\.be/|youtube\.com/embed/)([\w-]{11})",
]


def extract_video_id(url: str):
    for pattern in YOUTUBE_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _fetch_transcript(video_id: str) -> str:
    fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en"])
    return " ".join(snippet.text for snippet in fetched).strip()


def _download_audio_and_transcribe(url: str) -> str:
    import yt_dlp

    tmp_dir = tempfile.mkdtemp()
    out_template = os.path.join(tmp_dir, "audio.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    for fname in os.listdir(tmp_dir):
        if fname.endswith(".wav"):
            wav_path = os.path.join(tmp_dir, fname)
            try:
                return extract_text_from_audio(wav_path)
            finally:
                os.remove(wav_path)

    raise RuntimeError("yt-dlp finished but no audio file was found afterward.")


def extract_text_from_video_url(url: str) -> str:
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(
            "That doesn't look like a valid YouTube URL. "
            "Expected something like youtube.com/watch?v=... or youtu.be/..."
        )

    try:
        text = _fetch_transcript(video_id)
        if text:
            return text
    except (TranscriptsDisabled, NoTranscriptFound):
        pass  # no captions on this video — fall through to audio download
    except VideoUnavailable:
        raise ValueError("That video is unavailable (private, deleted, or region-locked).")
    except Exception as e:
        print(f"[video_url] transcript fetch failed, trying audio download instead: {e}")

    # no usable captions — download audio and run speech-to-text on it
    return _download_audio_and_transcribe(url)
