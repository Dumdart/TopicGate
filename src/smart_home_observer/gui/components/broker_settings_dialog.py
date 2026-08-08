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
from uuid import UUID

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.gui.main_view_model import MainViewModel


class BrokerSettingsDialog(QDialog):
    """Create or edit a broker profile and its MQTT configuration."""

    apply_requested = Signal()
    save_requested = Signal()

    def __init__(
        self,
        view_model: MainViewModel,
        parent: QWidget | None = None,
        *,
        creating: bool = False,
        profile_id: UUID | None = None,
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._port_was_changed = False
        self.setWindowTitle(
            "Add broker profile" if creating else "Edit broker profile"
        )
        self.setObjectName(
            "createBrokerProfileDialog" if creating else "brokerSettingsDialog"
        )

        selected_profile = None
        if not creating:
            selected_profile = (
                view_model.active_broker_profile
                if profile_id is None
                else next(
                    profile
                    for profile in view_model.broker_profiles
                    if profile.id == profile_id
                )
            )
        self._profile_id = None if selected_profile is None else selected_profile.id
        mqtt_config = (
            MqttConfig("localhost", 1883, "", "")
            if selected_profile is None
            else selected_profile.config
        )
        layout = QFormLayout(self)
        self._name_edit = QLineEdit(
            "" if selected_profile is None else selected_profile.name
        )
        self._name_edit.setObjectName("brokerProfileNameEdit")
        self._name_edit.setPlaceholderText("Home broker")
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

        layout.addRow("Profile", self._name_edit)
        layout.addRow("Host", self._host_edit)
        layout.addRow("Port", self._port_edit)
        layout.addRow("Username", self._username_edit)
        layout.addRow("Password", self._password_edit)
        layout.addRow("Use TLS", self._use_tls_checkbox)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._buttons.setObjectName("brokerSettingsButtons")
        self._save_button: QPushButton | None = None
        if not creating:
            self._save_button = self._buttons.addButton(
                "Save",
                QDialogButtonBox.ButtonRole.ApplyRole,
            )
            self._save_button.setObjectName("saveBrokerSettingsButton")
        self._apply_button = self._buttons.addButton(
            "Add profile"
            if creating
            else (
                "Save & reconnect"
                if self._profile_id == view_model.active_broker_profile.id
                else "Save & connect"
            ),
            QDialogButtonBox.ButtonRole.ApplyRole,
        )
        self._apply_button.setObjectName("applyBrokerSettingsButton")
        self._cancel_button = self._buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(self._buttons)

        self._name_edit.textChanged.connect(self._update_apply_enabled)
        self._host_edit.textChanged.connect(self._update_apply_enabled)
        self._port_edit.textChanged.connect(self._update_apply_enabled)
        self._port_edit.textEdited.connect(self._mark_port_changed)
        self._use_tls_checkbox.toggled.connect(self._update_tls_port)
        if self._save_button is not None:
            self._save_button.clicked.connect(self.save_requested.emit)
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

    @property
    def profile_id(self) -> UUID | None:
        """Return the profile selected for the pending broker update."""
        return self._profile_id

    @property
    def profile_name(self) -> str:
        """Return the validated broker profile name entered by the user."""
        name = self._name_edit.text().strip()
        if not name:
            raise ValueError("A broker profile name is required.")
        if any(
            profile.id != self._profile_id
            and profile.name.casefold() == name.casefold()
            for profile in self._view_model.broker_profiles
        ):
            raise ValueError("A broker profile with that name already exists.")
        return name

    def set_applying(self, applying: bool) -> None:
        """Prevent edits while a broker update is reconnecting."""
        for control in (
            self._name_edit,
            self._host_edit,
            self._port_edit,
            self._username_edit,
            self._password_edit,
            self._use_tls_checkbox,
        ):
            control.setEnabled(not applying)
        self._cancel_button.setEnabled(not applying)
        if self._save_button is not None:
            self._save_button.setEnabled(not applying and self._is_valid())
        self._apply_button.setEnabled(not applying and self._is_valid())

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._name_edit.setFocus()

    def _mark_port_changed(self, _port: str) -> None:
        self._port_was_changed = True

    def _update_tls_port(self, use_tls: bool) -> None:
        if use_tls and not self._port_was_changed:
            self._port_edit.setText("8883")

    def _update_apply_enabled(self, *_args: object) -> None:
        is_valid = self._is_valid()
        if self._save_button is not None:
            self._save_button.setEnabled(is_valid)
        self._apply_button.setEnabled(is_valid)

    def _is_valid(self) -> bool:
        try:
            self.profile_name
            self.mqtt_config
        except ValueError:
            return False
        return True
