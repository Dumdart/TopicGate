from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QPlainTextEdit

from topicgate.gui.main_view_model import MainViewModel
from topicgate.gui.components.workspace_pane import WorkspacePane


class TopicDetailsPane(WorkspacePane):
    """Read-only details and statistics for the selected live topic."""

    def __init__(self) -> None:
        super().__init__("Details / Stats")

        form = QFormLayout()
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self._topic_label = QLabel("No topic selected")
        self._topic_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._topic_label.setWordWrap(True)
        self._received_at_label = QLabel("-")
        self._quality_of_service_label = QLabel("-")
        self._retained_label = QLabel("-")
        self._message_count_label = QLabel("0")
        self._dropped_message_count_label = QLabel("0")
        form.addRow("Topic path", self._topic_label)
        form.addRow("Last received", self._received_at_label)
        form.addRow("QoS", self._quality_of_service_label)
        form.addRow("Retained", self._retained_label)
        form.addRow("Message count", self._message_count_label)
        form.addRow("Dropped messages", self._dropped_message_count_label)
        self.content_layout.addLayout(form)

        self.content_layout.addWidget(self._section_label("Decoded payload"))
        self._decoded_payload = QPlainTextEdit()
        self._decoded_payload.setObjectName("decodedPayload")
        self._decoded_payload.setReadOnly(True)
        self._decoded_payload.setPlaceholderText(
            "Select a topic to inspect its payload"
        )
        self.content_layout.addWidget(self._decoded_payload, 3)

        self.content_layout.addWidget(self._section_label("Raw payload (hex)"))
        self._raw_payload = QPlainTextEdit()
        self._raw_payload.setObjectName("rawPayload")
        self._raw_payload.setReadOnly(True)
        self._raw_payload.setMaximumHeight(110)
        self.content_layout.addWidget(self._raw_payload, 1)

    def render(self, view_model: MainViewModel) -> None:
        self._topic_label.setText(view_model.topic or "No topic selected")
        self._decoded_payload.setPlainText(view_model.decoded_payload)
        self._raw_payload.setPlainText(view_model.raw_payload)
        self._received_at_label.setText(view_model.received_at)
        self._quality_of_service_label.setText(view_model.quality_of_service)
        self._retained_label.setText(view_model.retained)
        self._message_count_label.setText(view_model.message_count)
        self._dropped_message_count_label.setText(
            view_model.dropped_message_count
        )

    def focus_payload(self) -> None:
        self._decoded_payload.setFocus(Qt.FocusReason.OtherFocusReason)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600;")
        return label
