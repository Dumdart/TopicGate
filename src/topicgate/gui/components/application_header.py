from uuid import UUID

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from topicgate.core.models.broker_summary import BrokerSummary
from topicgate.gui.components.connection_controls import ConnectionStatusLabel


class BrokerSelector(QComboBox):
    broker_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("brokerSelector")
        self.setAccessibleName("Active broker")
        self.currentIndexChanged.connect(self._emit_selection)

    def render(self, brokers: tuple[BrokerSummary, ...], active_id: UUID) -> None:
        self.blockSignals(True)
        self.clear()
        active_index = 0
        for index, broker in enumerate(brokers):
            self.addItem(broker.name, broker.id)
            if broker.id == active_id:
                active_index = index
        self.setCurrentIndex(active_index)
        self.blockSignals(False)

    def _emit_selection(self, index: int) -> None:
        if index >= 0:
            self.broker_selected.emit(self.itemData(index))


class ApplicationHeader(QFrame):
    broker_selected = Signal(object)
    connect_requested = Signal()
    reconnect_requested = Signal()
    disconnect_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("applicationHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(12)
        identity = QVBoxLayout()
        title = QLabel("TopicGate")
        title.setObjectName("applicationTitle")
        subtitle = QLabel("MQTT observer desktop")
        subtitle.setStyleSheet("color: #6b7280;")
        identity.addWidget(title)
        identity.addWidget(subtitle)
        layout.addLayout(identity)
        layout.addStretch(1)
        broker_group = QVBoxLayout()
        label = QLabel("BROKER")
        label.setObjectName("sectionTitle")
        self.selector = BrokerSelector()
        self.selector.setMinimumWidth(220)
        self.selector.broker_selected.connect(self.broker_selected.emit)
        self.endpoint = QLabel()
        self.endpoint.setObjectName("brokerEndpoint")
        self.endpoint.setStyleSheet("color: #6b7280;")
        self.endpoint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        broker_group.addWidget(label)
        broker_group.addWidget(self.selector)
        broker_group.addWidget(self.endpoint)
        layout.addLayout(broker_group)
        self.status = ConnectionStatusLabel()
        layout.addWidget(self.status)
        self.connect_button = self._button("Connect", "headerConnectButton")
        self.reconnect_button = self._button("Reconnect", "headerReconnectButton")
        self.disconnect_button = self._button("Disconnect", "headerDisconnectButton")
        self.connect_button.clicked.connect(self.connect_requested.emit)
        self.reconnect_button.clicked.connect(self.reconnect_requested.emit)
        self.disconnect_button.clicked.connect(self.disconnect_requested.emit)
        for button in (self.connect_button, self.reconnect_button, self.disconnect_button):
            layout.addWidget(button)

    def render(self, brokers: tuple[BrokerSummary, ...], active: BrokerSummary, status: str, busy: bool) -> None:
        self.selector.render(brokers, active.id)
        scheme = "mqtts" if active.config.use_tls else "mqtt"
        self.endpoint.setText(f"{scheme}://{active.config.host}:{active.config.port}")
        self.status.render(status)
        self.selector.setEnabled(not busy)
        self.connect_button.setEnabled(status == "disconnected" and not busy)
        self.reconnect_button.setEnabled(status in {"connected", "reconnecting"} and not busy)
        self.disconnect_button.setEnabled(status in {"connecting", "connected", "reconnecting"} and not busy)

    @staticmethod
    def _button(text: str, name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)
        return button
