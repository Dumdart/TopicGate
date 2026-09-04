from base64 import b64encode
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from topicgate.core.models.connection_status import ConnectionStatus
from topicgate.core.models.health import ActionKind, EqualCondition, HealthExpectation
from topicgate.gui.main_view_model import MainViewModel


class ExpectationEditor(QWidget):
    """Edit broker- or topic-scoped equality expectations."""

    def __init__(
        self,
        view_model: MainViewModel,
        target_kind: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if target_kind not in {"broker", "topic"}:
            raise ValueError("target_kind must be 'broker' or 'topic'")
        self._view_model = view_model
        self._target_kind = target_kind
        self._selected_id: UUID | None = None
        self._expectations: tuple[HealthExpectation, ...] = ()
        self.setObjectName(f"{target_kind}ExpectationEditor")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._context = QLabel()
        self._context.setObjectName("expectationContext")
        self._context.setWordWrap(True)
        layout.addWidget(self._context)

        self._table = QTableWidget(0, 4)
        self._table.setObjectName("expectationTable")
        self._table.setHorizontalHeaderLabels(
            ["Name", "Expected", "State", "Revision"]
        )
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        self._table.cellClicked.connect(self._select_row)
        layout.addWidget(self._table, 1)

        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setObjectName("expectationName")
        self._description = QLineEdit()
        self._description.setObjectName("expectationDescription")
        self._expected = QComboBox()
        self._expected.setObjectName("expectationExpectedValue")
        self._expected.setEditable(target_kind == "topic")
        if target_kind == "broker":
            self._expected.addItems([item.value for item in ConnectionStatus])
            self._expected.setCurrentText(ConnectionStatus.CONNECTED.value)
        self._encoding = QComboBox()
        self._encoding.setObjectName("expectationEncoding")
        self._encoding.addItem("UTF-8 text", "utf-8")
        self._encoding.addItem("Base64 bytes", "base64")
        self._encoding.setVisible(target_kind == "topic")
        self._enabled = QCheckBox("Enabled")
        self._enabled.setObjectName("expectationEnabled")
        self._enabled.setChecked(True)
        self._log_action = QCheckBox("Log transitions")
        self._log_action.setObjectName("expectationLogAction")
        self._log_action.setChecked(True)
        self._store_action = QCheckBox("Store failure history")
        self._store_action.setObjectName("expectationStoreAction")
        self._store_action.setChecked(True)
        form.addRow("Name", self._name)
        form.addRow("Description", self._description)
        form.addRow("Expected", self._expected)
        if target_kind == "topic":
            form.addRow("Encoding", self._encoding)
        form.addRow("", self._enabled)
        form.addRow("Actions", self._log_action)
        form.addRow("", self._store_action)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self._new_button = QPushButton("Add expectation")
        self._new_button.setObjectName("addExpectationButton")
        self._delete_button = QPushButton("Delete")
        self._delete_button.setObjectName("deleteExpectationButton")
        self._save_button = QPushButton("Save")
        self._save_button.setObjectName("saveExpectationButton")
        self._new_button.clicked.connect(self._new)
        self._delete_button.clicked.connect(self._delete)
        self._save_button.clicked.connect(self._save)
        buttons.addWidget(self._new_button)
        buttons.addStretch(1)
        buttons.addWidget(self._delete_button)
        buttons.addWidget(self._save_button)
        layout.addLayout(buttons)

        self._view_model.health_changed.connect(self.render)
        self.render()

    def render(self) -> None:
        if self._target_kind == "topic":
            topic = self._view_model.topic
            available = bool(topic) and "+" not in topic and "#" not in topic
            self._context.setText(
                f"Expectations for {topic}"
                if available
                else "Select an exact topic to configure expectations."
            )
            self._expectations = self._view_model.topic_expectations
        else:
            available = True
            self._context.setText(
                f"Broker expectations for "
                f"{self._view_model.active_broker_profile.name}"
            )
            self._expectations = self._view_model.broker_expectations

        self._table.setRowCount(len(self._expectations))
        for row, expectation in enumerate(self._expectations):
            values = (
                expectation.name,
                self._expected_label(expectation),
                "Enabled" if expectation.enabled else "Disabled",
                str(expectation.revision),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, expectation.expectation_id)
                self._table.setItem(row, column, item)
        self._new_button.setEnabled(available)
        self._set_form_enabled(available)
        if self._selected_id is not None:
            selected = next(
                (
                    item
                    for item in self._expectations
                    if item.expectation_id == self._selected_id
                ),
                None,
            )
            if selected is not None:
                self._load(selected)
                return
        self._selected_id = None
        self._delete_button.setEnabled(False)

    def _new(self) -> None:
        self._selected_id = None
        self._name.clear()
        self._description.clear()
        self._enabled.setChecked(True)
        self._log_action.setChecked(True)
        self._store_action.setChecked(True)
        if self._target_kind == "topic":
            self._expected.setEditText("")
            self._encoding.setCurrentIndex(0)
        else:
            self._expected.setCurrentText(ConnectionStatus.CONNECTED.value)
        self._delete_button.setEnabled(False)
        self._name.setFocus(Qt.FocusReason.OtherFocusReason)

    def _select_row(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._expectations):
            self._load(self._expectations[row])

    def _load(self, expectation: HealthExpectation) -> None:
        self._selected_id = expectation.expectation_id
        self._name.setText(expectation.name)
        self._description.setText(expectation.description)
        self._enabled.setChecked(expectation.enabled)
        self._log_action.setChecked(ActionKind.LOG in expectation.actions)
        self._store_action.setChecked(
            ActionKind.STORE_FAILURE in expectation.actions
        )
        value = expectation.condition.expected_value
        if self._target_kind == "broker":
            self._expected.setCurrentText(str(value))
        elif isinstance(value, bytes):
            try:
                self._expected.setEditText(value.decode("utf-8"))
                self._encoding.setCurrentIndex(0)
            except UnicodeDecodeError:
                self._expected.setEditText(b64encode(value).decode("ascii"))
                self._encoding.setCurrentIndex(1)
        else:
            self._expected.setEditText(str(value))
            self._encoding.setCurrentIndex(0)
        self._delete_button.setEnabled(True)

    def _save(self) -> None:
        try:
            self._view_model.save_expectation(
                target_kind=self._target_kind,
                expectation_id=self._selected_id,
                name=self._name.text(),
                description=self._description.text(),
                expected_value=self._expected.currentText(),
                encoding=str(self._encoding.currentData() or "utf-8"),
                enabled=self._enabled.isChecked(),
                log_action=self._log_action.isChecked(),
                store_failure=self._store_action.isChecked(),
            )
        except (RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "Invalid expectation", str(error))
            return
        self._selected_id = None
        self.render()

    def _delete(self) -> None:
        if self._selected_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete expectation?",
            "Delete this expectation? Its active failure will be closed and "
            "historical episodes will be retained.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._view_model.delete_expectation(self._selected_id)
        self._selected_id = None
        self._new()
        self.render()

    def _set_form_enabled(self, enabled: bool) -> None:
        for widget in (
            self._name,
            self._description,
            self._expected,
            self._encoding,
            self._enabled,
            self._log_action,
            self._store_action,
            self._save_button,
        ):
            widget.setEnabled(enabled)

    @staticmethod
    def _expected_label(expectation: HealthExpectation) -> str:
        condition = expectation.condition
        if not isinstance(condition, EqualCondition):
            return type(condition).__name__
        value = condition.expected_value
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return f"Base64: {b64encode(value).decode('ascii')}"
        return str(value)
