"""
Copyright (c) Cutleast
"""

from copy import copy

import pytest
from cutleast_core_lib.test.utils import Utils
from cutleast_core_lib.ui.widgets.enum_selector import EnumSelector
from cutleast_core_lib.ui.widgets.key_edit import KeyLineEdit
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit, QSpinBox
from pytestqt.qtbot import QtBot

from core.config.translator_config import TranslatorConfig
from core.translator.apis import TranslatorApi
from core.user_data.user_data import UserData
from tests.base_test import BaseTest
from ui.settings.translator_settings import TranslatorSettings


class TestTranslatorSettings(BaseTest):
    """
    Tests `ui.settings.translator_settings.TranslatorSettings`.
    """

    API_SELECTOR: tuple[str, type[EnumSelector[TranslatorApi]]] = (
        "api_selector",
        EnumSelector[TranslatorApi],
    )
    API_KEY_ENTRY: tuple[str, type[KeyLineEdit]] = "api_key_entry", KeyLineEdit
    LLM_BASE_URL_ENTRY: tuple[str, type[QLineEdit]] = (
        "llm_base_url_entry",
        QLineEdit,
    )
    LLM_MODEL_SELECTOR: tuple[str, type[QComboBox]] = (
        "llm_model_selector",
        QComboBox,
    )
    LLM_TIMEOUT_BOX: tuple[str, type[QSpinBox]] = "llm_timeout_box", QSpinBox
    LLM_TEMPERATURE_BOX: tuple[str, type[QDoubleSpinBox]] = (
        "llm_temperature_box",
        QDoubleSpinBox,
    )

    SHOW_CONFIRMATIONS_BOX: tuple[str, type[QCheckBox]] = (
        "show_confirmations_box",
        QCheckBox,
    )

    @pytest.fixture
    def translator_settings(
        self, user_data: UserData, qtbot: QtBot
    ) -> TranslatorSettings:
        """
        Returns a new `TranslatorSettings` instance for tests.
        """

        return TranslatorSettings(user_data.translator_config)

    def test_initial(
        self, translator_settings: TranslatorSettings, user_data: UserData
    ) -> None:
        """
        Tests the initial state of the `TranslatorSettings` instance.
        """

        # given
        translator_config: TranslatorConfig = user_data.translator_config

        api_selector: EnumSelector[TranslatorApi] = Utils.get_private_field(
            translator_settings, *TestTranslatorSettings.API_SELECTOR
        )
        api_key_entry: KeyLineEdit = Utils.get_private_field(
            translator_settings, *TestTranslatorSettings.API_KEY_ENTRY
        )
        llm_base_url_entry: QLineEdit = Utils.get_private_field(
            translator_settings, *TestTranslatorSettings.LLM_BASE_URL_ENTRY
        )
        llm_model_selector: QComboBox = Utils.get_private_field(
            translator_settings, *TestTranslatorSettings.LLM_MODEL_SELECTOR
        )
        llm_timeout_box: QSpinBox = Utils.get_private_field(
            translator_settings, *TestTranslatorSettings.LLM_TIMEOUT_BOX
        )
        llm_temperature_box: QDoubleSpinBox = Utils.get_private_field(
            translator_settings, *TestTranslatorSettings.LLM_TEMPERATURE_BOX
        )

        show_confirmations_box: QCheckBox = Utils.get_private_field(
            translator_settings, *TestTranslatorSettings.SHOW_CONFIRMATIONS_BOX
        )

        # then
        assert api_selector.getCurrentValue() == translator_config.translator
        assert api_key_entry.isEnabled() == (
            translator_config.translator == TranslatorApi.DeepL
        )
        assert (api_key_entry.text().strip() or None) == translator_config.api_key
        assert llm_base_url_entry.isEnabled() == (
            translator_config.translator
            in {
                TranslatorApi.Ollama,
                TranslatorApi.LMStudio,
                TranslatorApi.LlamaCpp,
            }
        )
        assert llm_base_url_entry.text() == translator_config.llm_base_url
        assert llm_model_selector.currentText() == translator_config.llm_model
        assert llm_timeout_box.value() == translator_config.llm_timeout
        assert llm_temperature_box.value() == translator_config.llm_temperature

        assert (
            show_confirmations_box.isChecked()
            == translator_config.show_confirmation_dialogs
        )

    def test_apply(
        self, translator_settings: TranslatorSettings, user_data: UserData
    ) -> None:
        """
        Tests the `apply` method of the `AppSettings` instance.
        """

        # given
        translator_config: TranslatorConfig = user_data.translator_config
        old_config: TranslatorConfig = copy(translator_config)

        # when
        translator_settings.apply(translator_config)

        # then
        assert translator_config == old_config
