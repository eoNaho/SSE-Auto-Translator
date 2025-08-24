# gemini.py
"""
This file is part of SSE Auto Translator
by Cutleast and falls under the license
Attribution-NonCommercial-NoDerivatives 4.0 International.
"""

import google.generativeai as genai
import qtpy.QtWidgets as qtw

from main import MainApp
from .translator import Translator

import logging
log = logging.getLogger("GeminiTranslator")

class GeminiTranslator(Translator):
    """
    Class for Google Gemini API (requires API key).
    """

    name = "Gemini"

    cache: dict[str, str] = {}

    def __init__(self, app: MainApp):
        super().__init__(app)

        self.api_key = app.translator_config.get("api_key")
        if not self.api_key:
            log.error("Gemini API key is not configured.")
            return

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-pro')
        except Exception as e:
            log.error(f"Failed to configure Gemini model: {e}")
            self.model = None

    def translate(self, text: str, src: str, dst: str) -> str:
        """
        Translates `text` from `src` language to `dst` language using Gemini.
        The prompt is specifically engineered to return only the translated string.
        """
        if not self.model:
            return f"Error: Gemini model not initialized."

        if text in self.cache:
            return self.cache[text]

        prompt = (
            f"Translate the following text from {src} to {dst}. "
            "IMPORTANT: Your response must contain ONLY the translated text, "
            "with no additional explanations, comments, or formatting. "
            f"The text to translate is: \"{text}\""
        )

        try:
            generation_config = genai.types.GenerationConfig(
                temperature=0.2,
            )
            response = self.model.generate_content(prompt, generation_config=generation_config)
            
            translated_text = response.text.strip()
            self.cache[text] = translated_text
            return translated_text

        except Exception as e:
            log.error(f"An error occurred during Gemini translation: {e}")
            return text

    def mass_translate(self, texts: list[str], src: str, dst: str) -> dict[str, str]:
        """
        Translates `texts` and returns translated result with original texts as keys.
        """
        result: dict[str, str] = {}
        unique_texts = list(set(texts))

        for text in unique_texts:
            result[text] = self.translate(text, src, dst)

        return result

    def get_settings_widget(self) -> qtw.QWidget:
        """
        Returns settings widget. A API Key é gerenciada na tela principal de configurações.
        """
        return qtw.QLabel(self.app.loc.settings.no_config_required)