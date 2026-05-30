"""
Copyright (c) Cutleast
"""

from typing import Annotated, Optional, override

from cutleast_core_lib.core.config.base_config import BaseConfig

from core.translator.apis import TranslatorApi


class TranslatorConfig(BaseConfig):
    """
    Class for translator settings.
    """

    translator: TranslatorApi = TranslatorApi.Google
    """The translator API to use for machine translations."""

    api_key: Annotated[Optional[str], BaseConfig.PropertyMarker.ExcludeFromLogging] = (
        None
    )
    """The API key for the translator API."""

    llm_base_url: str = ""
    """
    Base URL for local LLM translator APIs.

    Leave blank to use the default URL for the selected local provider.
    """

    llm_model: str = ""
    """
    Model name for local LLM translator APIs.

    Leave blank to use the provider default.
    """

    llm_timeout: int = 120
    """Timeout in seconds for local LLM translator API requests."""

    llm_temperature: float = 0.1
    """Sampling temperature for local LLM translator API requests."""

    show_confirmation_dialogs: bool = True
    """Whether to ask for confirmation before starting a machine translation."""

    @override
    @staticmethod
    def get_config_name() -> str:
        return "translator/config.json"
