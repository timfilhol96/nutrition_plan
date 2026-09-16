"""Runtime configuration.

Defaults live here. Any value can be overridden by a key of the same name in
st.secrets, so model names never need to be edited in code.
"""

import streamlit as st

DEFAULTS = {
    # Primary LLM provider (free tier).
    "GROQ_BASE_URL": "https://api.groq.com/openai/v1",
    "GROQ_MODEL": "openai/gpt-oss-20b",
    # Fallback LLM provider; must be a ":free" model.
    "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
    "OPENROUTER_MODEL": "google/gemma-4-31b-it:free",
    "LLM_TIMEOUT_S": 20.0,
    "LLM_SESSION_CAP": 30,
    "PROVIDER_COOLDOWN_S": 60.0,
    "MAX_ROW_CHARS": 120,
    "MAX_ROWS_PER_MEAL": 20,
    "USDA_CANDIDATES": 5,
}

# Cache lifetimes are needed at import time (decorators), so they are not overridable.
CACHE_TTL_S = 24 * 3600


def secret(name: str, default=None):
    """Read a key from st.secrets, tolerating a missing key or secrets file."""
    try:
        return st.secrets[name]
    except (KeyError, FileNotFoundError):
        return default


def setting(name: str):
    return secret(name, DEFAULTS[name])
