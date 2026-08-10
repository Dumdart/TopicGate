from collections.abc import Callable

from PySide6.QtCore import QObject, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QLabel


class ConnectionStatusLabel(QLabel):
    """Prominent connection state displayed in the menu bar corner."""

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
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(self.sizeHint())
        self.setContentsMargins(0, 0, 0, 0)

    @property
    def status(self) -> str:
        return self._status

    def sizeHint(self) -> QSize:
        return QSize(188, 34)

    def render(self, status: str) -> None:
        self._status = status.lower()
        status_label = self._status.title()
        self.setText(f"MQTT {status_label}")
        self.setAccessibleDescription(f"MQTT connection is {self._status}.")
        self.setToolTip(f"MQTT broker is {self._status}")
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        accent = QColor(self._STATUS_COLORS.get(self._status, "#6b7280"))
        surface = self.palette().color(QPalette.ColorRole.Window)
        foreground = QColor(
            "#f8fafc" if surface.lightnessF() < 0.5 else "#1f2937"
        )
        muted = QColor(foreground)
        muted.setAlpha(164)

        fill = QColor(accent)
        fill.setAlpha(18)
        border = QColor(accent)
        border.setAlpha(62)
        pill = QRectF(self.rect()).adjusted(1.5, 2.5, -1.5, -2.5)
        painter.setPen(border)
        painter.setBrush(self._blend(surface, fill))
        painter.drawRoundedRect(pill, 8, 8)

        halo = QColor(accent)
        halo.setAlpha(38)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(QRectF(11, 11, 12, 12))
        painter.setBrush(accent)
        painter.drawEllipse(QRectF(14, 14, 6, 6))

        label_font = QFont(self.font())
        label_font.setPointSizeF(9.5)
        label_font.setWeight(QFont.Weight.Medium)
        painter.setFont(label_font)
        painter.setPen(muted)
        painter.drawText(
            QRectF(29, 2, 43, self.height() - 4),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "MQTT",
        )

        divider = QColor(foreground)
        divider.setAlpha(45)
        painter.setPen(divider)
        painter.drawLine(72, 11, 72, self.height() - 11)

        status_font = QFont(label_font)
        status_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(status_font)
        painter.setPen(foreground)
        painter.drawText(
            QRectF(82, 2, self.width() - 91, self.height() - 4),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._status.title(),
        )

    @staticmethod
    def _blend(base: QColor, overlay: QColor) -> QColor:
        alpha = overlay.alphaF()
        return QColor(
            round(base.red() * (1 - alpha) + overlay.red() * alpha),
            round(base.green() * (1 - alpha) + overlay.green() * alpha),
            round(base.blue() * (1 - alpha) + overlay.blue() * alpha),
        )


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
