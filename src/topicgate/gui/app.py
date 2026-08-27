

import asyncio
import ctypes
import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from topicgate.app.app_dependencies import AppDependencies
from topicgate.app.services.service_container import ServiceContainer
from topicgate.gui.main_window import MainWindow
from topicgate.gui.main_view_model import MainViewModel
from topicgate.gui.theme import apply_light_theme
from topicgate.paths import asset_path


class App:
    def __init__(self, qt_application: QApplication):
        self._qt_application = qt_application
        self._dependencies = AppDependencies(control_owner="desktop")
        self._services = ServiceContainer(self._dependencies)
        self._view_model = MainViewModel(
            runtime=self._dependencies.runtime,
            snapshot_service=self._dependencies.snapshot_service,
            mcp_setup_service=self._dependencies.mcp_setup,
        )
        self._window = MainWindow(self._view_model)


    async def run(self) -> int:
        # Check that closing the last window does not stop qasync before
        # asynchronous cleanup has completed.
        self._qt_application.setQuitOnLastWindowClosed(False)
        stopped = asyncio.get_running_loop().create_future()

        def request_shutdown() -> None:
            if not stopped.done():
                stopped.set_result(None)

        self._qt_application.lastWindowClosed.connect(request_shutdown)
        try:
            try:
                await self._services.start_services()
            except ConnectionError as error:
                self._view_model.log_message.emit(
                    f"Initial MQTT connection failed: {error}"
                )
            await self._view_model.start()
            self._window.show()
            await stopped
            return 0
        finally:
            try:
                try:
                    cancel_operations = getattr(
                        self._window,
                        "cancel_pending_operations",
                        None,
                    )
                    if cancel_operations is not None:
                        await cancel_operations()
                finally:
                    await self._view_model.stop()
            finally:
                await self._services.stop_services()


def configure_windows_identity() -> None:
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Dumdart.TopicGate"
        )


def configure_application_identity() -> None:
    QCoreApplication.setOrganizationName("Dumdart")
    QCoreApplication.setApplicationName("TopicGate")
    QGuiApplication.setApplicationDisplayName("TopicGate Desktop")


def run() -> int:
    configure_windows_identity()
    configure_application_identity()

    qt_application = QApplication(sys.argv)
    icon = QIcon(asset_path("icon.png"))
    qt_application.setWindowIcon(icon)

    apply_light_theme(qt_application)

    event_loop = QEventLoop(qt_application)
    asyncio.set_event_loop(event_loop)

    app = App(qt_application)

    with event_loop:
        return event_loop.run_until_complete(app.run())
