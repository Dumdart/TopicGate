from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit

from topicgate.gui.main_view_model import MainViewModel
from topicgate.gui.components.workspace_pane import WorkspacePane
from topicgate.gui.components.topic_metadata import TopicMetadataPane


class TopicDetailsPane(WorkspacePane):
    """Read-only details and statistics for the selected live topic."""

    def __init__(self) -> None:
        super().__init__("Details / Stats")

        self._metadata = TopicMetadataPane()
        self.content_layout.addWidget(self._metadata)

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
