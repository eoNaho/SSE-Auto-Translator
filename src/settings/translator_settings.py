"""
This file is part of SSE Auto Translator
by Cutleast and falls under the license
Attribution-NonCommercial-NoDerivatives 4.0 International.
"""

import jstyleson as json
import qtpy.QtCore as qtc
import qtpy.QtWidgets as qtw
from urllib.parse import urlparse

from main import MainApp
from translator_api import AVAILABLE_APIS
from widgets import KeyEntry


class TranslatorSettings(qtw.QWidget):
    """
    Widget for translator API settings.
    """

    on_change_signal = qtc.Signal()
    """
    This signal gets emitted every time
    the user changes some setting.
    """

    def __init__(self, app: MainApp):
        super().__init__()

        self.app = app
        self.loc = app.loc
        self.mloc = app.loc.settings

        self.setObjectName("root")

        flayout = qtw.QFormLayout()
        self.setLayout(flayout)

        # Translator
        self.translator_box = qtw.QComboBox()
        self.translator_box.setEditable(False)
        self.translator_box.addItems([translator.name for translator in AVAILABLE_APIS])
        self.translator_box.setCurrentText(self.app.translator_config["translator"])
        self.translator_box.currentTextChanged.connect(self.on_change)
        flayout.addRow(self.mloc.translator, self.translator_box)

        # API Key
        # Store the label as an instance variable for reliable access
        self.api_key_label = qtw.QLabel(self.mloc.translator_api_key)
        self.api_key_entry = KeyEntry()
        self.api_key_entry.setDisabled(True)
        self.api_key_entry.textChanged.connect(self.on_change)
        if self.app.translator_config["api_key"]:
            self.api_key_entry.setText(self.app.translator_config["api_key"])
            self.api_key_entry.setDisabled(False)
        flayout.addRow(self.api_key_label, self.api_key_entry)

        # Proxy Settings Group (only visible for Gemini)
        self.proxy_groupbox = qtw.QGroupBox(self.mloc.proxy_settings)
        self.proxy_groupbox.setVisible(False)
        flayout.addRow(self.proxy_groupbox)
        proxy_flayout = qtw.QFormLayout()
        self.proxy_groupbox.setLayout(proxy_flayout)

        # Proxy URL
        proxy_url_label = qtw.QLabel(self.mloc.proxy_url)
        self.proxy_url_entry = qtw.QLineEdit()
        self.proxy_url_entry.setPlaceholderText("http://username:password@proxy:port ou socks5://proxy:port")
        proxy_config = self.app.translator_config.get("proxy", {})
        if proxy_config.get("url"):
            self.proxy_url_entry.setText(proxy_config["url"])
        self.proxy_url_entry.textChanged.connect(self.on_change)
        self.proxy_url_entry.setToolTip(self.mloc.proxy_help_text)
        proxy_flayout.addRow(proxy_url_label, self.proxy_url_entry)

        # Proxy Authentication
        proxy_auth_label = qtw.QLabel(self.mloc.proxy_auth)
        proxy_auth_hlayout = qtw.QHBoxLayout()
        
        self.proxy_username_entry = qtw.QLineEdit()
        self.proxy_username_entry.setPlaceholderText(self.mloc.username)
        if proxy_config.get("username"):
            self.proxy_username_entry.setText(proxy_config["username"])
        self.proxy_username_entry.textChanged.connect(self.on_change)
        proxy_auth_hlayout.addWidget(self.proxy_username_entry)
        
        self.proxy_password_entry = qtw.QLineEdit()
        self.proxy_password_entry.setPlaceholderText(self.mloc.password)
        self.proxy_password_entry.setEchoMode(qtw.QLineEdit.EchoMode.Password)
        if proxy_config.get("password"):
            self.proxy_password_entry.setText(proxy_config["password"])
        self.proxy_password_entry.textChanged.connect(self.on_change)
        proxy_auth_hlayout.addWidget(self.proxy_password_entry)
        
        proxy_flayout.addRow(proxy_auth_label, proxy_auth_hlayout)

        # Rate Limiting Settings
        rate_limit_label = qtw.QLabel(self.mloc.rate_limit_delay)
        self.rate_limit_spinbox = qtw.QDoubleSpinBox()
        self.rate_limit_spinbox.setRange(0.1, 10.0)
        self.rate_limit_spinbox.setSingleStep(0.1)
        self.rate_limit_spinbox.setValue(self.app.translator_config.get("rate_limit_delay", 1.0))
        self.rate_limit_spinbox.valueChanged.connect(self.on_change)
        proxy_flayout.addRow(rate_limit_label, self.rate_limit_spinbox)

        # Max Retries
        retries_label = qtw.QLabel(self.mloc.max_retries)
        self.retries_spinbox = qtw.QSpinBox()
        self.retries_spinbox.setRange(1, 10)
        self.retries_spinbox.setValue(self.app.translator_config.get("max_retries", 3))
        self.retries_spinbox.valueChanged.connect(self.on_change)
        proxy_flayout.addRow(retries_label, self.retries_spinbox)

        # Retry Delay
        retry_delay_label = qtw.QLabel(self.mloc.retry_delay)
        self.retry_delay_spinbox = qtw.QDoubleSpinBox()
        self.retry_delay_spinbox.setRange(0.5, 30.0)
        self.retry_delay_spinbox.setSingleStep(0.5)
        self.retry_delay_spinbox.setValue(self.app.translator_config.get("retry_delay", 2.0))
        self.retry_delay_spinbox.valueChanged.connect(self.on_change)
        proxy_flayout.addRow(retry_delay_label, self.retry_delay_spinbox)

        # Test Proxy Button
        self.test_proxy_button = qtw.QPushButton(self.mloc.test_proxy)
        self.test_proxy_button.clicked.connect(self.test_proxy_connection)
        proxy_flayout.addRow(self.test_proxy_button)

        # Info label
        info_label = qtw.QLabel(self.mloc.proxy_config_info)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-style: italic;")
        proxy_flayout.addRow(info_label)

        # Connect translator change to show/hide proxy settings
        self.translator_box.currentTextChanged.connect(
            lambda text: self._update_proxy_visibility(text)
        )
        self._update_proxy_visibility(self.translator_box.currentText())

        # Reset Confirmation Dialogs
        reset_confirmations_button = qtw.QPushButton(self.loc.main.reset_confirmations)
        reset_confirmations_button.setDisabled(
            self.app.translator_config.get("show_confirmation_dialogs", True)
        )

        def reset_confirmations():
            self.app.translator_config["show_confirmation_dialogs"] = True

            with open(self.app.translator_conf_path, "w", encoding="utf8") as file:
                json.dump(self.app.translator_config, file, indent=4)

            reset_confirmations_button.setDisabled(True)

        reset_confirmations_button.clicked.connect(reset_confirmations)
        flayout.addRow(reset_confirmations_button)

    def _update_proxy_visibility(self, translator_name: str):
        """Show proxy settings only for Gemini"""
        is_gemini = translator_name == "Gemini"
        self.proxy_groupbox.setVisible(is_gemini)
        
        # Enable/disable API key based on translator
        is_api_required = translator_name in ["DeepL", "Gemini"]
        self.api_key_entry.setEnabled(is_api_required)
        
        self.api_key_label.setEnabled(is_api_required)

    def test_proxy_connection(self):
        """Test the proxy connection"""
        import urllib.request
        from urllib.error import URLError
        
        proxy_url = self.proxy_url_entry.text().strip()
        if not proxy_url:
            qtw.QMessageBox.warning(self, self.mloc.test_proxy, self.mloc.proxy_url_required)
            return
            
        try:
            parsed = urlparse(proxy_url)
            test_url = "http://httpbin.org/ip"
            
            # Configurar o proxy baseado no tipo
            if parsed.scheme in ['socks4', 'socks5']:
                try:
                    import socks
                    import socket
                    
                    # Configurar socket para SOCKS
                    sock_type = socks.SOCKS5 if parsed.scheme == 'socks5' else socks.SOCKS4
                    socks.set_default_proxy(
                        sock_type,
                        parsed.hostname,
                        parsed.port,
                        username=parsed.username,
                        password=parsed.password
                    )
                    socket.socket = socks.socksocket
                    
                    # Testar conexão
                    response = urllib.request.urlopen(test_url, timeout=10)
                except ImportError:
                    qtw.QMessageBox.critical(
                        self, 
                        self.mloc.test_proxy, 
                        "Biblioteca PySocks não instalada. Instale com: pip install pysocks"
                    )
                    return
            else:
                # Para HTTP/HTTPS
                proxy_handler = urllib.request.ProxyHandler({
                    'http': proxy_url,
                    'https': proxy_url
                })
                opener = urllib.request.build_opener(proxy_handler)
                response = opener.open(test_url, timeout=10)
            
            result = response.read().decode()
            qtw.QMessageBox.information(self, self.mloc.test_proxy, 
                                      f"{self.mloc.proxy_test_success}\n\n{result}")
            
        except Exception as e:
            qtw.QMessageBox.critical(self, self.mloc.test_proxy, 
                                   f"{self.mloc.proxy_test_failed}\n\n{str(e)}")
        finally:
            # Restaurar socket original para proxies SOCKS
            if parsed.scheme in ['socks4', 'socks5']:
                try:
                    import socket
                    socket.socket = socket._orig_socket
                except:
                    pass

    def on_change(self, *args):
        """
        This emits change signal without passing parameters.
        """
        self.on_change_signal.emit()

    def get_settings(self):
        api_key = self.api_key_entry.text() if self.api_key_entry.text() else None
        
        proxy_config = {}
        if self.proxy_url_entry.text().strip():
            proxy_config["url"] = self.proxy_url_entry.text().strip()
            if self.proxy_username_entry.text().strip():
                proxy_config["username"] = self.proxy_username_entry.text().strip()
            if self.proxy_password_entry.text().strip():
                proxy_config["password"] = self.proxy_password_entry.text().strip()

        return {
            "translator": self.translator_box.currentText(),
            "api_key": api_key,
            "proxy": proxy_config,
            "rate_limit_delay": self.rate_limit_spinbox.value(),
            "max_retries": self.retries_spinbox.value(),
            "retry_delay": self.retry_delay_spinbox.value(),
            "show_confirmation_dialogs": self.app.translator_config.get(
                "show_confirmation_dialogs", True
            ),
        }