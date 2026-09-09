"""
config_store.py
Persists API keys to a local JSON file so they survive restarts without
needing environment variables set every time. This is meant for personal,
local use — the file is plain JSON on disk, not encrypted. Don't use this
approach on a shared or publicly-hosted server; use real env vars / a
secrets manager there instead.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "..", "config.json")

DEFAULTS = {
    "anthropic_api_key": "",
    "gemini_api_key": "",
    "preferred_provider": "auto",  # "auto" | "anthropic" | "gemini" | "nlp"
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULTS)


def save_config(data: dict):
    current = load_config()
    current.update({k: v for k, v in data.items() if k in DEFAULTS})
    with open(CONFIG_PATH, "w") as f:
        json.dump(current, f, indent=2)
    # keep permissions tight where the OS supports it (no-op on Windows)
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except Exception:
        pass
    return current


def sync_env_from_config(force: bool = False):
    """Push saved keys into os.environ.
    By default, real env vars the user set in their shell win (so power users
    can still override via shell without editing this file's config.json).
    Pass force=True right after saving via /settings so the new value takes
    effect immediately, even if a stale env var was set earlier in this process."""
    config = load_config()
    if config.get("anthropic_api_key") and (force or not os.environ.get("ANTHROPIC_API_KEY")):
        os.environ["ANTHROPIC_API_KEY"] = config["anthropic_api_key"]
    if config.get("gemini_api_key") and (force or not os.environ.get("GEMINI_API_KEY")):
        os.environ["GEMINI_API_KEY"] = config["gemini_api_key"]
    return config


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return key[:4] + "•" * (len(key) - 8) + key[-4:]


def active_provider():
    """Figure out which provider will actually be used right now,
    respecting: real env vars > saved config keys > local NLP fallback."""
    config = load_config()
    preferred = config.get("preferred_provider", "auto")

    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY") or config.get("anthropic_api_key"))
    has_gemini = bool(os.environ.get("GEMINI_API_KEY") or config.get("gemini_api_key"))

    if preferred == "anthropic" and has_anthropic:
        return "anthropic"
    if preferred == "gemini" and has_gemini:
        return "gemini"
    if preferred == "nlp":
        return "none"

    # auto: prefer Claude if both are set, otherwise whichever is available
    if has_anthropic:
        return "anthropic"
    if has_gemini:
        return "gemini"
    return "none"
