from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from topicgate.core.models.subscription import Subscription


class AddSubscriptionDialog(QDialog):
    """Collect and validate a new MQTT subscription filter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add topic filter")
        layout = QFormLayout(self)

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("home/+/temperature")
        self._qos_combo = QComboBox()
        self._qos_combo.addItems(
            [
                "0 - At most once",
                "1 - At least once",
                "2 - Exactly once",
            ]
        )
        self._qos_combo.setCurrentIndex(1)
        layout.addRow("Topic filter", self._filter_edit)
        layout.addRow("QoS", self._qos_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._filter_edit.setFocus()

    def subscription(self) -> Subscription | None:
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        try:
            return Subscription(
                self._filter_edit.text().strip(),
                qos=self._qos_combo.currentIndex(),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid subscription", str(error))
            return None
