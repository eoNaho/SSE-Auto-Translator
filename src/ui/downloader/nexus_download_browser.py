"""
Copyright (c) Cutleast
"""

import logging
import webbrowser
from pathlib import Path
from typing import Optional, override

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.translation_provider.nm_api.nxm_handler import NXMHandler
from core.translation_provider.nm_api.nxm_request import NxmRequest


JS_AUTO_CLICK_NEXUS_DOWNLOAD: str = """
(function autoClickNexusDownload() {
    var attempts = 0;
    var maxAttempts = 50;

    function clickFirst(selector) {
        var element = document.querySelector(selector);
        if (element) {
            element.click();
            return true;
        }
        return false;
    }

    function tryClick() {
        if (clickFirst('a[href^="nxm://"]')) {
            return;
        }

        if (clickFirst('a.btn-mod, a[data-download="nxm"]')) {
            return;
        }

        attempts++;
        if (attempts < maxAttempts) {
            setTimeout(tryClick, 200);
        }
    }

    tryClick();
})();
"""


class _NexusWebPage(QWebEnginePage):
    """
    Custom QWebEnginePage that intercepts ``nxm://`` navigation requests so
    the link never reaches the OS and is instead validated and forwarded to
    the existing NXM handler signal.
    """

    nxm_intercepted: Signal = Signal(str)
    """
    Emitted when an ``nxm://`` URL is intercepted.

    Args:
        str: The raw NXM URL string (e.g. ``nxm://skyrimspecialedition/mods/…``).
    """

    log: logging.Logger = logging.getLogger("NexusWebPage")

    @override
    def acceptNavigationRequest(
        self,
        url: QUrl | str,
        nav_type: QWebEnginePage.NavigationType,
        is_main_frame: bool,
    ) -> bool:
        qurl = QUrl(url) if isinstance(url, str) else url

        if qurl.scheme() == "nxm":
            self.log.debug(f"Intercepted nxm:// URL: {qurl.toString()!r}")
            self.nxm_intercepted.emit(qurl.toString())
            return False  # block the navigation

        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class NexusDownloadBrowserDialog(QDialog):
    """
    Embedded-browser dialog for Nexus Mods non-premium (free) downloads.

    Opens the Nexus file page inside a persistent QWebEngineView so the user
    can log in with their Nexus account and click "Mod Manager Download".
    The resulting ``nxm://`` link is intercepted, validated against the
    expected ``game``, ``mod_id`` and ``file_id``, and – if it matches –
    forwarded to :class:`NXMHandler` so the existing download queue continues
    automatically.

    On a mismatch the dialog stays open and shows a warning so the user can
    try again.  Closing the dialog without capturing the right link leaves the
    download in the *UserActionRequired* state; the caller is responsible for
    signalling cancellation to the provider.

    Args:
        url (str): Nexus Mods page URL to open (with ``?tab=files&file_id=…&nmm=1``).
        expected_game (str): Nexus Mods game id (e.g. ``"skyrimspecialedition"``).
        expected_mod_id (int): Expected mod id.
        expected_file_id (int): Expected file id.
        data_path (Optional[Path]):
            Root data path used to persist cookies/login across sessions.
            When ``None`` an in-memory (non-persistent) profile is used.
        auto_click (bool):
            Whether to auto-click the Nexus Mods download button after page load.
        parent (Optional[QWidget]): Qt parent widget.
    """

    nxm_captured: Signal = Signal(str)
    """
    Emitted once a valid, matching ``nxm://`` link has been intercepted.

    Args:
        str: The full NXM URL string, ready to be forwarded to
             :attr:`NXMHandler.request_signal`.
    """

    _shared_profile: Optional[QWebEngineProfile] = None
    """Shared persistent browser profile instance."""

    PROFILE_FOLDER_NAME: str = "nexus-profile"
    """Sub-folder name inside ``data_path / "browser"`` for the persistent profile."""

    log: logging.Logger = logging.getLogger("NexusDownloadBrowserDialog")

    __web_view: QWebEngineView
    __web_page: _NexusWebPage
    __profile: QWebEngineProfile

    __expected_game: str
    __expected_mod_id: int
    __expected_file_id: int
    __target_url: str
    __auto_click: bool

    def __init__(
        self,
        url: str,
        expected_game: str,
        expected_mod_id: int,
        expected_file_id: int,
        data_path: Optional[Path] = None,
        auto_click: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.__target_url = url
        self.__expected_game = expected_game
        self.__expected_mod_id = expected_mod_id
        self.__expected_file_id = expected_file_id
        self.__auto_click = auto_click

        self.__profile = self.__create_profile(data_path)
        self.__web_page = _NexusWebPage(self.__profile, self)
        self.__web_page.nxm_intercepted.connect(self.__on_nxm_intercepted)

        self.__init_ui()
        self.__web_view.load(QUrl(url))

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def __create_profile(self, data_path: Optional[Path]) -> QWebEngineProfile:
        if data_path is not None:
            if NexusDownloadBrowserDialog._shared_profile is not None:
                return NexusDownloadBrowserDialog._shared_profile

            profile_path = data_path / "browser" / self.PROFILE_FOLDER_NAME
            profile_path.mkdir(parents=True, exist_ok=True)
            # Named profiles use the folder *name*, not the full path;
            # we set storagePath explicitly via the off-the-shelf constructor.
            # We create it with no parent so it doesn't get destroyed with the dialog.
            profile = QWebEngineProfile("nexus-profile")
            profile.setPersistentStoragePath(str(profile_path))
            profile.setCachePath(str(profile_path / "cache"))
            profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
            )
            self.log.debug(
                f"Using persistent browser profile at '{profile_path}'."
            )
            NexusDownloadBrowserDialog._shared_profile = profile
            return profile
        else:
            # In-memory profile (used in tests / when data_path is unavailable)
            profile = QWebEngineProfile(self)
            self.log.debug("Using in-memory (non-persistent) browser profile.")
            return profile

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def __init_ui(self) -> None:
        self.setWindowTitle(self.tr("Nexus Mods – Mod Manager Download"))
        self.setMinimumSize(1100, 750)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        vlayout = QVBoxLayout(self)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.setSpacing(0)
        self.setLayout(vlayout)

        vlayout.addWidget(self.__build_toolbar())

        self.__web_view = QWebEngineView(self.__web_page, self)
        self.__web_view.titleChanged.connect(self.__on_title_changed)
        self.__web_view.loadFinished.connect(self.__on_load_finished)
        vlayout.addWidget(self.__web_view, stretch=1)

        vlayout.addWidget(self.__build_footer())

    def __build_toolbar(self) -> QToolBar:
        toolbar = QToolBar(self)
        toolbar.setMovable(False)

        back_action = toolbar.addAction(self.tr("←"))
        back_action.setToolTip(self.tr("Back"))
        back_action.triggered.connect(lambda: self.__web_view.back())

        forward_action = toolbar.addAction(self.tr("→"))
        forward_action.setToolTip(self.tr("Forward"))
        forward_action.triggered.connect(lambda: self.__web_view.forward())

        reload_action = toolbar.addAction(self.tr("↺"))
        reload_action.setToolTip(self.tr("Reload"))
        reload_action.triggered.connect(lambda: self.__web_view.reload())

        toolbar.addSeparator()

        auto_click_action = toolbar.addAction(self.tr("Auto-click"))
        auto_click_action.setToolTip(
            self.tr("Automatically click the Nexus Mods download button when it appears")
        )
        auto_click_action.setCheckable(True)
        auto_click_action.setChecked(self.__auto_click)
        auto_click_action.toggled.connect(self.__set_auto_click)

        toolbar.addSeparator()

        open_external_action = toolbar.addAction(self.tr("Open in browser"))
        open_external_action.setToolTip(self.tr("Open current page in the system browser"))
        open_external_action.triggered.connect(self.__open_in_external_browser)

        return toolbar

    def __build_footer(self) -> QWidget:
        footer = QWidget(self)
        hlayout = QHBoxLayout(footer)
        hlayout.setContentsMargins(8, 4, 8, 4)

        hint = QPushButton(
            self.tr(
                "Click \"Mod Manager Download\" on the Nexus page, then this dialog "
                "will close automatically."
            )
        )
        hint.setFlat(True)
        hint.setEnabled(False)
        hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        hlayout.addWidget(hint, stretch=1)

        cancel_btn = QPushButton(self.tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        hlayout.addWidget(cancel_btn)

        return footer

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def __on_title_changed(self, title: str) -> None:
        if title:
            self.setWindowTitle(
                self.tr("Nexus Mods – Mod Manager Download") + f" – {title}"
            )

    def __set_auto_click(self, enabled: bool) -> None:
        self.__auto_click = enabled
        if enabled:
            self.__web_page.runJavaScript(JS_AUTO_CLICK_NEXUS_DOWNLOAD)

    def __on_load_finished(self, ok: bool) -> None:
        if ok and self.__auto_click:
            self.__web_page.runJavaScript(JS_AUTO_CLICK_NEXUS_DOWNLOAD)

    def __open_in_external_browser(self) -> None:
        current_url = self.__web_view.url().toString()
        if current_url and current_url != "about:blank":
            webbrowser.open(current_url)
        else:
            webbrowser.open(self.__target_url)

    def __on_nxm_intercepted(self, raw_url: str) -> None:
        """Validate the intercepted ``nxm://`` URL and accept or warn."""

        self.log.info(f"Intercepted nxm:// URL: {raw_url!r}")

        try:
            request = NxmRequest.from_url(raw_url)
        except Exception as ex:
            self.log.error(f"Failed to parse nxm:// URL: {ex}", exc_info=ex)
            self.__show_parse_error(raw_url)
            return

        if (
            request.game == self.__expected_game
            and request.mod_id == self.__expected_mod_id
            and request.file_id == self.__expected_file_id
        ):
            self.log.info(
                f"NXM link matches expected download "
                f"(game={request.game}, mod_id={request.mod_id}, "
                f"file_id={request.file_id}). Forwarding to NXMHandler."
            )
            self.nxm_captured.emit(raw_url)
            self.accept()
        else:
            self.log.warning(
                f"NXM link mismatch: "
                f"expected game={self.__expected_game!r} mod_id={self.__expected_mod_id} "
                f"file_id={self.__expected_file_id}, "
                f"got game={request.game!r} mod_id={request.mod_id} "
                f"file_id={request.file_id}."
            )
            self.__show_mismatch_warning(request)

    def __show_mismatch_warning(self, request: NxmRequest) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle(self.tr("Wrong file"))
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(
            self.tr(
                "The download you clicked does not match the file in the queue.\n\n"
                "Expected:\n"
                "  Mod ID: {expected_mod_id}\n"
                "  File ID: {expected_file_id}\n\n"
                "Got:\n"
                "  Mod ID: {actual_mod_id}\n"
                "  File ID: {actual_file_id}\n\n"
                "Please go back and click the correct file."
            ).format(
                expected_mod_id=self.__expected_mod_id,
                expected_file_id=self.__expected_file_id,
                actual_mod_id=request.mod_id,
                actual_file_id=request.file_id,
            )
        )
        msg.exec()

    def __show_parse_error(self, raw_url: str) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle(self.tr("Error"))
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(
            self.tr("Failed to parse the download link:\n{url}").format(url=raw_url)
        )
        msg.exec()

    # ------------------------------------------------------------------
    # Class-level convenience
    # ------------------------------------------------------------------

    @staticmethod
    def open_for_download(
        url: str,
        expected_game: str,
        expected_mod_id: int,
        expected_file_id: int,
        data_path: Optional[Path] = None,
        auto_click: bool = True,
        parent: Optional[QWidget] = None,
    ) -> bool:
        """
        Creates and shows the browser dialog modally.

        On a successful capture the ``nxm://`` URL is forwarded to
        :attr:`NXMHandler.request_signal` automatically before this
        method returns.

        Returns:
            bool: ``True`` if the link was captured (dialog accepted),
                  ``False`` if the user cancelled.
        """

        dialog = NexusDownloadBrowserDialog(
            url=url,
            expected_game=expected_game,
            expected_mod_id=expected_mod_id,
            expected_file_id=expected_file_id,
            data_path=data_path,
            auto_click=auto_click,
            parent=parent,
        )
        dialog.nxm_captured.connect(NXMHandler.get().request_signal.emit)

        result = dialog.exec()
        return result == QDialog.DialogCode.Accepted
