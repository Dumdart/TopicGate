from PySide6.QtCore import Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.gui.main_view_model import MainViewModel


class BrokerSettingsDialog(QDialog):
    """Edit global MQTT broker settings before reconnecting."""

    apply_requested = Signal()

    def __init__(
        self,
        view_model: MainViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._port_was_changed = False
        self.setWindowTitle("Broker settings")
        self.setObjectName("brokerSettingsDialog")

        mqtt_config = view_model.mqtt_config
        layout = QFormLayout(self)
        self._host_edit = QLineEdit(mqtt_config.host)
        self._host_edit.setObjectName("brokerHostEdit")
        self._host_edit.setPlaceholderText("mqtt.example.com")
        self._port_edit = QLineEdit(str(mqtt_config.port))
        self._port_edit.setObjectName("brokerPortEdit")
        self._username_edit = QLineEdit(mqtt_config.username)
        self._username_edit.setObjectName("brokerUsernameEdit")
        self._password_edit = QLineEdit(mqtt_config.password)
        self._password_edit.setObjectName("brokerPasswordEdit")
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._use_tls_checkbox = QCheckBox()
        self._use_tls_checkbox.setObjectName("brokerUseTlsCheckbox")
        self._use_tls_checkbox.setChecked(mqtt_config.use_tls)

        layout.addRow("Host", self._host_edit)
        layout.addRow("Port", self._port_edit)
        layout.addRow("Username", self._username_edit)
        layout.addRow("Password", self._password_edit)
        layout.addRow("Use TLS", self._use_tls_checkbox)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._buttons.setObjectName("brokerSettingsButtons")
        self._apply_button = self._buttons.addButton(
            "Apply & reconnect",
            QDialogButtonBox.ButtonRole.ApplyRole,
        )
        self._apply_button.setObjectName("applyBrokerSettingsButton")
        self._cancel_button = self._buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(self._buttons)

        self._host_edit.textChanged.connect(self._update_apply_enabled)
        self._port_edit.textChanged.connect(self._update_apply_enabled)
        self._port_edit.textEdited.connect(self._mark_port_changed)
        self._use_tls_checkbox.toggled.connect(self._update_tls_port)
        self._apply_button.clicked.connect(self.apply_requested.emit)
        self._buttons.rejected.connect(self.reject)
        self._update_apply_enabled()

    @property
    def mqtt_config(self) -> MqttConfig:
        """Return the validated broker configuration entered by the user."""
        host = self._host_edit.text().strip()
        port_text = self._port_edit.text().strip()
        if not host:
            raise ValueError("MQTT host is required.")
        try:
            port = int(port_text)
        except ValueError as error:
            raise ValueError("MQTT port must be an integer from 1 to 65535.") from error
        if not 1 <= port <= 65535:
            raise ValueError("MQTT port must be an integer from 1 to 65535.")
        return MqttConfig(
            host=host,
            port=port,
            username=self._username_edit.text(),
            password=self._password_edit.text(),
            use_tls=self._use_tls_checkbox.isChecked(),
        )

    def set_applying(self, applying: bool) -> None:
        """Prevent edits while a broker update is reconnecting."""
        for control in (
            self._host_edit,
            self._port_edit,
            self._username_edit,
            self._password_edit,
            self._use_tls_checkbox,
        ):
            control.setEnabled(not applying)
        self._cancel_button.setEnabled(not applying)
        self._apply_button.setEnabled(not applying and self._is_valid())

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._host_edit.setFocus()

    def _mark_port_changed(self, _port: str) -> None:
        self._port_was_changed = True

    def _update_tls_port(self, use_tls: bool) -> None:
        if use_tls and not self._port_was_changed:
            self._port_edit.setText("8883")

    def _update_apply_enabled(self, *_args: object) -> None:
        self._apply_button.setEnabled(self._is_valid())

    def _is_valid(self) -> bool:
        try:
            self.mqtt_config
        except ValueError:
            return False
        return True
