"""
This file is part of SSE Auto Translator
by Cutleast and falls under the license
Attribution-NonCommercial-NoDerivatives 4.0 International.
"""

import deepl
import googletrans

from main import MainApp

from .translator import Translator


class DeepLTranslator(Translator):
    """
    Class for DeepL API (supports multiple API keys with automatic rotation).
    """

    name = "DeepL"

    cache: dict[str, str] = {}
    current_key_index = 0

    langs = {
        "portuguese": "PT-BR",
        "chinese": "ZH",
    }

    def __init__(self, app: MainApp):
        super().__init__(app)

        self.api_keys = app.translator_config.get("api_keys", [])
        if not self.api_keys:
            # Backward compatibility: check for single api_key
            single_key = app.translator_config.get("api_key")
            if single_key:
                self.api_keys = [single_key]
            else:
                raise ValueError("Nenhuma chave API configurada para DeepL")

        # Inicializar com a primeira chave
        self.current_key_index = 0
        self.translator = deepl.Translator(self.api_keys[self.current_key_index])

        # Todo: Load glossary from user config
        self.glossary_id: str = None

        if self.glossary_id is not None:
            self.glossary = self.translator.get_glossary(self.glossary_id)
        else:
            self.glossary = None

    def rotate_api_key(self):
        """Rotate to the next available API key"""
        if len(self.api_keys) <= 1:
            raise deepl.QuotaExceededException("No alternative API keys available")
            
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.translator = deepl.Translator(self.api_keys[self.current_key_index])
        print(f"Rotated to DeepL API key {self.current_key_index + 1}/{len(self.api_keys)}")

    def mass_translate(self, texts: list[str], src: str, dst: str) -> dict[str, str]:
        result: dict[str, str] = {}

        texts = list(set(texts))  # Remove duplicates

        for text in texts:
            result[text] = self.translate(text, src, dst)

        return result

    def translate(self, text: str, src: str, dst: str) -> str:
        if text not in self.cache:
            # Get language codes from DeepLTranslator.langs
            # and googletrans.LANGCODES as fallback
            src_code = self.langs.get(
                src.lower(), googletrans.LANGCODES.get(src.lower(), src)
            )
            dst_code = self.langs.get(
                dst.lower(), googletrans.LANGCODES.get(dst.lower(), dst)
            )

            try:
                if self.glossary is not None:
                    result: deepl.TextResult = self.translator.translate_text_with_glossary(
                        text, self.glossary, dst_code
                    )
                else:
                    result: deepl.TextResult = self.translator.translate_text(
                        text, source_lang=src_code, target_lang=dst_code
                    )

                self.cache[text] = result.text

            except deepl.QuotaExceededException:
                # Rotate API key and retry
                self.rotate_api_key()
                return self.translate(text, src, dst)

            except deepl.DeepLException as e:
                # Outros erros do DeepL
                raise Exception(f"Erro do DeepL: {str(e)}")

        return self.cache[text]