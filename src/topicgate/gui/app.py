

import sys
import asyncio
from PySide6.QtCore import QCoreApplication, QEventLoop
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from topicgate.app.app_dependencies import AppDependencies
from topicgate.app.service_container import ServiceContainer
from topicgate.gui.main_window import MainWindow
from topicgate.gui.main_view_model import MainViewModel

class App:
    def __init__(self, qt_application: QApplication):
        self._qt_application = qt_application
        self._dependencies = AppDependencies()
        self._services = ServiceContainer(self._dependencies)
        self._view_model = MainViewModel(
            runtime=self._dependencies.runtime
        )
        self._window = MainWindow(self._view_model)
        

    async def run(self) -> int:
        try:
            try:
                await self._services.start_services()
            except ConnectionError as error:
                self._view_model.log_message.emit(
                    f"Initial MQTT connection failed: {error}"
                )
            await self._view_model.start()
            stopped = asyncio.get_running_loop().create_future()
            self._qt_application.aboutToQuit.connect(
                lambda: not stopped.done() and stopped.set_result(None)
            )
            self._window.show()
            await stopped
            return 0
        finally:
            await self._view_model.stop()
            await self._services.stop_services()


def configure_application_identity() -> None:
    QCoreApplication.setOrganizationName("Dumdart")
    QCoreApplication.setApplicationName("TopicGate")
    QGuiApplication.setApplicationDisplayName("TopicGate Desktop")


def run() -> int:
    configure_application_identity()
    qt_application = QApplication(sys.argv)
    event_loop = QEventLoop(qt_application)
    asyncio.set_event_loop(event_loop)

    app = App(qt_application)

    with event_loop:
        return event_loop.run_until_complete(app.run())
