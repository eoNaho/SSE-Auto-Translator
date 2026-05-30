"""
Copyright (c) Cutleast
"""

from __future__ import annotations

from typing import Any, final, override

import requests as req
from cutleast_core_lib.core.utilities.hash import sha256_hash

from core.utilities.game_language import GameLanguage

from .translator import Translator


class LocalLlmTranslator(Translator):
    """
    Base class for local LLM translator APIs.
    """

    DEFAULT_BASE_URL: str
    DEFAULT_MODEL: str

    @property
    def base_url(self) -> str:
        return (self._config.llm_base_url.strip() or self.DEFAULT_BASE_URL).rstrip("/")

    @property
    def model(self) -> str:
        return self._config.llm_model.strip() or self.DEFAULT_MODEL

    def get_available_models(self) -> list[str]:
        """
        Lists currently available models for this local LLM provider.

        Returns:
            list[str]: Model IDs that can be used in translation requests.
        """

        return []

    def _build_prompt(self, text: str, dst: GameLanguage) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a professional game localization translator. "
                    f"Translate English game text to {dst.value}. Preserve all "
                    "placeholders, variables, XML/HTML tags, quote characters, escape "
                    "sequences, whitespace, and line breaks exactly unless the text "
                    "itself must be translated. Keep proper nouns, item names, quest "
                    "names, and Skyrim lore terms unchanged when translating them would "
                    "make them less precise. Do not summarize, explain, add notes, or "
                    "wrap the answer in quotes. Return only the final translated text."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Translate this exact string. Output only the translation:\n" + text
                ),
            },
        ]

    def _clean_translation(self, text: str) -> str:
        cleaned = text.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
            cleaned = cleaned[1:-1].strip()
        return cleaned

    @override
    def get_cache_id(self, text: str, dst: GameLanguage) -> str:
        data = (
            f"{self.__class__.__name__}-{self.base_url}-{self.model}-"
            f"{self._config.llm_temperature}-{text}-{dst.name}"
        )

        return sha256_hash(data.encode())


@final
class OllamaTranslator(LocalLlmTranslator):
    """
    API class for translating texts with a local Ollama server.
    """

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama3.1"

    @override
    def get_available_models(self) -> list[str]:
        response = req.get(
            f"{self.base_url}/api/ps",
            timeout=self._config.llm_timeout,
        )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        models = data.get("models", [])
        if not isinstance(models, list):
            return []

        result: list[str] = []
        for model in models:
            if not isinstance(model, dict):
                continue

            name = model.get("model") or model.get("name")
            if isinstance(name, str):
                result.append(name)

        return result

    @override
    def translate_uncached(self, text: str, dst: GameLanguage) -> str:
        prompt = self._build_prompt(text, dst)
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt[1]["content"],
            "system": prompt[0]["content"],
            "stream": False,
            "options": {
                "temperature": self._config.llm_temperature,
            },
        }

        response = req.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self._config.llm_timeout,
        )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        translation = data.get("response")
        if not isinstance(translation, str):
            raise RuntimeError("Ollama response did not contain a text translation.")

        return self._clean_translation(translation)


class OpenAICompatibleTranslator(LocalLlmTranslator):
    """
    Base class for local OpenAI-compatible chat completion APIs.
    """

    @override
    def get_available_models(self) -> list[str]:
        response = req.get(
            f"{self.base_url}/v1/models",
            timeout=self._config.llm_timeout,
        )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        models = data.get("data", [])
        if not isinstance(models, list):
            return []

        result: list[str] = []
        for model in models:
            if not isinstance(model, dict):
                continue

            name = model.get("id")
            if isinstance(name, str):
                result.append(name)

        return result

    @override
    def translate_uncached(self, text: str, dst: GameLanguage) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._build_prompt(text, dst),
            "temperature": self._config.llm_temperature,
            "stream": False,
        }

        response = req.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=self._config.llm_timeout,
        )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        try:
            translation = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError(
                "OpenAI-compatible response did not contain a text translation."
            ) from error

        if not isinstance(translation, str):
            raise RuntimeError(
                "OpenAI-compatible response did not contain a text translation."
            )

        return self._clean_translation(translation)


@final
class LMStudioTranslator(OpenAICompatibleTranslator):
    """
    API class for translating texts with LM Studio's local server.
    """

    DEFAULT_BASE_URL = "http://localhost:1234"
    DEFAULT_MODEL = "local-model"


@final
class LlamaCppTranslator(OpenAICompatibleTranslator):
    """
    API class for translating texts with llama.cpp's llama-server.
    """

    DEFAULT_BASE_URL = "http://localhost:8080"
    DEFAULT_MODEL = "local-model"
