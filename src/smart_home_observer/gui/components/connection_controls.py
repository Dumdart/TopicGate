from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel


class ConnectionStatusLabel(QLabel):
    """Prominent connection state displayed in the menu bar corner."""

    _COLORS = {
        "connected": ("#1b5e20", "#e8f5e9"),
        "connecting": ("#7a4f00", "#fff4ce"),
        "reconnecting": ("#7a4f00", "#fff4ce"),
        "disconnected": ("#9f1c16", "#fdecea"),
    }

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("connectionStatus")
        self.setAccessibleName("MQTT connection status")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(164, 34)
        self.setContentsMargins(12, 2, 12, 2)

    def render(self, status: str) -> None:
        foreground, background = self._COLORS.get(
            status,
            ("#424242", "#eeeeee"),
        )
        self.setText(f"\u25cf  MQTT {status.title()}")
        self.setStyleSheet(
            f"color: {foreground};"
            f"background-color: {background};"
            f"border: 1px solid {foreground};"
            "border-radius: 8px;"
            "font-size: 14px;"
            "font-weight: 700;"
            "padding: 4px 12px;"
        )
        self.setToolTip(f"MQTT connection: {status}")


class ConnectionControls(QObject):
    """Bundle MQTT connection state and lifecycle actions."""

    connect_requested = Signal()
    reconnect_requested = Signal()
    disconnect_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.status_label = ConnectionStatusLabel()
        self.connect_action = self._create_action(
            "Connect",
            "connectAction",
            "Connect to the MQTT broker",
            self.connect_requested.emit,
        )
        self.reconnect_action = self._create_action(
            "Reconnect",
            "reconnectAction",
            "Reconnect to the MQTT broker",
            self.reconnect_requested.emit,
        )
        self.disconnect_action = self._create_action(
            "Disconnect",
            "disconnectAction",
            "Disconnect from the MQTT broker",
            self.disconnect_requested.emit,
        )

    @property
    def actions(self) -> tuple[QAction, QAction, QAction]:
        return (
            self.connect_action,
            self.reconnect_action,
            self.disconnect_action,
        )

    def render(self, status: str) -> None:
        self.status_label.render(status)
        self.connect_action.setEnabled(status == "disconnected")
        self.reconnect_action.setEnabled(status in {"connected", "reconnecting"})
        self.disconnect_action.setEnabled(
            status in {"connecting", "connected", "reconnecting"}
        )

    def _create_action(
        self,
        text: str,
        object_name: str,
        tooltip: str,
        requested: Callable[[], None],
    ) -> QAction:
        action = QAction(text, self)
        action.setObjectName(object_name)
        action.setToolTip(tooltip)
        action.triggered.connect(lambda _checked=False: requested())
        return action
