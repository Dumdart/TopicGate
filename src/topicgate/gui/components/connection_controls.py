from collections.abc import Callable

from PySide6.QtCore import QObject, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QLabel


class ConnectionStatusLabel(QLabel):
    """Compact textual connection state for the application header."""

    _STATUS_COLORS = {
        "connected": "#168a55",
        "connecting": "#b66a00",
        "reconnecting": "#b66a00",
        "disconnected": "#c43d3d",
    }

    def __init__(self) -> None:
        super().__init__()
        self._status = "disconnected"
        self.setObjectName("connectionStatus")
        self.setAccessibleName("MQTT connection status")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setMinimumSize(self.sizeHint())
        self.setContentsMargins(0, 0, 0, 0)

    @property
    def status(self) -> str:
        return self._status

    def sizeHint(self) -> QSize:
        return QSize(108, 24)

    def render(self, status: str) -> None:
        self._status = status.lower()
        status_label = self._status.title()
        self.setText(status_label)
        self.setAccessibleDescription(f"MQTT connection is {self._status}.")
        self.setToolTip(f"MQTT broker is {self._status}")
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        accent = QColor(self._STATUS_COLORS.get(self._status, "#6b7280"))
        halo = QColor(accent)
        halo.setAlpha(42)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(QRectF(1, 6, 12, 12))
        painter.setBrush(accent)
        painter.drawEllipse(QRectF(4, 9, 6, 6))

        label_font = QFont(self.font())
        label_font.setPointSizeF(9.0)
        label_font.setWeight(QFont.Weight.Medium)
        painter.setFont(label_font)
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        painter.drawText(
            QRectF(19, 0, self.width() - 19, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._status.title(),
        )


class ConnectionControls(QObject):
    """Bundle MQTT connection state and lifecycle actions."""

    connect_requested = Signal()
    reconnect_requested = Signal()
    disconnect_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.connect_action = self._create_action(
            "Connect",
            "connectAction",
            "Connect to the MQTT broker",
            self.connect_requested.emit,
        )
        self.reconnect_action = self._create_action(
            "Reconnect & observe",
            "reconnectAction",
            "Interrupt and renew the MQTT connection, then capture a snapshot",
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

    def render(self, status: str, busy: bool = False) -> None:
        self.connect_action.setEnabled(status == "disconnected" and not busy)
        self.reconnect_action.setEnabled(
            status in {"connected", "reconnecting"} and not busy
        )
        self.disconnect_action.setEnabled(
            status in {"connecting", "connected", "reconnecting"} and not busy
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
