"""
Copyright (c) Cutleast
"""

from pathlib import Path

from requests_mock import Mocker as RequestsMock

from core.config.translator_config import TranslatorConfig
from core.translator.local_llm import LMStudioTranslator, OllamaTranslator
from core.utilities.game_language import GameLanguage


class TestLocalLlmTranslator:
    """
    Tests local LLM translator APIs.
    """

    def test_ollama_translate(self, requests_mock: RequestsMock) -> None:
        """
        Tests translating a text with Ollama.
        """

        # given
        config = TranslatorConfig(_config_path=Path("."), llm_model="mistral")
        requests_mock.post(
            "http://localhost:11434/api/generate",
            json={"response": "Hallo Welt"},
        )

        # when
        result: str = OllamaTranslator(config).translate_uncached(
            "Hello World", GameLanguage.German
        )

        # then
        assert result == "Hallo Welt"
        request = requests_mock.last_request
        assert request is not None
        assert request.json()["model"] == "mistral"
        assert request.json()["stream"] is False

    def test_ollama_available_models(self, requests_mock: RequestsMock) -> None:
        """
        Tests listing running Ollama models.
        """

        # given
        config = TranslatorConfig(_config_path=Path("."))
        requests_mock.get(
            "http://localhost:11434/api/ps",
            json={"models": [{"model": "mistral"}, {"name": "llama3.1"}]},
        )

        # when
        result: list[str] = OllamaTranslator(config).get_available_models()

        # then
        assert result == ["mistral", "llama3.1"]

    def test_openai_compatible_translate(self, requests_mock: RequestsMock) -> None:
        """
        Tests translating a text with an OpenAI-compatible local API.
        """

        # given
        config = TranslatorConfig(
            _config_path=Path("."),
            llm_base_url="http://localhost:1234",
            llm_model="qwen2.5",
        )
        requests_mock.post(
            "http://localhost:1234/v1/chat/completions",
            json={"choices": [{"message": {"content": "Bonjour"}}]},
        )

        # when
        result: str = LMStudioTranslator(config).translate_uncached(
            "Hello", GameLanguage.French
        )

        # then
        assert result == "Bonjour"
        request = requests_mock.last_request
        assert request is not None
        assert request.json()["model"] == "qwen2.5"
        assert request.json()["messages"][0]["role"] == "system"

    def test_openai_compatible_available_models(
        self, requests_mock: RequestsMock
    ) -> None:
        """
        Tests listing OpenAI-compatible local API models.
        """

        # given
        config = TranslatorConfig(
            _config_path=Path("."),
            llm_base_url="http://localhost:1234",
        )
        requests_mock.get(
            "http://localhost:1234/v1/models",
            json={"data": [{"id": "qwen2.5"}, {"id": "mistral"}]},
        )

        # when
        result: list[str] = LMStudioTranslator(config).get_available_models()

        # then
        assert result == ["qwen2.5", "mistral"]
