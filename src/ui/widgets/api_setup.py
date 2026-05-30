"""
This file is part of SSE Auto Translator
by Cutleast and falls under the license
Attribution-NonCommercial-NoDerivatives 4.0 International.
"""

import logging
from typing import Optional, override

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QClipboard, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.translation_provider.nm_api.nm_api import NexusModsApi

from .paste_entry import PasteLineEdit


class _SsoThread(QThread):
    """
    Background thread that runs the Nexus Mods SSO flow without blocking the UI.
    """

    url_ready = Signal(str)
    """Emitted with the SSO login URL once it is available."""

    sso_completed = Signal(str)
    """Emitted with the API key on successful login."""

    sso_failed = Signal(str)
    """Emitted with an error message if the SSO flow fails."""

    def __init__(self) -> None:
        super().__init__()
        self.log = logging.getLogger(self.__class__.__name__)

    @override
    def run(self) -> None:
        try:
            api = NexusModsApi()
            key = api.get_sso_key(url_callback=self.url_ready.emit)
            self.sso_completed.emit(key)
        except Exception as ex:
            self.log.error(f"SSO flow failed: {ex}", exc_info=ex)
            self.sso_failed.emit(str(ex))


class _SsoWaitDialog(QDialog):
    """
    Dialog shown while the SSO login is in progress.
    Displays the login URL so the user can copy and paste it into any browser.
    """

    __url_field: QLineEdit
    __status_label: QLabel
    __copy_button: QPushButton
    __cancel_button: QPushButton

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(self.tr("Nexus Mods Login"))
        self.setMinimumWidth(560)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)
        self.setLayout(vlayout)

        info_label = QLabel(
            self.tr(
                "Open the link below in your browser and log in to Nexus Mods.\n"
                "This dialog will close automatically once you are logged in."
            )
        )
        info_label.setWordWrap(True)
        vlayout.addWidget(info_label)

        url_hlayout = QHBoxLayout()
        vlayout.addLayout(url_hlayout)

        self.__url_field = QLineEdit()
        self.__url_field.setReadOnly(True)
        self.__url_field.setPlaceholderText(self.tr("Generating login URL..."))
        url_hlayout.addWidget(self.__url_field)

        self.__copy_button = QPushButton(self.tr("Copy"))
        self.__copy_button.setDisabled(True)
        self.__copy_button.clicked.connect(self.__copy_url)
        url_hlayout.addWidget(self.__copy_button)

        self.__status_label = QLabel(self.tr("Waiting for login URL..."))
        self.__status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vlayout.addWidget(self.__status_label)

        self.__cancel_button = QPushButton(self.tr("Cancel"))
        self.__cancel_button.clicked.connect(self.reject)
        vlayout.addWidget(self.__cancel_button, alignment=Qt.AlignmentFlag.AlignRight)

    def set_url(self, url: str) -> None:
        self.__url_field.setText(url)
        self.__copy_button.setEnabled(True)
        self.__status_label.setText(self.tr("Waiting for you to log in via the browser..."))

    def set_success(self) -> None:
        self.__status_label.setText(self.tr("Login successful!"))
        self.__cancel_button.setEnabled(False)

    def set_error(self, message: str) -> None:
        self.__status_label.setText(self.tr("Login failed: ") + message)
        self.__cancel_button.setText(self.tr("Close"))

    def __copy_url(self) -> None:
        clipboard: QClipboard = QGuiApplication.clipboard()
        clipboard.setText(self.__url_field.text())
        self.__copy_button.setText(self.tr("Copied!"))


class ApiSetup(QWidget):
    """
    Widget for API Setup.
    """

    valid_signal = Signal(bool)
    is_valid: bool = False
    api_key: Optional[str] = None

    __sso_thread: Optional[_SsoThread] = None

    def __init__(self) -> None:
        super().__init__()

        vlayout = QVBoxLayout()
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(vlayout)
        self.setMinimumWidth(600)

        api_help_label = QLabel(
            self.tr(
                "In order to get translations from Nexus Mods this tool needs access "
                "to the Nexus Mods API. You can setup access by two methods: "
                "insert API key manually or via SSO (Single-Sign-On)."
            )
        )
        api_help_label.setWordWrap(True)
        vlayout.addWidget(api_help_label)

        vlayout.addSpacing(10)

        tab_widget = QTabWidget()
        tab_widget.tabBar().setExpanding(True)
        tab_widget.setObjectName("centered_tab")
        vlayout.addWidget(tab_widget, stretch=1)

        sso_box = QWidget()
        sso_box.setContentsMargins(0, 0, 0, 0)
        sso_box.setObjectName("transparent")
        sso_vlayout = QVBoxLayout()
        sso_vlayout.setContentsMargins(0, 0, 0, 0)
        sso_box.setLayout(sso_vlayout)
        sso_button = QPushButton(
            self.tr("Click here to login to Nexus Mods via browser")
        )
        sso_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        def start_sso() -> None:
            sso_button.setDisabled(True)
            sso_button.setText(self.tr("Waiting for login..."))

            dialog = _SsoWaitDialog(self)

            thread = _SsoThread()
            self.__sso_thread = thread

            thread.url_ready.connect(dialog.set_url)

            def on_completed(key: str) -> None:
                self.api_key = key
                self.is_valid = True
                dialog.set_success()
                dialog.accept()
                sso_button.setText(self.tr("Successfully logged into Nexus Mods"))
                self.setDisabled(True)
                self.valid_signal.emit(True)

            def on_failed(message: str) -> None:
                dialog.set_error(message)
                sso_button.setEnabled(True)
                sso_button.setText(
                    self.tr("Click here to login to Nexus Mods via browser")
                )

            def on_dialog_rejected() -> None:
                thread.terminate()
                thread.wait()
                sso_button.setEnabled(True)
                sso_button.setText(
                    self.tr("Click here to login to Nexus Mods via browser")
                )

            thread.sso_completed.connect(on_completed)
            thread.sso_failed.connect(on_failed)
            thread.finished.connect(lambda: None)  # keep reference alive
            dialog.rejected.connect(on_dialog_rejected)

            thread.start()
            dialog.exec()

        sso_button.clicked.connect(start_sso)
        sso_vlayout.addWidget(sso_button)
        tab_widget.addTab(sso_box, self.tr("Single-Sign-On (browser)"))

        api_key_box = QWidget()
        api_key_box.setContentsMargins(0, 0, 0, 0)
        api_key_box.setObjectName("transparent")
        api_key_vlayout = QVBoxLayout()
        api_key_vlayout.setContentsMargins(0, 0, 0, 0)
        api_key_box.setLayout(api_key_vlayout)
        api_key_hlayout = QHBoxLayout()
        api_key_vlayout.addLayout(api_key_hlayout)
        api_key_label = QLabel(self.tr("Insert your API key"))
        api_key_hlayout.addWidget(api_key_label)
        self.api_key_entry = PasteLineEdit()
        api_key_hlayout.addWidget(self.api_key_entry)
        api_key_check_button = QPushButton(self.tr("Check API key"))

        def check_api_key() -> None:
            key = self.api_key_entry.text().strip()

            if not key:
                return

            api_key_check_button.setText("Checking API key...")
            if NexusModsApi().is_api_key_valid(key):
                self.api_key = key
                self.is_valid = True
                self.valid_signal.emit(True)
                api_key_check_button.setText(self.tr("API key is valid!"))
                self.setDisabled(True)
            else:
                self.is_valid = False
                self.valid_signal.emit(False)
                api_key_check_button.setText(self.tr("API key is invalid!"))

        api_key_check_button.clicked.connect(check_api_key)
        api_key_vlayout.addWidget(api_key_check_button)
        tab_widget.addTab(api_key_box, self.tr("Manual Setup"))
