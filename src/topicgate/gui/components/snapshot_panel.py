from PySide6.QtCore import QLocale, Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from topicgate.app.services.broker_snapshot_service import (
    MAX_SNAPSHOT_RESULT_LIMIT,
)
from topicgate.core.payload_limits import MAX_RENDERED_PAYLOAD_BYTES
from topicgate.presentation.snapshot_presentation import (
    BrokerSnapshotHealth,
    SnapshotQuery,
)


class SnapshotPanel(QWidget):
    """Collapsible snapshot controls and broker-wide health summary."""

    apply_requested = Signal(object)
    reset_requested = Signal()
    reconnect_observe_requested = Signal(object)
    validation_failed = Signal(str)
    expansion_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("snapshotPanel")
        self.setMinimumWidth(0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        header = QFrame()
        header.setObjectName("snapshotHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(8, 3, 8, 3)
        header_layout.setSpacing(2)
        primary_summary = QHBoxLayout()
        primary_summary.setSpacing(7)
        self._toggle = QToolButton()
        self._toggle.setObjectName("snapshotToggleButton")
        self._toggle.setText("Snapshot")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._toggle.setAccessibleName("Snapshot details")
        self._toggle.toggled.connect(self._set_expanded)
        primary_summary.addWidget(self._toggle)
        primary_summary.addStretch(1)
        self._summary_labels = {
            name: self._summary_label(object_name)
            for name, object_name in (
                ("connection", "snapshotSummaryConnection"),
                ("returned", "snapshotSummaryReturned"),
                ("dropped", "snapshotSummaryDropped"),
                ("completeness", "snapshotSummaryCompleteness"),
            )
        }
        primary_summary.addWidget(self._summary_labels["connection"])
        primary_summary.addWidget(self._summary_labels["completeness"])
        secondary_summary = QHBoxLayout()
        secondary_summary.setSpacing(12)
        secondary_summary.addStretch(1)
        secondary_summary.addWidget(self._summary_labels["returned"])
        secondary_summary.addWidget(self._summary_labels["dropped"])
        header_layout.addLayout(primary_summary)
        header_layout.addLayout(secondary_summary)
        layout.addWidget(header)

        self._content = QWidget()
        self._content.setObjectName("snapshotContent")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        controls = QGroupBox("Snapshot filters")
        controls.setObjectName("snapshotControls")
        form = QFormLayout(controls)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._topic_filter = QLineEdit("#")
        self._topic_filter.setObjectName("snapshotTopicFilter")
        self._maximum_age = QLineEdit()
        self._maximum_age.setObjectName("snapshotMaximumAge")
        self._maximum_age.setPlaceholderText("No maximum")
        age_validator = QDoubleValidator(0.0, float("inf"), 3, self)
        age_validator.setLocale(QLocale.c())
        self._maximum_age.setValidator(age_validator)
        self._result_limit = QSpinBox()
        self._result_limit.setObjectName("snapshotResultLimit")
        self._result_limit.setRange(1, MAX_SNAPSHOT_RESULT_LIMIT)
        self._payload_limit = QSpinBox()
        self._payload_limit.setObjectName("snapshotPayloadLimit")
        self._payload_limit.setRange(0, MAX_RENDERED_PAYLOAD_BYTES)
        self._payload_limit.setSuffix(" bytes")
        form.addRow("Topic filter", self._topic_filter)
        form.addRow("Maximum age (seconds)", self._maximum_age)
        form.addRow("Result limit", self._result_limit)
        form.addRow("Payload rendering limit", self._payload_limit)

        button_row = QHBoxLayout()
        apply_button = QPushButton("Apply")
        apply_button.setObjectName("applySnapshotButton")
        clear_button = QPushButton("Clear filters")
        clear_button.setObjectName("clearSnapshotFiltersButton")
        apply_button.clicked.connect(self._emit_apply)
        clear_button.clicked.connect(self._clear_filters)
        button_row.addWidget(apply_button)
        button_row.addWidget(clear_button)
        form.addRow(button_row)

        self._warning = QLabel(
            "Reconnect & observe interrupts and renews the active broker "
            "connection before capturing a new snapshot."
        )
        self._warning.setObjectName("reconnectObserveWarning")
        self._warning.setWordWrap(True)
        self._warning.setStyleSheet("color: #92400e;")
        form.addRow(self._warning)
        observe_button = QPushButton("Reconnect && observe")
        observe_button.setObjectName("reconnectObserveButton")
        observe_button.setAccessibleName("Reconnect & observe")
        observe_button.clicked.connect(self._emit_observe)
        form.addRow(observe_button)
        content_layout.addWidget(controls)

        health_group = QGroupBox("Snapshot health")
        health_group.setObjectName("snapshotHealthPanel")
        health_form = QFormLayout(health_group)
        health_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._health_labels = {
            name: self._label(object_name)
            for name, object_name in (
                ("captured", "snapshotCapturedAt"),
                ("connected", "snapshotConnectedAt"),
                ("observation", "snapshotObservationStartedAt"),
                ("duration", "snapshotObservationDuration"),
                ("returned", "snapshotReturnedCount"),
                ("omitted", "snapshotOmittedCount"),
                ("stale", "snapshotStaleCount"),
                ("truncated", "snapshotTruncatedCount"),
                ("dropped", "snapshotDroppedCount"),
                ("completeness", "snapshotCompletenessStatus"),
            )
        }
        for title, key in (
            ("Captured", "captured"),
            ("Connected", "connected"),
            ("Observation", "observation"),
            ("Observed for", "duration"),
            ("Returned", "returned"),
            ("Omitted", "omitted"),
            ("Stale", "stale"),
            ("Truncated", "truncated"),
            ("Dropped", "dropped"),
            ("Completeness", "completeness"),
        ):
            health_form.addRow(title, self._health_labels[key])
        self._limitations = self._label("snapshotLimitations")
        self._limitations.setWordWrap(True)
        health_form.addRow("Limitations", self._limitations)
        content_layout.addWidget(health_group)
        layout.addWidget(self._content)

        self._action_widgets = (
            apply_button,
            clear_button,
            observe_button,
        )
        self.render_query(SnapshotQuery())
        self.render_connection_status("disconnected")
        self._summary_labels["returned"].setText("Returned 0")
        self._summary_labels["dropped"].setText("Dropped 0")
        self._summary_labels["completeness"].setText("Limited")
        self._set_expanded(False)

    @property
    def is_expanded(self) -> bool:
        return self._toggle.isChecked()

    @property
    def query(self) -> SnapshotQuery:
        age_text = self._maximum_age.text().strip()
        try:
            maximum_age = None if not age_text else float(age_text)
        except ValueError as error:
            raise ValueError(
                "Maximum age must be a non-negative number or blank."
            ) from error
        return SnapshotQuery(
            topic_filter=self._topic_filter.text().strip(),
            max_age_seconds=maximum_age,
            result_limit=self._result_limit.value(),
            payload_limit_bytes=self._payload_limit.value(),
        )

    def set_expanded(self, expanded: bool) -> None:
        self._toggle.setChecked(expanded)

    def render_query(self, query: SnapshotQuery) -> None:
        self._topic_filter.setText(query.topic_filter)
        self._maximum_age.setText(
            "" if query.max_age_seconds is None else str(query.max_age_seconds)
        )
        self._result_limit.setValue(query.result_limit)
        self._payload_limit.setValue(query.payload_limit_bytes)

    def render_connection_status(self, status: str) -> None:
        value = status.replace("_", " ").title()
        label = self._summary_labels["connection"]
        label.setText(value)
        color = {
            "connected": "#168a55",
            "connecting": "#92400e",
            "reconnecting": "#92400e",
            "disconnected": "#9f2f2f",
        }.get(status.lower(), "#4b5563")
        label.setStyleSheet(f"color: {color};")
        self._update_summary_accessibility()

    def render_health(self, health: BrokerSnapshotHealth) -> None:
        values = {
            "captured": health.captured_at_label,
            "connected": health.connected_at_label,
            "observation": health.observation_started_at_label,
            "duration": health.observed_for_label,
            "returned": str(health.returned_count),
            "omitted": str(health.omitted_count),
            "stale": str(health.stale_count),
            "truncated": str(health.truncated_count),
            "dropped": str(health.dropped_message_count),
            "completeness": health.completeness_status,
        }
        for name, value in values.items():
            self._health_labels[name].setText(value)
        self._limitations.setText(
            "\n".join(f"- {item}" for item in health.limitation_labels) or "None"
        )
        self._summary_labels["returned"].setText(
            f"Returned {health.returned_count}"
        )
        self._summary_labels["dropped"].setText(
            f"Dropped {health.dropped_message_count}"
        )
        completeness = self._summary_labels["completeness"]
        completeness.setText(health.completeness_status)
        completeness.setStyleSheet(
            "color: #168a55;"
            if health.completeness_status == "Complete"
            else "color: #92400e;"
        )
        self._update_summary_accessibility()

    def set_busy(self, busy: bool) -> None:
        for widget in self._action_widgets:
            widget.setEnabled(not busy)

    def _set_expanded(self, expanded: bool) -> None:
        self._content.setVisible(expanded)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        state = "expanded" if expanded else "collapsed"
        self._toggle.setAccessibleDescription(
            f"Snapshot details are {state}."
        )
        action = "Collapse" if expanded else "Expand"
        self._toggle.setAccessibleName(f"{action} snapshot details")
        self._toggle.setToolTip(f"{action} snapshot details")
        self.expansion_changed.emit(expanded)

    def _update_summary_accessibility(self) -> None:
        summary = ", ".join(
            label.text() for label in self._summary_labels.values()
        )
        self._toggle.setAccessibleDescription(
            f"Snapshot details are {'expanded' if self.is_expanded else 'collapsed'}. "
            f"{summary}."
        )

    def _emit_apply(self) -> None:
        self._emit_query(self.apply_requested)

    def _emit_observe(self) -> None:
        self._emit_query(self.reconnect_observe_requested)

    def _clear_filters(self) -> None:
        query = SnapshotQuery()
        self.render_query(query)
        self.reset_requested.emit()

    def _emit_query(self, signal: Signal) -> None:
        try:
            query = self.query
        except ValueError as error:
            self.validation_failed.emit(str(error))
            return
        signal.emit(query)

    @staticmethod
    def _label(name: str) -> QLabel:
        label = QLabel("-")
        label.setObjectName(name)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @staticmethod
    def _summary_label(name: str) -> QLabel:
        label = QLabel("-")
        label.setObjectName(name)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setStyleSheet("color: #4b5563;")
        return label
