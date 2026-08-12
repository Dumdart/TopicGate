from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QLineEdit, QPlainTextEdit, QPushButton

from topicgate.gui.components.workspace_pane import WorkspacePane


class PublishPane(WorkspacePane):
    publish_requested = Signal(str, str, str)

    def __init__(self) -> None:
        super().__init__("Publish")
        self._connected = False
        self._busy = False
        form = QFormLayout()
        self._topic = QLineEdit()
        self._topic.setObjectName("publishTopic")
        self._topic.setPlaceholderText("topic/path")
        self._encoding = QComboBox()
        self._encoding.setObjectName("publishEncoding")
        self._encoding.addItem("UTF-8", "utf-8")
        self._encoding.addItem("Base64", "base64")
        form.addRow("Topic", self._topic)
        form.addRow("Encoding", self._encoding)
        self.content_layout.addLayout(form)
        self._payload = QPlainTextEdit()
        self._payload.setObjectName("publishPayload")
        self._payload.setPlaceholderText("Message payload")
        self._payload.setMaximumHeight(120)
        self.content_layout.addWidget(self._payload)
        self._publish = QPushButton("Publish message")
        self._publish.setObjectName("publishButton")
        self._publish.setProperty("primary", True)
        self._publish.clicked.connect(self._emit_publish)
        self._topic.textChanged.connect(self._update_enabled)
        self._payload.textChanged.connect(self._update_enabled)
        self.content_layout.addWidget(self._publish)

    def render(self, selected_topic: str, connected: bool, busy: bool) -> None:
        self._connected = connected
        self._busy = busy
        if selected_topic and "+" not in selected_topic and "#" not in selected_topic and not self._topic.hasFocus():
            self._topic.setText(selected_topic)
        self._publish.setText("Publishing…" if busy else "Publish message")
        for widget in (self._topic, self._payload, self._encoding):
            widget.setEnabled(not busy)
        self._update_enabled()

    def _emit_publish(self) -> None:
        self.publish_requested.emit(self._topic.text(), self._payload.toPlainText(), str(self._encoding.currentData()))

    def _update_enabled(self) -> None:
        topic = self._topic.text().strip()
        self._publish.setEnabled(
            self._connected
            and not self._busy
            and bool(topic)
            and "+" not in topic
            and "#" not in topic
            and bool(self._payload.toPlainText())
        )
