"""
Copyright (c) Cutleast
"""

import logging
import webbrowser
from pathlib import Path
from typing import Optional

from cutleast_core_lib.core.utilities.scale import scale_value
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QPushButton, QTreeWidget, QTreeWidgetItem

from core.downloader.file_download import FileDownload
from core.translation_provider.nm_api.nm_api import NexusModsApi
from core.translation_provider.nm_api.nxm_handler import NXMHandler
from core.translation_provider.nm_api.nxm_id import NxmModId
from core.utilities.progress_update import ProgressUpdate
from ui.downloader.nexus_download_browser import NexusDownloadBrowserDialog
from ui.utilities.icon_provider import IconProvider
from ui.widgets.progress_widget import ProgressWidget


class DownloadItem(QTreeWidgetItem, QObject):  # type: ignore
    """
    Class for items in the Downloads tab.

    TODO: Add button to remove a download from the queue
    """

    __update_signal = Signal(ProgressUpdate)

    finished_signal = Signal(object)
    """
    This signal gets emitted when the download is finished and can be removed.
    """

    remove_signal = Signal(object)
    """
    This signal gets emitted when the download should be removed from the queue.
    """

    log: logging.Logger = logging.getLogger("DownloadItem")

    download: FileDownload
    current_widget: Optional[ProgressWidget | QPushButton] = None

    def __init__(self, download: FileDownload) -> None:
        QObject.__init__(self)
        super().__init__()

        self.download = download
        self.__update_signal.connect(
            self.__update_progress, Qt.ConnectionType.QueuedConnection
        )

        self.setText(0, self.download.mod_details.display_name)
        self.setIcon(0, self.download.source.get_icon())  # pyright: ignore[reportArgumentType] (source can't be Local here)

    def __show_download_button(self) -> None:
        if isinstance(self.current_widget, QPushButton):
            return

        parent: QTreeWidget = self.treeWidget()

        button = QPushButton(
            IconProvider.get_qta_icon("ri.download-line"),
            self.tr("Non-premium download..."),
        )

        def open_download_page() -> None:
            assert isinstance(self.download.mod_details.mod_id, NxmModId)

            mod_id: NxmModId = self.download.mod_details.mod_id

            url = NexusModsApi.create_nexus_mods_url(
                mod_id.nm_game_id,
                mod_id.mod_id,
                mod_id.file_id,
                mod_manager=True,
            )

            self.log.debug(f"Opening internal browser for {url!r}...")

            # Resolve data path for the persistent browser profile.
            data_path: Optional[Path] = None
            try:
                from core.user_data.user_data_service import UserDataService
                data_path = UserDataService.get().get_data_path()
            except Exception:
                self.log.warning(
                    "UserDataService not available; browser profile will be in-memory."
                )

            dialog = NexusDownloadBrowserDialog(
                url=url,
                expected_game=mod_id.nm_game_id,
                expected_mod_id=mod_id.mod_id,
                expected_file_id=mod_id.file_id or 0,
                data_path=data_path,
                parent=parent,
            )
            dialog.nxm_captured.connect(NXMHandler.get().request_signal.emit)

            def on_rejected() -> None:
                """Cancel the blocked worker when the user closes the dialog."""
                self.log.info("Download browser closed without capturing NXM link.")
                # Signal the provider to stop waiting for the NXM link
                from core.translation_provider.provider_manager import ProviderManager
                try:
                    nm_api = ProviderManager.get_provider(NexusModsApi)
                    nm_api.cancel_pending_download()
                except Exception as ex:
                    self.log.warning(
                        f"Could not cancel pending download: {ex}"
                    )

            dialog.rejected.connect(on_rejected)

            dialog.exec()

            button.setIcon(IconProvider.get_qta_icon("fa5s.check"))

        button.clicked.connect(open_download_page)

        parent.setItemWidget(self, 2, button)
        self.current_widget = button

    def __show_progress_widget(self) -> None:
        if isinstance(self.current_widget, ProgressWidget):
            return

        parent: QTreeWidget = self.treeWidget()
        progress_widget = ProgressWidget(self)
        progress_widget.close_signal.connect(lambda: self.remove_signal.emit(self))
        parent.setItemWidget(self, 2, progress_widget)
        self.current_widget = progress_widget

    def update_progress(self, progress_update: ProgressUpdate) -> None:
        """
        Updates progress of the mod item. This method is thread-safe.

        Args:
            progress_update (ProgressUpdate): Progress update created by worker thread.
        """

        self.__update_signal.emit(progress_update)

    def __update_progress(self, progress_update: ProgressUpdate) -> None:
        match progress_update.status_text:
            case ProgressUpdate.Status.UserActionRequired:
                # User has no premium and must start download in browser
                self.__show_download_button()

            case ProgressUpdate.Status.Finished:
                self.finished_signal.emit(self)

            case ProgressUpdate.Status.Failed:
                self.__show_progress_widget()

                if (
                    isinstance(self.current_widget, ProgressWidget)
                    and progress_update.exception
                ):
                    self.current_widget.setException(progress_update.exception)

            case text:
                self.__show_progress_widget()

                if isinstance(self.current_widget, ProgressWidget):
                    self.current_widget.setProgress(
                        progress_update.current, progress_update.maximum
                    )

                if progress_update.speed is not None:
                    text = (text or "") + f" ({scale_value(progress_update.speed)}/s)"

                if text is not None and self.current_widget is not None:
                    self.current_widget.setText(text)

        if progress_update.maximum > 1 and progress_update.maximum != 100:
            self.setText(1, scale_value(progress_update.maximum))
