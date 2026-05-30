"""
Copyright (c) Cutleast
"""

from enum import Enum


class TranslatorApi(Enum):
    """Enum for available translator APIs."""

    Google = "Google Translator"
    """Google translator API (free)."""

    DeepL = "DeepL"
    """DeepL translator API (requires API key)."""

    Ollama = "Ollama"
    """Local Ollama API."""

    LMStudio = "LM Studio"
    """Local LM Studio OpenAI-compatible API."""

    LlamaCpp = "llama.cpp"
    """Local llama.cpp OpenAI-compatible API."""
