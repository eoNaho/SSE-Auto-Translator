import time
import random
import logging
import os
from contextlib import contextmanager
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import google.generativeai as genai
from google.api_core import retry, exceptions
import qtpy.QtWidgets as qtw
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from main import MainApp
from .translator import Translator

log = logging.getLogger("GeminiTranslator")

class GeminiTranslator(Translator):
    name = "Gemini"

    cache: dict[str, str] = {}
    last_request_time: float = 0
    current_key_index = 0

    def __init__(self, app: MainApp):
        super().__init__(app)

        self.api_keys = app.translator_config.get("api_keys", [])
        if not self.api_keys:
            single_key = app.translator_config.get("api_key")
            if single_key:
                self.api_keys = [single_key]
            else:
                log.error("Gemini API key is not configured.")
                raise ValueError("Gemini API key is required")

        proxy_config = app.translator_config.get("proxy", {})
        self.rate_limit_delay = app.translator_config.get("rate_limit_delay", 1.0)
        self.max_retries = app.translator_config.get("max_retries", 3)
        self.retry_delay = app.translator_config.get("retry_delay", 2.0)
        
        self.proxy_url = proxy_config.get("url")
        self.proxy_username = proxy_config.get("username")
        self.proxy_password = proxy_config.get("password")

        try:
            genai.configure(api_key=self.api_keys[self.current_key_index])
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            log.info("Gemini translator initialized successfully")
            
        except Exception as e:
            log.error(f"Failed to configure Gemini model: {e}")
            raise

    def _rotate_api_key(self):
        if len(self.api_keys) <= 1:
            log.warning("Limite de cota atingido, mas não há chaves de API alternativas para rotacionar.")
            raise exceptions.ResourceExhausted("No alternative API keys available")
            
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        new_key = self.api_keys[self.current_key_index]
        genai.configure(api_key=new_key)
        
        log.info(f"Chave de API do Gemini rotacionada para o índice {self.current_key_index} ({len(self.api_keys)} chaves no total).")

    def _create_proxied_session(self):
        if not self.proxy_url:
            return requests.Session()
        
        session = requests.Session()
        proxies = {}
        
        parsed = urlparse(self.proxy_url)
        
        if self.proxy_username and self.proxy_password:
            auth = f"{self.proxy_username}:{self.proxy_password}"
            proxy_with_auth = f"{parsed.scheme}://{auth}@{parsed.netloc}{parsed.path}"
            proxies = {
                'http': proxy_with_auth,
                'https': proxy_with_auth
            }
        else:
            proxies = {
                'http': self.proxy_url,
                'https': self.proxy_url
            }
        
        session.proxies.update(proxies)
        return session

    @contextmanager
    def _proxy_context(self):
        if not self.proxy_url:
            yield
            return

        original_env = dict(os.environ)
        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
        
        try:
            parsed_url = urlparse(self.proxy_url)
            
            if self.proxy_username and self.proxy_password:
                auth = f"{self.proxy_username}:{self.proxy_password}"
                proxy_with_auth = f"{parsed_url.scheme}://{auth}@{parsed_url.netloc}{parsed_url.path}"
                for var in proxy_vars:
                    os.environ[var] = proxy_with_auth
            else:
                for var in proxy_vars:
                    os.environ[var] = self.proxy_url
            
            log.info(f"Temporarily using proxy: {parsed_url.scheme}://{parsed_url.netloc}")
            yield
            
        except Exception as e:
            log.error(f"Error configuring proxy: {e}")
            yield
        finally:
            for var in proxy_vars:
                if var in original_env:
                    os.environ[var] = original_env[var]
                elif var in os.environ:
                    del os.environ[var]
            log.info("Proxy environment restored.")

    def _enforce_rate_limit(self):
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        remaining_delay = self.rate_limit_delay - elapsed
        
        if remaining_delay > 0:
            time.sleep(remaining_delay + random.uniform(0, 0.2))
        
        self.last_request_time = time.time()

    @retry.Retry(
        predicate=retry.if_exception_type(
            exceptions.ResourceExhausted,
            exceptions.ServiceUnavailable,
            exceptions.DeadlineExceeded
        )
    )
    def translate(self, text: str, src: str, dst: str) -> str:
        if not self.model:
            return f"Error: Gemini model not initialized."

        if text in self.cache:
            return self.cache[text]

        self._enforce_rate_limit()

        prompt = (
            f"Translate exactly this text from {src} to {dst}: \"{text}\"\n"
            "Rules: 1. Return ONLY the translated text 2. No explanations 3. No formatting "
            "4. Preserve any special characters or codes 5. Be accurate and concise"
        )

        try:
            generation_config = genai.types.GenerationConfig(
                temperature=0.1, 
                max_output_tokens=500,
                top_p=0.8
            )
            
            with self._proxy_context():
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    request_options={
                        'timeout': 30,
                    }
                )
            
            if not response.parts:
                finish_reason = response.candidates[0].finish_reason.name if response.candidates else "UNKNOWN"
                log.warning(
                    f"Gemini returned an empty response for '{text[:50]}...'. "
                    f"Finish Reason: {finish_reason}"
                )
                if response.prompt_feedback.safety_ratings:
                    log.warning(f"Safety Ratings: {response.prompt_feedback.safety_ratings}")
                return text

            translated_text = response.text.strip()
            
            if not translated_text or translated_text == prompt:
                log.warning(f"Empty or invalid response from Gemini for: {text}")
                return text
                
            self.cache[text] = translated_text
            return translated_text

        except exceptions.ResourceExhausted as e:
            log.warning(f"Rate limit exceeded (ResourceExhausted): {e}. Tentando rotacionar a chave de API.")
            self._rotate_api_key()
            raise e

        except exceptions.InvalidArgument as e:
            log.error(f"Invalid argument error: {e}")
            return text

        except Exception as e:
            log.error(f"Unexpected error in Gemini translation: {e}")
            return text

    def mass_translate(self, texts: list[str], src: str, dst: str) -> dict[str, str]:
        result: dict[str, str] = {}
        unique_texts = list(set(texts))

        for text in unique_texts:
            result[text] = self.translate(text, src, dst)

        return result

    def get_settings_widget(self) -> qtw.QWidget:
        widget = qtw.QWidget()
        layout = qtw.QVBoxLayout(widget)
        
        info_label = qtw.QLabel(
            "Gemini Translator Settings\n\n"
            "• API Key required for Gemini Pro\n"
            "• Proxy support for bypassing limits\n"
            "• Automatic rate limiting\n"
            "• Retry mechanism for failed requests"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        return widget