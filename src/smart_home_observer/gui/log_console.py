from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QPlainTextEdit, QWidget


class LogConsoleDock(QDockWidget):
    """Collapsible bounded log console for observer events."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Log console", parent)
        self.setObjectName("logConsoleDock")
        self.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)

        self._console = QPlainTextEdit()
        self._console.setObjectName("logConsole")
        self._console.setReadOnly(True)
        self._console.setMaximumBlockCount(2000)
        self.setWidget(self._console)

    def append_message(self, message: str) -> None:
        timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
        self._console.appendPlainText(f"{timestamp}  {message}")
