from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit

from topicgate.gui.main_view_model import MainViewModel
from topicgate.gui.components.workspace_pane import WorkspacePane
from topicgate.gui.components.topic_metadata import TopicMetadataPane


class TopicDetailsPane(WorkspacePane):
    """Read-only details and statistics for the selected live topic."""

    def __init__(self) -> None:
        super().__init__("Details / Stats")

        self._filter_notice = QLabel()
        self._filter_notice.setObjectName("subscriptionFilterNotice")
        self._filter_notice.setTextFormat(Qt.TextFormat.PlainText)
        self._filter_notice.setWordWrap(True)
        self._filter_notice.setHidden(True)
        self.content_layout.addWidget(self._filter_notice)

        self._metadata = TopicMetadataPane()
        self.content_layout.addWidget(self._metadata)

        self._decoded_label = self._section_label("Decoded payload")
        self.content_layout.addWidget(self._decoded_label)
        self._decoded_payload = QPlainTextEdit()
        self._decoded_payload.setObjectName("decodedPayload")
        self._decoded_payload.setReadOnly(True)
        self._decoded_payload.setPlaceholderText(
            "Select a topic to inspect its payload"
        )
        self.content_layout.addWidget(self._decoded_payload, 3)

        self._raw_label = self._section_label("Raw payload (hex)")
        self.content_layout.addWidget(self._raw_label)
        self._raw_payload = QPlainTextEdit()
        self._raw_payload.setObjectName("rawPayload")
        self._raw_payload.setReadOnly(True)
        self._raw_payload.setMaximumHeight(110)
        self.content_layout.addWidget(self._raw_payload, 1)

    def render(self, view_model: MainViewModel) -> None:
        wildcard_subscription = view_model.selected_wildcard_subscription
        showing_filter = wildcard_subscription is not None
        self._filter_notice.setVisible(showing_filter)
        for widget in (
            self._metadata,
            self._decoded_label,
            self._decoded_payload,
            self._raw_label,
            self._raw_payload,
        ):
            widget.setVisible(not showing_filter)
        if wildcard_subscription is not None:
            self._filter_notice.setText(
                f"Subscription filter: {wildcard_subscription.topic_filter}\n\n"
                "This filter does not carry a payload. Matching MQTT messages "
                "appear under their concrete topic paths in the Observer Tree."
            )
            return

        detail = view_model.topic_detail
        self._metadata.render(detail)
        self._decoded_payload.setPlainText(detail.decoded_payload)
        self._raw_payload.setPlainText(detail.raw_payload)

    def focus_payload(self) -> None:
        self._decoded_payload.setFocus(Qt.FocusReason.OtherFocusReason)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600;")
        return label


# Backward-compatible name while the pane acts as the primary content component.
TopicContentPane = TopicDetailsPane
