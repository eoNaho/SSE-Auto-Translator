"""
Copyright (c) Cutleast
"""

from copy import copy
from typing import override

from cutleast_core_lib.ui.settings.settings_page import SettingsPage
from cutleast_core_lib.ui.widgets.enum_radiobutton_widget import EnumRadiobuttonsWidget
from cutleast_core_lib.ui.widgets.key_edit import KeyLineEdit
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)

from core.config.translator_config import TranslatorConfig
from core.translator.apis import TranslatorApi
from core.translator.local_llm import (
    LMStudioTranslator,
    LlamaCppTranslator,
    LocalLlmTranslator,
    OllamaTranslator,
)


class TranslatorSettings(SettingsPage[TranslatorConfig]):
    """
    Widget for translator API settings.
    """

    __flayout: QFormLayout

    __api_selector: EnumRadiobuttonsWidget[TranslatorApi]
    __api_key_entry: KeyLineEdit
    __api_key_label: QLabel

    __llm_base_url_entry: QLineEdit
    __llm_base_url_label: QLabel
    __llm_model_selector: QComboBox
    __llm_model_label: QLabel
    __refresh_llm_models_button: QPushButton
    __llm_timeout_box: QSpinBox
    __llm_timeout_label: QLabel
    __llm_temperature_box: QDoubleSpinBox
    __llm_temperature_label: QLabel

    __show_confirmations_box: QCheckBox

    @override
    def _init_ui(self) -> None:
        scroll_widget = QWidget()
        scroll_widget.setObjectName("transparent")
        self.setWidget(scroll_widget)

        self.__flayout = QFormLayout()
        scroll_widget.setLayout(self.__flayout)

        self.__init_api_settings()
        self.__init_confirmation_box()

    def __init_api_settings(self) -> None:
        self.__api_selector = EnumRadiobuttonsWidget(
            TranslatorApi,
            self._initial_config.translator,
            orientation=Qt.Orientation.Horizontal,
        )
        self.__api_selector.currentValueChanged.connect(
            lambda _: self.changed_signal.emit()
        )
        self.__api_selector.currentValueChanged.connect(self.__update_api_settings)
        self.__flayout.addRow(self.tr("Translator API"), self.__api_selector)

        self.__api_key_label = QLabel(self.tr("Translator API key"))
        self.__api_key_entry = KeyLineEdit()
        if self._initial_config.api_key:
            self.__api_key_entry.setText(self._initial_config.api_key)
        self.__api_key_entry.textChanged.connect(lambda _: self.changed_signal.emit())
        self.__flayout.addRow(self.__api_key_label, self.__api_key_entry)

        self.__llm_base_url_label = QLabel(self.tr("Local LLM base URL"))
        self.__llm_base_url_entry = QLineEdit()
        self.__llm_base_url_entry.setPlaceholderText(
            self.tr("Leave empty to use provider default")
        )
        self.__llm_base_url_entry.setText(self._initial_config.llm_base_url)
        self.__llm_base_url_entry.textChanged.connect(
            lambda _: self.changed_signal.emit()
        )
        self.__flayout.addRow(self.__llm_base_url_label, self.__llm_base_url_entry)

        self.__llm_model_label = QLabel(self.tr("Local LLM model"))
        model_widget = QWidget()
        model_widget.setObjectName("transparent")
        model_layout = QHBoxLayout()
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_widget.setLayout(model_layout)

        self.__llm_model_selector = QComboBox()
        self.__llm_model_selector.setPlaceholderText(
            self.tr("Refresh to load running models")
        )
        self.__set_llm_models([], self._initial_config.llm_model)
        self.__llm_model_selector.currentTextChanged.connect(
            lambda _: self.changed_signal.emit()
        )
        model_layout.addWidget(self.__llm_model_selector, stretch=1)

        self.__refresh_llm_models_button = QPushButton(self.tr("Refresh"))
        self.__refresh_llm_models_button.clicked.connect(self.__refresh_llm_models)
        model_layout.addWidget(self.__refresh_llm_models_button)
        self.__flayout.addRow(self.__llm_model_label, model_widget)

        self.__llm_timeout_label = QLabel(self.tr("Local LLM timeout"))
        self.__llm_timeout_box = QSpinBox()
        self.__llm_timeout_box.setRange(5, 3600)
        self.__llm_timeout_box.setSuffix(" s")
        self.__llm_timeout_box.setValue(self._initial_config.llm_timeout)
        self.__llm_timeout_box.valueChanged.connect(
            lambda _: self.changed_signal.emit()
        )
        self.__flayout.addRow(self.__llm_timeout_label, self.__llm_timeout_box)

        self.__llm_temperature_label = QLabel(self.tr("Local LLM temperature"))
        self.__llm_temperature_box = QDoubleSpinBox()
        self.__llm_temperature_box.setRange(0.0, 2.0)
        self.__llm_temperature_box.setSingleStep(0.1)
        self.__llm_temperature_box.setDecimals(2)
        self.__llm_temperature_box.setValue(self._initial_config.llm_temperature)
        self.__llm_temperature_box.valueChanged.connect(
            lambda _: self.changed_signal.emit()
        )
        self.__flayout.addRow(
            self.__llm_temperature_label, self.__llm_temperature_box
        )

        self.__update_api_settings(self._initial_config.translator)

    def __update_api_settings(self, translator_api: TranslatorApi) -> None:
        uses_api_key: bool = translator_api == TranslatorApi.DeepL
        uses_local_llm: bool = translator_api in {
            TranslatorApi.Ollama,
            TranslatorApi.LMStudio,
            TranslatorApi.LlamaCpp,
        }

        self.__api_key_label.setEnabled(uses_api_key)
        self.__api_key_entry.setEnabled(uses_api_key)

        for widget in [
            self.__llm_base_url_label,
            self.__llm_base_url_entry,
            self.__llm_model_label,
            self.__llm_model_selector,
            self.__refresh_llm_models_button,
            self.__llm_timeout_label,
            self.__llm_timeout_box,
            self.__llm_temperature_label,
            self.__llm_temperature_box,
        ]:
            widget.setEnabled(uses_local_llm)

    def __set_llm_models(self, models: list[str], selected_model: str) -> None:
        self.__llm_model_selector.blockSignals(True)
        self.__llm_model_selector.clear()

        if selected_model:
            self.__llm_model_selector.addItem(selected_model)

        for model in models:
            if self.__llm_model_selector.findText(model) == -1:
                self.__llm_model_selector.addItem(model)

        if selected_model:
            self.__llm_model_selector.setCurrentText(selected_model)

        self.__llm_model_selector.blockSignals(False)

    def __refresh_llm_models(self) -> None:
        translator_api = self.__api_selector.getCurrentValue()
        translator_classes: dict[TranslatorApi, type[LocalLlmTranslator]] = {
            TranslatorApi.Ollama: OllamaTranslator,
            TranslatorApi.LMStudio: LMStudioTranslator,
            TranslatorApi.LlamaCpp: LlamaCppTranslator,
        }
        translator_cls = translator_classes.get(translator_api)
        if translator_cls is None:
            return

        config = copy(self._initial_config)
        config.translator = translator_api
        config.llm_base_url = self.__llm_base_url_entry.text().strip()
        config.llm_model = self.__llm_model_selector.currentText().strip()
        config.llm_timeout = self.__llm_timeout_box.value()
        config.llm_temperature = self.__llm_temperature_box.value()

        try:
            models = translator_cls(config).get_available_models()
        except Exception as error:
            QMessageBox.warning(
                self,
                self.tr("Could not load models"),
                self.tr("Could not load running local LLM models:\n{error}").format(
                    error=error
                ),
            )
            return

        old_model = self.__llm_model_selector.currentText()
        self.__set_llm_models(models, config.llm_model)
        if self.__llm_model_selector.currentText() != old_model:
            self.changed_signal.emit()

        if not models:
            QMessageBox.information(
                self,
                self.tr("No running models"),
                self.tr("No running local LLM models were found."),
            )

    def __init_confirmation_box(self) -> None:
        self.__show_confirmations_box = QCheckBox(
            self.tr("Ask for confirmation before starting a batch machine translation")
        )
        self.__show_confirmations_box.setChecked(
            self._initial_config.show_confirmation_dialogs
        )
        self.__show_confirmations_box.stateChanged.connect(
            lambda _: self.changed_signal.emit()
        )
        self.__flayout.addRow(self.__show_confirmations_box)

    @override
    def apply(self, config: TranslatorConfig) -> None:
        config.translator = self.__api_selector.getCurrentValue()
        config.api_key = self.__api_key_entry.text().strip() or None
        config.llm_base_url = self.__llm_base_url_entry.text().strip()
        config.llm_model = self.__llm_model_selector.currentText().strip()
        config.llm_timeout = self.__llm_timeout_box.value()
        config.llm_temperature = self.__llm_temperature_box.value()
        config.show_confirmation_dialogs = self.__show_confirmations_box.isChecked()
