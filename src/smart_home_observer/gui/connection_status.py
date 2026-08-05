from PySide6.QtWidgets import QLabel


class ConnectionStatusLabel(QLabel):
    """Compact connection state intended for the menu bar corner."""

    _COLORS = {
        "connected": "#2e7d32",
        "connecting": "#9a6700",
        "reconnecting": "#9a6700",
        "disconnected": "#b3261e",
    }

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("connectionStatus")
        self.setAccessibleName("MQTT connection status")
        self.setContentsMargins(8, 0, 12, 0)

    def render(self, status: str) -> None:
        color = self._COLORS.get(status, "#5f6368")
        self.setText(f"\u25cf  {status.title()}")
        self.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.setToolTip(f"MQTT connection: {status}")
