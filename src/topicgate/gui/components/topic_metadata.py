from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

from topicgate.presentation.topic_presentation import TopicDetail


class TopicMetadataPane(QWidget):
    """Compact metadata renderer for the selected topic detail."""

    def __init__(self) -> None:
        super().__init__()
        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.topic = self._label("topicPathLabel", "No topic selected")
        self.topic.setWordWrap(True)
        self.received = self._label("receivedAtLabel")
        self.encoding = self._label("payloadEncodingLabel")
        self.size = self._label("payloadSizeLabel")
        self.qos = self._label("qosLabel")
        self.retained = self._label("retainedLabel")
        self.messages = self._label("messageCountLabel", "0")
        self.dropped = self._label("droppedMessageCountLabel", "0")
        for title, widget in (
            ("Topic path", self.topic),
            ("Last received", self.received),
            ("Encoding", self.encoding),
            ("Payload size", self.size),
            ("QoS", self.qos),
            ("Retained", self.retained),
            ("Message count", self.messages),
            ("Dropped messages", self.dropped),
        ):
            form.addRow(title, widget)

    def render(self, detail: TopicDetail) -> None:
        self.topic.setText(detail.topic or "No topic selected")
        self.received.setText(detail.received_at)
        self.encoding.setText(detail.payload_encoding)
        self.size.setText(detail.payload_size_label)
        self.qos.setText(detail.qos_label)
        self.retained.setText(detail.retain_label)
        self.messages.setText(str(detail.message_count))
        self.dropped.setText(str(detail.dropped_message_count))

    @staticmethod
    def _label(name: str, text: str = "-") -> QLabel:
        label = QLabel(text)
        label.setObjectName(name)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label
