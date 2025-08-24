import time
import random
import logging
from typing import Dict, List
from urllib.parse import quote, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth

import qtpy.QtWidgets as qtw

from main import MainApp
from .translator import Translator

log = logging.getLogger("DeepLScraperTranslator")

class DeepLScraperTranslator(Translator):

    name = "DeepL Scraping"

    cache: Dict[str, str] = {}
    last_request_time: float = 0
    driver = None

    def __init__(self, app: MainApp):
        super().__init__(app)

        proxy_config = app.translator_config.get("proxy", {})
        self.rate_limit_delay = app.translator_config.get("rate_limit_delay", 3.0)
        self.max_retries = app.translator_config.get("max_retries", 2)
        
        self.proxy_url = proxy_config.get("url")
        self.proxy_username = proxy_config.get("username")
        self.proxy_password = proxy_config.get("password")

        self._init_stealth_driver()

    def _init_stealth_driver(self):
        try:
            log.info("Iniciando driver stealth...")
            chrome_options = Options()
            
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.page_load_strategy = 'eager'

            if self.proxy_url:
                proxy_string = self.proxy_url
                if self.proxy_username and self.proxy_password:
                    parsed = urlparse(self.proxy_url)
                    auth = f"{self.proxy_username}:{self.proxy_password}"
                    proxy_string = f"{parsed.scheme}://{auth}@{parsed.netloc}"
                
                chrome_options.add_argument(f'--proxy-server={proxy_string}')

            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            stealth(
                self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )

            log.info("Driver stealth configurado com sucesso!")

        except Exception as e:
            log.error(f"Erro ao iniciar driver stealth: {e}")
            self.driver = None

    def _enforce_rate_limit(self):
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        
        self.last_request_time = time.time()

    def _get_deepl_language_code(self, language: str) -> str:
        language_map = {
            'en': 'en', 'english': 'en', 'inglês': 'en',
            'pt': 'pt', 'portuguese': 'pt', 'português': 'pt',
            'es': 'es', 'spanish': 'es', 'espanhol': 'es',
            'fr': 'fr', 'french': 'fr', 'francês': 'fr',
            'de': 'de', 'german': 'de', 'alemão': 'de',
        }
        return language_map.get(language.lower(), 'en')

    def _wait_for_translation(self, timeout: int = 15) -> str:
        try:
            wait = WebDriverWait(self.driver, timeout)
            
            target_element = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="translator-target-input"]'))
            )
            
            start_time = time.time()
            last_value = ""
            
            while time.time() - start_time < timeout:
                current_value = target_element.get_attribute('value') or target_element.text
                current_value = current_value.strip()
                
                if current_value and current_value != last_value:
                    time.sleep(0.5)
                    final_value = target_element.get_attribute('value') or target_element.text
                    if final_value.strip():
                        return final_value.strip()
                
                last_value = current_value
                time.sleep(0.3)
                
            return ""
            
        except TimeoutException:
            return ""

    def translate(self, text: str, src: str, dst: str) -> str:
        if not self.driver:
            log.error("Driver não disponível")
            return text

        if not text or len(text.strip()) == 0:
            return text

        cache_key = f"{src}_{dst}_{text}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        self._enforce_rate_limit()

        src_code = self._get_deepl_language_code(src)
        dst_code = self._get_deepl_language_code(dst)
        
        encoded_text = quote(text)
        url = f"https://www.deepl.com/translator#{src_code}/{dst_code}/{encoded_text}"

        for attempt in range(self.max_retries):
            try:
                self.driver.get(url)
                
                translation = self._wait_for_translation(15)
                
                if translation and translation != text:
                    self.cache[cache_key] = translation
                    return translation
                else:
                    log.warning(f"Tradução não carregada na tentativa {attempt + 1}")
                    time.sleep(2)

            except Exception as e:
                log.error(f"Erro na tentativa {attempt + 1}: {e}")
                time.sleep(3)

        return text

    def mass_translate(self, texts: List[str], src: str, dst: str) -> Dict[str, str]:
        result: Dict[str, str] = {}
        unique_texts = list(set(texts))

        for i, text in enumerate(unique_texts):
            result[text] = self.translate(text, src, dst)
            
            if i > 0 and i % 3 == 0:
                time.sleep(random.uniform(1, 2))

        return result

    def get_settings_widget(self) -> qtw.QWidget:
        widget = qtw.QWidget()
        layout = qtw.QVBoxLayout(widget)
        
        info_label = qtw.QLabel(
            "DeepL Stealth Scraper\n\n"
            "• Técnicas profissionais anti-detecção\n"
            "• Selenium otimizado com stealth\n"
            "• Bypass completo de proteções\n"
            "• Aguarda carregamento JavaScript\n\n"
            "🛡️  Tecnologias:\n"
            "• Selenium Stealth\n"
            "• User-Agent realista\n"
            "• WebGL spoofing\n"
            "• Detecção zero"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        return widget
        
    def __del__(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass